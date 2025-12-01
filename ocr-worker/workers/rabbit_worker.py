# ocr-worker/workers/rabbit_worker_v5.py

import json
import os
import socket
import time
from datetime import datetime, timedelta

import pika
import psycopg2

from ocr_engine.schemas import PredictRequest
from ocr_engine.predictor import run_ocr

# ------------------------------------------------------------
# DB 접속 설정 (V3/V4와 동일)
# ------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "mq_database",
    "user": "jewan",
    "password": "jewan",
}

# ------------------------------------------------------------
# RabbitMQ 접속 설정 (V5에서 추가)
# ------------------------------------------------------------
RABBITMQ_CONFIG = {
    "host": "localhost",
    "port": 5672,
    "username": "jewan",
    "password": "jewan",
}

# Spring 쪽 RabbitMqConfig 에서 만든 큐 이름과 동일하게 맞춘다.
QUEUE_NAME = "ocr.jobs"

# 여러 워커를 띄웠을 때 구분용 (로그용으로만 사용)
_env_name = os.getenv("CONSUMER_NAME")
if _env_name:
    CONSUMER_NAME = _env_name
else:
    host = socket.gethostname()
    pid = os.getpid()
    CONSUMER_NAME = f"{host}-{pid}"

# 처리할 Job 이 없을 때 재시도 간격 (에러 발생 시 sleep 용)
RETRY_SLEEP_SEC = 3.0

# Job 생성 후 몇 초가 지나면 타임아웃으로 간주할지 (요구사항: 60초)
MAX_WAIT_SEC = 60


def get_db_connection():
    """
    PostgreSQL 커넥션 생성.

    - 단일 워커 프로세스 기준으로 하나만 생성해서 재사용한다.
    - 여러 워커 프로세스를 띄우면 각자 독립된 커넥션을 가진다.
    """
    print("[Worker] connecting to DB...", flush=True)
    conn = psycopg2.connect(**DB_CONFIG)
    print(
        f"[Worker] DB connected (host={DB_CONFIG['host']}, db={DB_CONFIG['dbname']})",
        flush=True,
    )
    return conn


def get_rabbitmq_channel():
    """
    RabbitMQ BlockingConnection + Channel 생성.

    - queue_declare(durable=True) 로 큐를 보장한다.
    - basic_qos(prefetch_count=1) 로 한 워커가 한 번에 한 메시지만 처리하게 한다.
    """
    print("[Worker] connecting to RabbitMQ...", flush=True)

    credentials = pika.PlainCredentials(
        RABBITMQ_CONFIG["username"], RABBITMQ_CONFIG["password"]
    )
    params = pika.ConnectionParameters(
        host=RABBITMQ_CONFIG["host"],
        port=RABBITMQ_CONFIG["port"],
        credentials=credentials,
    )

    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    # 큐가 없으면 생성 (durable=True → 브로커 재시작해도 유지)
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    # 한 번에 한 메시지씩만 전달받도록 설정
    channel.basic_qos(prefetch_count=1)

    print(f"[Worker] RabbitMQ connected. queue={QUEUE_NAME}", flush=True)
    return connection, channel


