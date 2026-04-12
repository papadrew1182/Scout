#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Running Scout migrations..."
python migrate.py

echo "Running seed (idempotent)..."
python seed.py

echo "Starting Scout API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
