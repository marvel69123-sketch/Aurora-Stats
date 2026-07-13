#!/bin/bash
# Post-merge for Replit workspace — install only; DB push is opt-in.
set -e
cd "$(dirname "$0")/.."
bash scripts/verify-layout.sh
pnpm install --frozen-lockfile || pnpm install
# Optional: uncomment when DATABASE_URL is configured for @workspace/db
# pnpm --filter @workspace/db run push
