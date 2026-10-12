#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
if [ ! -f .env ]; then cp .env.example .env; fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m alembic upgrade head
echo 'Open http://127.0.0.1:8000/docs'
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
