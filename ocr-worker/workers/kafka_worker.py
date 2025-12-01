# ocr-worker/workers/kafka_worker.py
import os
import socket
import time
import json
from datetime import datetime, timedelta

import psycopg2
from kafka import KafkaConsumer

from ocr_engine.schemas import PredictRequest
from ocr_engine.predictor import run_ocr

# ------------------------------------------------------------
# DB 접속 설정 (V3/V4/V5와 동일)
# ------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "mq_database",
    "user": "jewan",
    "password": "jewan",
}

# ------------------------------------------------------------
# Kafka 설정 (V6)
# ------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = "ocr.jobs"
KAFKA_GROUP_ID = "ocr-workers"

_env_name = os.getenv("CONSUMER_NAME")
if _env_name:
    CONSUMER_CLIENT_ID = _env_name
else:
    host = socket.gethostname()
    pid = os.getpid()
    CONSUMER_CLIENT_ID = f"{host}-{pid}"

# 처리할 Job 이 없을 때 잠깐 쉬는 용도 (에러 시 등)
POLL_INTERVAL_SEC = 1.0

# 요청 후 몇 초가 지나면 타임아웃으로 간주할지 (요구사항: 60초)
MAX_WAIT_SEC = 60


def get_db_connection():
    """
    PostgreSQL 커넥션 생성.
    - 단일 워커 프로세스 기준 하나만 생성해서 재사용.
    """
    print("[Worker] connecting to DB...", flush=True)
    conn = psycopg2.connect(**DB_CONFIG)
    print(
        f"[Worker] DB connected (host={DB_CONFIG['host']}, db={DB_CONFIG['dbname']})",
        flush=True,
    )
    return conn


def get_kafka_consumer():
    """
    Kafka Consumer 생성.
    - group_id = 'ocr-workers' 로 설정해서 컨슈머 그룹 사용.
    - enable_auto_commit=False 로 두고, 처리 후 수동 commit.
    - value_deserializer 로 JSON 문자열을 dict 로 변환.
    """
    print("[Worker] connecting to Kafka...", flush=True)

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        group_id=KAFKA_GROUP_ID,
        client_id=CONSUMER_CLIENT_ID,
        enable_auto_commit=False,
        auto_offset_reset="latest",  # 새 그룹이면 최신 offset부터 소비
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    print(
        f"[Worker] Kafka connected. topic={KAFKA_TOPIC}, group={KAFKA_GROUP_ID}, client_id={CONSUMER_CLIENT_ID}",
        flush=True,
    )
    return consumer


def mark_job_processing_if_valid(conn, job_id: int) -> bool:
    """
    Kafka 에서 받은 job_id 기준으로,
    - DB 에서 해당 Job 을 조회하고
    - 만료 여부 / 상태를 검사한 뒤
    - 유효하면 PROCESSING 으로 변경.

    Redis V4 의 mark_job_processing_if_valid 과 동일한 역할.
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
    Job 처리 결과에 따라 상태를 DONE / FAILED 로 업데이트.
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
    실제 OCR 작업 수행.
    - ocr_engine.run_ocr 를 직접 호출.
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
    워커 메인 루프 (V6: Kafka 기반).

    흐름:
    1) Kafka Consumer Group 으로 topic(ocr.jobs)에서 메시지 consume
    2) payload(JSON)에서 jobId, pdfName 추출
    3) DB 에서 jobId 검증 후 PROCESSING 으로 변경
    4) OCR 수행
    5) DONE/FAILED 로 상태 업데이트
    6) 성공/실패와 무관하게 해당 offset commit (DB 상태가 진실의 근원)
    """
    print(f"[Worker] starting main loop (Kafka) as client_id={CONSUMER_CLIENT_ID}...", flush=True)
    conn = get_db_connection()
    consumer = get_kafka_consumer()

    try:
        while True:
            try:
                # poll 사용하면 타임아웃 제어 가능
                records = consumer.poll(timeout_ms=1000)

                if not records:
                    # 새 메시지가 없는 경우 잠깐 쉰다
                    time.sleep(POLL_INTERVAL_SEC)
                    continue

                for tp, messages in records.items():
                    for msg in messages:
                        fields = msg.value  # dict (JSON 디코딩 결과)
                        print(
                            f"[Worker] received message: topic={msg.topic}, "
                            f"partition={msg.partition}, offset={msg.offset}, value={fields}",
                            flush=True,
                        )

                        job_id_str = fields.get("jobId")
                        pdf_name = fields.get("pdfName")

                        if job_id_str is None or pdf_name is None:
                            print(
                                "[Worker] invalid message fields (jobId/pdfName missing). skip.",
                                flush=True,
                            )
                            # 잘못된 메시지도 offset 은 소비 완료로 처리
                            consumer.commit()
                            continue

                        try:
                            job_id = int(job_id_str)
                        except ValueError:
                            print(
                                f"[Worker] invalid jobId value (not int). jobId={job_id_str}",
                                flush=True,
                            )
                            consumer.commit()
                            continue

                        # DB 에서 Job 유효성 체크 + PROCESSING 변경
                        is_valid = mark_job_processing_if_valid(conn, job_id)
                        if not is_valid:
                            # 만료/이미 처리 등 -> Kafka offset 만 commit
                            consumer.commit()
                            continue

                        # 실제 OCR 처리
                        success = process_job(job_id, str(pdf_name))

                        # DB 상태 업데이트
                        update_job_status(conn, job_id, success)

                        # 이 메시지에 대한 offset commit
                        consumer.commit()
                        print(
                            f"[Worker] committed offset topic={msg.topic}, "
                            f"partition={msg.partition}, offset={msg.offset}",
                            flush=True,
                        )

            except KeyboardInterrupt:
                print("[Worker] KeyboardInterrupt received. stopping...", flush=True)
                break
            except Exception as e:
                print(
                    f"[Worker] unexpected error while handling message: {e}, keep running...",
                    flush=True,
                )
                time.sleep(3.0)

    finally:
        try:
            consumer.close()
        except Exception:
            pass
        conn.close()
        print("[Worker] Kafka & DB connection closed.", flush=True)


if __name__ == "__main__":
    main_loop()
