#!/bin/bash
set -e
cd /app/backend
python seed_admin.py || true
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
