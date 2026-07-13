#!/bin/bash
set -euo pipefail
# Path-relative production entry — safe for Replit Republish
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PYTHONUNBUFFERED=1
PORT="${PORT:-8080}"

# Single worker: SQLite + Autoscale healthchecks are unreliable with --workers > 1
# (multi-process socket share / DB init races caused flaky 500s on /docs and /healthz).
exec python -m uvicorn main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers 1 \
  --log-level info \
  --proxy-headers \
  --forwarded-allow-ips='*'