def mark_job_processing_if_valid(conn, job_id: int) -> bool:
    """
    RabbitMQ 에서 받은 job_id 기준으로,
    - DB 에서 해당 Job 을 조회하고
    - 만료 여부 / 상태를 검사한 뒤
    - 유효하면 PROCESSING 으로 변경한다.

    V3/V4 의 역할과 동일하지만, "어느 Job 을 가져올지"는 RabbitMQ 가 결정하고
    여기서는 "그 Job 이 아직 유효한지 검증 + PROCESSING 변경"만 담당한다.

    반환값:
    - True  : PROCESSING 으로 변경 완료 → 실제 처리 진행
    - False : 이미 만료되었거나 PENDING 이 아님 / 존재하지 않음 → 처리하지 않고 넘김
    """
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pdf_name, status, created_at
                FROM ocr_job
                WHERE id = %s
                FOR UPDATE
                """,
                (job_id,),
            )
            row = cur.fetchone()

            if row is None:
                print(
                    f"[Worker] job_id={job_id} not found in DB. skip.",
                    flush=True,
                )
                return False

            pdf_name, status, created_at = row
            now = datetime.now()

            if status != "PENDING":
                print(
                    f"[Worker] job_id={job_id} status is not PENDING ({status}). skip.",
                    flush=True,
                )
                return False

            if now - created_at > timedelta(seconds=MAX_WAIT_SEC):
                print(
                    f"[Worker] job_id={job_id} expired "
                    f"(created_at={created_at}, now={now}), mark FAILED",
                    flush=True,
                )
                cur.execute(
                    "UPDATE ocr_job SET status = 'FAILED' WHERE id = %s",
                    (job_id,),
                )
                return False

            print(
                f"[Worker] picked job_id={job_id}, pdf_name={pdf_name}",
                flush=True,
            )
            cur.execute(
                "UPDATE ocr_job SET status = 'PROCESSING' WHERE id = %s",
                (job_id,),
            )
            return True


def update_job_status(conn, job_id: int, success: bool):
    """
    Job 처리 결과에 따라 상태를 DONE / FAILED 로 업데이트한다.
    """
    status = "DONE" if success else "FAILED"

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ocr_job SET status = %s WHERE id = %s",
                (status, job_id),
            )
    print(f"[Worker] job_id={job_id} -> status={status}", flush=True)


def process_job(job_id: int, pdf_name: str) -> bool:
    """
    실제 OCR 작업을 수행한다.

    - FastAPI HTTP 호출 없이, ocr_engine 의 run_ocr(PredictRequest)를 직접 호출한다.
    - PDF 존재 여부 등은 run_ocr 의 결과 message 로 판단한다.

    반환값:
    - 성공 시 True, 실패 시 False
    """
    print(f"[Worker] run_ocr start job_id={job_id}, pdf_name={pdf_name}", flush=True)

    try:
        req = PredictRequest(pdf_name=pdf_name)
        res = run_ocr(req)

        if res.message.startswith("pdf not found"):
            print(
                f"[Worker] job_id={job_id} failed: {res.message}",
                flush=True,
            )
            return False

        print(
            f"[Worker] job_id={job_id} succeeded (message={res.message})",
            flush=True,
        )
        return True
    except Exception as e:
        print(f"[Worker] job_id={job_id} ERROR: {e}", flush=True)
        return False


def main_loop():
    """
    워커 메인 루프 (V5: RabbitMQ 기반).

    흐름:
    1) RabbitMQ 큐(ocr.jobs)에서 메시지를 consume 한다.
    2) 메시지(body)는 JSON 문자열이라고 가정한다.
       - {"jobId": "1", "pdfName": "sample.pdf", "createdAt": "..."}
    3) DB 에서 jobId 기준으로 유효성 검사 + PROCESSING 변경
    4) OCR 처리
    5) DONE/FAILED 업데이트
    6) 성공/실패 여부에 따라 basic_ack / basic_nack(requeue) 처리
    """
    print(f"[Worker] starting main loop (RabbitMQ) as consumer={CONSUMER_NAME}...", flush=True)

    conn = get_db_connection()
    rabbit_conn, channel = get_rabbitmq_channel()

    # 콜백 내부에서 DB 커넥션과 채널을 사용한다.
    def on_message(ch, method, properties, body):
        """
        RabbitMQ 메시지 한 건을 처리하는 콜백.

        - body: 프로듀서(Spring)에서 보낸 JSON 문자열 (bytes)
        """
        print(f"[Worker] received raw message: delivery_tag={method.delivery_tag}", flush=True)

        try:
            # 1. JSON 파싱
            text = body.decode("utf-8")
            payload = json.loads(text)

            job_id_str = payload.get("jobId")
            pdf_name = payload.get("pdfName")

            if job_id_str is None or pdf_name is None:
                print(
                    f"[Worker] invalid message payload (jobId/pdfName missing): {payload}",
                    flush=True,
                )
                # 재시도해도 의미 없으므로 바로 ACK 처리
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            try:
                job_id = int(job_id_str)
            except ValueError:
                print(
                    f"[Worker] invalid jobId value (not int). jobId={job_id_str}",
                    flush=True,
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # 2. DB 에서 Job 상태 확인 + PROCESSING 변경
            is_valid = mark_job_processing_if_valid(conn, job_id)
            if not is_valid:
                # 이미 만료/처리된 Job 이면 재전달 의미 없으므로 ACK
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # 3. 실제 OCR 처리
            success = process_job(job_id, str(pdf_name))

            # 4. 처리 결과에 따라 DONE/FAILED 업데이트
            update_job_status(conn, job_id, success)

            # 5. 최종 ACK
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[Worker] ACK delivery_tag={method.delivery_tag}, job_id={job_id}", flush=True)

        except Exception as e:
            # 예기치 못한 오류가 난 경우:
            # - 일단 로그를 남기고,
            # - requeue=True 로 NACK 을 날려 재시도 기회를 남긴다.
            print(f"[Worker] unexpected error while handling message: {e}", flush=True)
            try:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except Exception as nack_err:
                print(f"[Worker] failed to NACK message: {nack_err}", flush=True)

            # 너무 자주 도는 것 방지용으로 약간 sleep
            time.sleep(RETRY_SLEEP_SEC)

    # 큐 소비 시작
    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=on_message,
        auto_ack=False,  # 반드시 수동 ACK 를 사용해야 재전달/재시도 제어 가능
    )

    print("[Worker] waiting for messages. To exit press CTRL+C", flush=True)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("[Worker] KeyboardInterrupt received. stopping...", flush=True)
        channel.stop_consuming()
    finally:
        rabbit_conn.close()
        conn.close()
        print("[Worker] RabbitMQ & DB connection closed.", flush=True)


if __name__ == "__main__":
    main_loop()
