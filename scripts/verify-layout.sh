#!/bin/bash
# Verify monorepo layout before install/build (Replit ~/workspace)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() { echo "ERROR: $1" >&2; exit 1; }

echo "== Aurora layout audit =="

# ── Root must be workspace package — NEVER the Vite frontend ─────────────────
grep -q '"name": "workspace"' package.json || fail "Root package.json must be name=workspace (monorepo). Do not move artifacts/web/package.json here."
test -f pnpm-workspace.yaml || fail "Missing pnpm-workspace.yaml"
test -f tsconfig.base.json || fail "Missing tsconfig.base.json"
test -f tsconfig.json || fail "Missing tsconfig.json"

# ── Deploy guard: never pin pnpm 9 (Replit SIGABRT on `pnpm add pnpm@9.x`) ───
if grep -E '"packageManager"[[:space:]]*:[[:space:]]*"pnpm@9' package.json >/dev/null 2>&1; then
  fail "package.json pins pnpm@9.x — remove packageManager (use Replit pnpm 10+). Republish was killed by pnpm add pnpm@9.15.0 / SIGABRT."
fi
if ! grep -q 'managePackageManagerVersions:[[:space:]]*false' pnpm-workspace.yaml; then
  fail "pnpm-workspace.yaml must set managePackageManagerVersions: false (permanent Replit publish fix)"
fi

# Guard: frontend files must NOT be at workspace root
for bad in vite.config.ts vite.config.js index.html; do
  if [ -f "$bad" ]; then
    fail "$bad found at workspace root. Official frontend lives in artifacts/web/"
  fi
done
if [ -d src ] && { [ -f src/main.tsx ] || [ -f src/App.tsx ]; }; then
  fail "Frontend src/ found at workspace root. Move it to artifacts/web/src/"
fi
if [ -d public ] && { [ -f public/index.html ] || [ -d public/assets ]; }; then
  fail "Frontend public/ found at workspace root. Move it to artifacts/web/public/"
fi

# ── Frontend: artifacts/web ──────────────────────────────────────────────────
test -f artifacts/web/package.json || fail "Missing artifacts/web/package.json"
test -f artifacts/web/vite.config.ts || fail "Missing artifacts/web/vite.config.ts"
test -f artifacts/web/tsconfig.json || fail "Missing artifacts/web/tsconfig.json"
test -d artifacts/web/src || fail "Missing artifacts/web/src"
grep -q '@workspace/web' artifacts/web/package.json || fail "artifacts/web/package.json must be @workspace/web"
grep -q 'artifacts/web' artifacts/web/vite.config.ts || true
# root: path must stay inside artifacts/web (import.meta.dirname)
grep -q 'import.meta.dirname' artifacts/web/vite.config.ts || fail "vite.config.ts must use import.meta.dirname (keep root inside artifacts/web)"

EXTENDS=$(grep -o '"extends"[[:space:]]*:[[:space:]]*"[^"]*"' artifacts/web/tsconfig.json | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
test -n "$EXTENDS" || fail "web tsconfig missing extends"
RESOLVED="$(cd artifacts/web && cd "$(dirname "$EXTENDS")" && pwd)/$(basename "$EXTENDS")"
test -f "$RESOLVED" || fail "broken extends: $EXTENDS -> $RESOLVED"
echo "OK web tsconfig extends -> $RESOLVED"

# ── Backend deploy: artifacts/aurora (SOURCE OF TRUTH) ───────────────────────
test -f artifacts/aurora/main.py || fail "Missing artifacts/aurora/main.py"
test -f artifacts/aurora/start.sh || fail "Missing artifacts/aurora/start.sh"
test -f artifacts/aurora/requirements.txt || fail "Missing artifacts/aurora/requirements.txt"
test -f artifacts/aurora/src/core/nl_router.py || fail "Missing artifacts/aurora/src/core/nl_router.py"
test -f artifacts/aurora/src/routers/analyze.py || fail "Missing artifacts/aurora/src/routers/analyze.py"
test -f artifacts/aurora/src/core/fixture_status.py || fail "Missing artifacts/aurora/src/core/fixture_status.py"
grep -q 'EARLY_OVERRIDE' artifacts/aurora/src/core/nl_router.py || fail "nl_router missing EARLY_OVERRIDE (live routing regression)"
grep -q 'ohiggins' artifacts/aurora/src/core/copilot_engine.py || fail "copilot_engine missing Chilean aliases"

# Deploy wiring (Replit keeps Aurora Python service declared on api-server artifact)
test -f artifacts/api-server/.replit-artifact/artifact.toml || fail "Missing artifacts/api-server/.replit-artifact/artifact.toml"
grep -q 'artifacts/aurora' artifacts/api-server/.replit-artifact/artifact.toml || fail "api-server artifact.toml must point at artifacts/aurora"
test -f artifacts/web/.replit-artifact/artifact.toml || fail "Missing artifacts/web/.replit-artifact/artifact.toml"

# ── Optional local mirror (must never diverge for critical files) ────────────
if [ -d aurora/src ]; then
  for f in src/core/nl_router.py src/core/copilot_engine.py src/routers/analyze.py src/core/fixture_status.py; do
    if [ -f "aurora/$f" ] && [ -f "artifacts/aurora/$f" ]; then
      if command -v cmp >/dev/null 2>&1; then
        cmp -s "artifacts/aurora/$f" "aurora/$f" || fail "DIVERGE: aurora/$f != artifacts/aurora/$f — run: bash scripts/sync-aurora-mirror.sh"
      fi
    fi
  done
  echo "OK aurora/ mirror matches artifacts/aurora for critical files"
fi

# Production web artifact must force clean build (stale dist was serving old UI)
grep -q 'build-web-production' artifacts/web/.replit-artifact/artifact.toml \
  || fail "web artifact.toml must use scripts/build-web-production.sh (clean rebuild)"
grep -q 'artifacts/web/dist/public' artifacts/web/.replit-artifact/artifact.toml \
  || fail "web publicDir must be artifacts/web/dist/public"

echo "OK monorepo layout verified"
echo "  frontend SoT:  artifacts/web  (ONLY product UI)"
echo "  backend SoT:   artifacts/aurora"
echo "  api scaffold:  artifacts/api-server"
echo "  libs:          lib/*"
echo "  local mirror:  aurora/ (optional; sync FROM artifacts/aurora)"
echo "  mockup:        artifacts/mockup-sandbox (excluded from workspace + deploy)"
