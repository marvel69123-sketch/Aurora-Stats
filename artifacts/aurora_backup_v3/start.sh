#!/bin/bash
set -e
cd /home/runner/workspace/artifacts/aurora
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 2
