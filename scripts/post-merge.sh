#!/bin/bash
# Post-merge for Replit workspace — install only; DB push is opt-in.
set -e
cd "$(dirname "$0")/.."

# Never let Corepack/pnpm self-install a mismatched packageManager (pnpm@9 SIGABRT).
export COREPACK_ENABLE_STRICT="${COREPACK_ENABLE_STRICT:-0}"
export COREPACK_ENABLE_AUTO_PIN="${COREPACK_ENABLE_AUTO_PIN:-0}"
export COREPACK_ENABLE_DOWNLOAD_PROMPT="${COREPACK_ENABLE_DOWNLOAD_PROMPT:-0}"

bash scripts/verify-layout.sh
pnpm install --frozen-lockfile || pnpm install
# Optional: uncomment when DATABASE_URL is configured for @workspace/db
# pnpm --filter @workspace/db run push
