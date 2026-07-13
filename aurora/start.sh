#!/bin/bash
set -e
# Path-relative production entry — safe for Replit Republish
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 2
