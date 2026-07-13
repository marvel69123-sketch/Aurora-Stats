#!/bin/bash
# One-way sync: artifacts/aurora (SOURCE OF TRUTH) → aurora/ (local mirror).
# Never copy the other direction for deploy. Never copy frontend to repo root.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/artifacts/aurora"
DST="$ROOT/aurora"

test -d "$SRC/src" || { echo "ERROR: missing $SRC/src" >&2; exit 1; }

mkdir -p "$DST"

# Sync Python package + entrypoints (exclude caches / local DBs)
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.replit-artifact/' \
    --exclude 'aurora.db' \
    --exclude '*.db-journal' \
    "$SRC/" "$DST/"
else
  # Windows / environments without rsync
  rm -rf "$DST/src" "$DST/brain" "$DST/tests"
  cp -R "$SRC/src" "$DST/src"
  [ -d "$SRC/brain" ] && cp -R "$SRC/brain" "$DST/brain"
  [ -d "$SRC/tests" ] && cp -R "$SRC/tests" "$DST/tests"
  for f in main.py requirements.txt start.sh run.sh; do
    [ -f "$SRC/$f" ] && cp "$SRC/$f" "$DST/$f"
  done
fi

echo "OK synced artifacts/aurora → aurora/ (local mirror only)"
echo "Deploy / Republish always uses: artifacts/aurora"
