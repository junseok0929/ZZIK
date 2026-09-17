#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then cp .env.example .env; fi
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -q -r backend/requirements.lock
npm --prefix frontend ci --silent
if .venv/bin/python -c 'from urllib.parse import urlparse; from backend.app.config import settings; import sys; u=urlparse(settings.database_url); sys.exit(0 if u.hostname in {"localhost", "127.0.0.1"} and u.port == 54329 else 1)'; then
  bash scripts/postgres-local.sh
fi
.venv/bin/alembic -c backend/alembic.ini upgrade head
if .venv/bin/python -c 'from backend.app.config import settings; import sys; sys.exit(0 if settings.demo_enabled and settings.face_analysis_provider == "fixture" else 1)'; then
  .venv/bin/python -m backend.app.seed
fi
mkdir -p logs
api_pid=''; worker_pid=''; web_pid=''
cleanup(){
  for task_pid in "$api_pid" "$worker_pid" "$web_pid"; do
    if [ -n "$task_pid" ]; then kill "$task_pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT INT TERM
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 >logs/api.log 2>&1 &
api_pid=$!
.venv/bin/python -m backend.app.worker >logs/worker.log 2>&1 &
worker_pid=$!
npm --prefix frontend run dev -- --host 127.0.0.1 --strictPort >logs/frontend.log 2>&1 &
web_pid=$!
printf '\nZZIK: http://127.0.0.1:5173\nLogs: logs/api.log, logs/worker.log, logs/frontend.log\nCtrl+C stops app processes; PostgreSQL and data are preserved.\n'
while kill -0 "$api_pid" 2>/dev/null && kill -0 "$worker_pid" 2>/dev/null && kill -0 "$web_pid" 2>/dev/null; do sleep 2; done
printf 'An app process exited. See logs/ for details.\n' >&2
exit 1
