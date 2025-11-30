# ocr-worker/workers/db_worker.py
import time
from datetime import datetime, timedelta

import psycopg2

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


def fetch_next_pending_job(conn):
    """
    PENDING 상태의 Job 하나를 가져오고, 즉시 PROCESSING 으로 상태를 변경한다.

    동작 요약:
    1) status = 'PENDING' 인 Job 을 id 순으로 한 건 가져온다.
       - SELECT ... FOR UPDATE SKIP LOCKED 사용으로 동시성 제어
         (다른 워커가 잡고 있는 행은 SKIP).
    2) created_at 기준으로 60초가 넘은 Job 이면, 즉시 FAILED 로 바꾸고
       다음 Job 을 다시 조회한다.
    3) 아직 유효한(만료 안 된) Job 을 찾으면, 그 Job 을 PROCESSING 으로 바꾸고 반환한다.

    반환값:
    - (job_id, pdf_name) 또는 처리할 Job 이 없으면 (None, None)
    """
    with conn:
        with conn.cursor() as cur:
            while True:
                cur.execute(
                    """
                    SELECT id, pdf_name, created_at
                    FROM ocr_job
                    WHERE status = 'PENDING'
                    ORDER BY id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """
                )
                row = cur.fetchone()

                # 처리할 Job 이 전혀 없으면 끝
                if row is None:
                    return None, None

                job_id, pdf_name, created_at = row

                now = datetime.now()
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
                    # 다음 후보를 보기 위해 while 루프 계속
                    continue

                # 아직 유효한 Job 이면 PROCESSING 으로 변경 후 반환
                print(
                    f"[Worker] picked job_id={job_id}, pdf_name={pdf_name}",
                    flush=True,
                )
                cur.execute(
                    "UPDATE ocr_job SET status = 'PROCESSING' WHERE id = %s",
                    (job_id,),
                )
                return job_id, pdf_name


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
    워커 메인 루프.

    - 무한 루프를 돌면서 PENDING Job 을 계속 가져와 처리한다.
    - 처리할 Job 이 없으면 POLL_INTERVAL_SEC 만큼 대기 후 다시 조회한다.
    """
    print("[Worker] starting main loop...", flush=True)
    conn = get_db_connection()

    try:
        while True:
            job_id, pdf_name = fetch_next_pending_job(conn)

            # 처리할 Job 이 없으면 잠시 대기
            if job_id is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            success = process_job(job_id, str(pdf_name))
            update_job_status(conn, job_id, success)
    finally:
        conn.close()
        print("[Worker] DB connection closed.", flush=True)


if __name__ == "__main__":
    main_loop()
