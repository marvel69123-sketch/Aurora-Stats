#!/bin/bash
# Production web build for Replit — always wipe stale dist first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WEB="artifacts/web"
DIST="$WEB/dist"
PUBLIC="$DIST/public"

echo "== Aurora web production build =="
test -f "$WEB/package.json" || { echo "ERROR: missing $WEB/package.json" >&2; exit 1; }

# Remove ANY previous Vite output so Replit cannot publish a stale bundle.
rm -rf "$DIST"
echo "cleared $DIST"

export CI="${CI:-true}"
export NODE_ENV=production
# MSYS/Git-Bash on Windows rewrites BASE_PATH=/ into the Git install path.
# Force a clean root base for Aurora web unless an explicit app path is set.
if [ -z "${BASE_PATH:-}" ] || [ "${BASE_PATH}" = "/" ] || [[ "${BASE_PATH}" == *Program\ Files* ]]; then
  export BASE_PATH="/"
fi
export MSYS2_ARG_CONV_EXCL="*"
export PORT="${PORT:-22333}"
export AURORA_UI_BUILD="${AURORA_UI_BUILD:-chatgpt-$(date -u +%Y%m%d%H%M%S)}"

pnpm --filter @workspace/web run build

test -f "$PUBLIC/index.html" || { echo "ERROR: missing $PUBLIC/index.html after build" >&2; exit 1; }

printf '%s\n' "$AURORA_UI_BUILD" > "$PUBLIC/aurora-ui-build.txt"

node <<'NODE'
const fs = require("fs");
const path = "artifacts/web/dist/public/index.html";
const build = fs.readFileSync("artifacts/web/dist/public/aurora-ui-build.txt", "utf8").trim();
let html = fs.readFileSync(path, "utf8");
if (!html.includes('name="aurora-ui-build"')) {
  html = html.replace(
    "</head>",
    `  <meta name="aurora-ui-build" content="${build}" />\n  </head>`,
  );
  fs.writeFileSync(path, html);
}
if (html.includes("Program Files/Git")) {
  console.error("ERROR: index.html has corrupted BASE_PATH (MSYS path rewrite)");
  process.exit(1);
}
console.log("injected aurora-ui-build meta:", build);
NODE

JS_BUNDLE="$(ls "$PUBLIC"/assets/index-*.js 2>/dev/null | head -1 || true)"
test -n "$JS_BUNDLE" || { echo "ERROR: no assets/index-*.js produced" >&2; exit 1; }

fail_if() {
  if grep -q "$1" "$JS_BUNDLE"; then
    echo "ERROR: forbidden legacy UI string in bundle: $1" >&2
    exit 1
  fi
}
require() {
  if ! grep -q "$1" "$JS_BUNDLE"; then
    echo "ERROR: required new UI string missing from bundle: $1" >&2
    exit 1
  fi
}

fail_if "Analisar uma partida"
fail_if "Aurora — Inteligência Esportiva"
require "Personalizar avatar"
require "Renomear conversa"
require "Como posso ajudar nas análises de hoje"

echo "OK served index: $PUBLIC/index.html"
echo "OK bundle:       $JS_BUNDLE"
echo "OK aurora-ui-build: $AURORA_UI_BUILD"
echo "OK verified ChatGPT-style UI; legacy empty-state absent"
