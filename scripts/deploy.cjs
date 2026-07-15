#!/usr/bin/env node
/**
 * Single deploy preparation script (infra only — no Aurora logic).
 *
 * Steps:
 *   1. layout verify
 *   2. pnpm install
 *   3. production web build
 *   4. print backend + Republish checklist
 *
 * Usage (repo root):
 *   node scripts/deploy.cjs
 *   pnpm run deploy
 */
"use strict";

const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

function run(cmd, opts = {}) {
  console.log("\n>>", cmd);
  execSync(cmd, {
    cwd: ROOT,
    stdio: "inherit",
    env: {
      ...process.env,
      COREPACK_ENABLE_STRICT: "0",
      COREPACK_ENABLE_AUTO_PIN: "0",
      COREPACK_ENABLE_DOWNLOAD_PROMPT: "0",
      CI: process.env.CI || "true",
    },
    ...opts,
  });
}

function bash(scriptRel) {
  const script = path.join(ROOT, scriptRel);
  if (process.platform === "win32") {
    const gitBash = "C:\\Program Files\\Git\\bin\\bash.exe";
    if (fs.existsSync(gitBash)) {
      run(`"${gitBash}" "${script}"`);
      return;
    }
  }
  run(`bash "${script}"`);
}

console.log("== Aurora deploy prep ==");
console.log("Root:", ROOT);
console.log("NOTE: Source of truth is GitHub. Do not rely on Replit auto-commits.");

bash("scripts/verify-layout.sh");

try {
  run("pnpm install --frozen-lockfile");
} catch {
  console.warn("frozen-lockfile failed — retrying pnpm install");
  run("pnpm install");
}

run("node scripts/build-web-production.cjs");

const buildTxt = path.join(
  ROOT,
  "artifacts",
  "web",
  "dist",
  "public",
  "aurora-ui-build.txt",
);
if (fs.existsSync(buildTxt)) {
  console.log("\nUI build id:", fs.readFileSync(buildTxt, "utf8").trim());
}

console.log(`
════════════════════════════════════════════════════════
  Build local OK. Próximos passos (deploy):

  A) Backend (uma vez / quando requirements mudarem):
       pip install -r artifacts/aurora/requirements.txt
       cd artifacts/aurora && python tests/smoke_health.py

  B) Publicar no Replit:
       1. git push origin main   (commits feitos por você — não pelo Agent)
       2. No Replit Shell: pull se necessário, depois Republish
       3. Hard refresh (Ctrl+Shift+R)

  Procedimento completo: DEPLOY.md
════════════════════════════════════════════════════════
`);
