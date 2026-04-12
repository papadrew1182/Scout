#!/bin/bash
set -e

echo "Running Scout migrations..."
python migrate.py

echo "Starting Scout API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
