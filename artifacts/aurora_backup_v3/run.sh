#!/bin/bash
set -e
cd "$(dirname "$0")"
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
