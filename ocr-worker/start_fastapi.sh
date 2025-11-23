#!/usr/bin/env sh
set -e

# 코드 위치로 이동
cd /app/ocr-worker

# FastAPI 서버 실행
exec uvicorn fastapi_server.app.main:app --host 0.0.0.0 --port 8000
