#!/bin/bash
set -e
cd /app/backend
# Bootstrap the super-admin account (idempotent; never blocks startup).
python ensure_admin.py || true
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
