# ocr-worker/workers/db_worker_v4.py
import os
import socket
import time
from datetime import datetime, timedelta

import psycopg2
import redis

from ocr_engine.schemas import PredictRequest
from ocr_engine.predictor import run_ocr

# ------------------------------------------------------------
# DB 접속 설정
# ------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "mq_database",
    "user": "jewan",
    "password": "jewan",
}

# ------------------------------------------------------------
# Redis 접속 및 Streams 설정 (V4에서 추가)
# ------------------------------------------------------------
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "decode_responses": True,  # 응답을 문자열(str)로 받기 위함
}

STREAM_KEY = "ocr:jobs"        # API 서버에서 XADD 하는 Stream 키
GROUP_NAME = "ocr-workers"     # Spring 에서도 같은 이름으로 그룹 생성

_env_name = os.getenv("CONSUMER_NAME")  # 필요하면 외부에서 강제로 지정 가능
if _env_name:
    CONSUMER_NAME = _env_name
else:
    # hostname + pid 조합으로 유니크한 consumer 이름 자동 생성
    host = socket.gethostname()
    pid = os.getpid()
    CONSUMER_NAME = f"{host}-{pid}"

# Redis XREADGROUP block 시간 (ms)
REDIS_BLOCK_MS = 5000  # 5초

# 처리할 Job 이 없을 때 다시 조회하기까지 대기 시간(초)
POLL_INTERVAL_SEC = 1.0

# 요청 후 몇 초가 지나면 타임아웃으로 간주할지 (요구사항: 60초)
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


def get_redis_connection():
    """
    Redis 커넥션 생성 (redis-py 클라이언트).

    decode_responses=True 로 설정해서,
    - key / field / value 를 모두 문자열(str)로 다루기 쉽게 만든다.
    """
    print("[Worker] connecting to Redis...", flush=True)
    conn = redis.Redis(**REDIS_CONFIG)
    print("[Worker] Redis connected.", flush=True)
    return conn


def ensure_consumer_group(r: redis.Redis):
    """
    Redis Streams Consumer Group 이 없으면 생성한다.

    - Spring Boot 쪽 RedisConfig 에서 이미 생성했다면 BUSYGROUP 에러가 날 수 있는데,
      그 경우는 정상으로 보고 무시한다.
    """
    try:
        # id='$' : 그룹 생성 후 새로 들어오는 메시지부터 소비
        r.xgroup_create(name=STREAM_KEY, groupname=GROUP_NAME, id="$", mkstream=True)
        print(
            f"[Worker] Created consumer group group={GROUP_NAME} on stream={STREAM_KEY}",
            flush=True,
        )
    except redis.ResponseError as e:
        msg = str(e)
        if "BUSYGROUP" in msg:
            print(
                f"[Worker] Consumer group already exists (group={GROUP_NAME})",
                flush=True,
            )
        else:
            # 그 외 에러는 그대로 올린다.
            raise


