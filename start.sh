#!/bin/bash
set -e
cd /app/backend
python seed_admin.py < /dev/null > /dev/null 2>&1 || true
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