def mark_job_processing_if_valid(conn, job_id: int) -> bool:
    """
    Redis 에서 받은 job_id 기준으로,
    - DB 에서 해당 Job 을 조회하고
    - 만료 여부 / 상태를 검사한 뒤
    - 유효하면 PROCESSING 으로 변경한다.

    V3 의 fetch_next_pending_job 과 거의 동일한 역할을 수행하지만,
    "다음 Job 을 고르는 역할"은 Redis 가 하고,
    여기서는 "해당 Job 이 아직 유효한지 검증 + PROCESSING 변경"만 담당한다.

    반환값:
    - True  : PROCESSING 으로 변경 완료 → 실제 처리 진행
    - False : 이미 만료되었거나 PENDING 이 아님 → 처리하지 않고 넘김
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

            # 해당 ID 가 DB 에 없으면 처리 불가
            if row is None:
                print(
                    f"[Worker] job_id={job_id} not found in DB. skip.",
                    flush=True,
                )
                return False

            pdf_name, status, created_at = row
            now = datetime.now()

            # 이미 PENDING 이 아니면(이미 다른 워커가 처리했거나 상태 변경됨) skip
            if status != "PENDING":
                print(
                    f"[Worker] job_id={job_id} status is not PENDING ({status}). skip.",
                    flush=True,
                )
                return False

            # 생성 후 60초가 지났으면 타임아웃으로 간주 → FAILED 처리
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

            # 아직 유효한 Job 이면 PROCESSING 으로 변경
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

    파라미터:
    - job_id: 대상 Job PK
    - success: True 이면 DONE, False 이면 FAILED 로 저장
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

        # message 내용으로 성공/실패 판별 (예시: pdf not found)
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
        # 예외 발생 시 실패 처리
        print(f"[Worker] job_id={job_id} ERROR: {e}", flush=True)
        return False


def main_loop():
    """
    워커 메인 루프 (V4: Redis Streams 기반).

    - V3 와 달리, 더 이상 DB 에서 PENDING Job 을 Polling 하지 않는다.
    - 대신 Redis Streams Consumer Group 으로부터 Job 을 가져온다.

    흐름:
    1) XREADGROUP 으로 Stream 에서 메시지(jobId, pdfName...)를 읽는다.
    2) DB 에서 해당 jobId 가 아직 PENDING 이고, 만료되지 않았는지 확인 후 PROCESSING 으로 변경
    3) process_job 실행
    4) 성공/실패에 따라 DONE / FAILED 로 상태 업데이트
    5) Redis 에 XACK 으로 메시지 ACK
    """
    print("[Worker] starting main loop (Redis Streams)...", flush=True)
    conn = get_db_connection()
    r = get_redis_connection()
    ensure_consumer_group(r)

    try:
        while True:
            try:
                # XREADGROUP 으로 새 메시지를 읽는다.
                #
                # - groupname : GROUP_NAME (ocr-workers)
                # - consumername : CONSUMER_NAME (worker-1, worker-2 ...)
                # - streams = { STREAM_KEY: '>' } → 이 그룹에서 아직 전달되지 않은 메시지
                # - count = 1 → 한 번에 최대 1개
                # - block = REDIS_BLOCK_MS(ms) → 최대 block 시간까지 대기
                entries = r.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_KEY: ">"},  # 새 메시지만
                    count=1,
                    block=REDIS_BLOCK_MS,
                )

                # 새 메시지가 없으면 잠시 대기 후 다시 루프
                if not entries:
                    time.sleep(POLL_INTERVAL_SEC)
                    continue

                # entries 구조:
                # [
                #   (
                #     'ocr:jobs',
                #     [
                #       ('1764505825504-0', { 'jobId': '1', 'pdfName': 'sample.pdf', 'createdAt': '...' })
                #     ]
                #   )
                # ]
                for stream_key, messages in entries:
                    for message_id, fields in messages:
                        print(
                            f"[Worker] received message: id={message_id}, fields={fields}",
                            flush=True,
                        )

                        # Redis 필드에서 jobId, pdfName 꺼내기
                        job_id_str = fields.get("jobId")
                        pdf_name = fields.get("pdfName")

                        if job_id_str is None or pdf_name is None:
                            print(
                                f"[Worker] invalid message fields (jobId/pdfName missing). id={message_id}",
                                flush=True,
                            )
                            # 잘못된 메시지는 재전달 의미가 없으므로 ACK 처리
                            r.xack(STREAM_KEY, GROUP_NAME, message_id)
                            continue

                        try:
                            job_id = int(job_id_str)
                        except ValueError:
                            print(
                                f"[Worker] invalid jobId value (not int). id={message_id}, jobId={job_id_str}",
                                flush=True,
                            )
                            r.xack(STREAM_KEY, GROUP_NAME, message_id)
                            continue

                        # DB 에서 이 Job 이 아직 유효한지 검사하고 PROCESSING 으로 변경
                        is_valid = mark_job_processing_if_valid(conn, job_id)
                        if not is_valid:
                            # 만료되었거나 이미 처리된 Job 이면 메시지만 ACK 하고 넘어감
                            r.xack(STREAM_KEY, GROUP_NAME, message_id)
                            continue

                        # 실제 OCR 처리 수행
                        success = process_job(job_id, str(pdf_name))

                        # 처리 결과에 따라 DONE / FAILED 로 업데이트
                        update_job_status(conn, job_id, success)

                        # 처리 완료 후 메시지 ACK
                        r.xack(STREAM_KEY, GROUP_NAME, message_id)
                        print(f"[Worker] ACK message id={message_id}", flush=True)

            except redis.RedisError as e:
                print(f"[Worker] Redis error: {e}, retry after sleep...", flush=True)
                time.sleep(5.0)
            except Exception as e:
                print(f"[Worker] unexpected error: {e}, keep running...", flush=True)
                time.sleep(3.0)

    finally:
        conn.close()
        print("[Worker] DB connection closed.", flush=True)


if __name__ == "__main__":
    main_loop()
