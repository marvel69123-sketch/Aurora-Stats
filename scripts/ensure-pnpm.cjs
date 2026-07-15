#!/usr/bin/env node
/**
 * Cross-platform install gate for the Aurora monorepo.
 * Blocks npm/yarn (broken with pnpm workspaces + catalog).
 * Safe on Windows (no `sh -c` dependency).
 */
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

for (const lock of ["package-lock.json", "yarn.lock"]) {
  const p = path.join(ROOT, lock);
  try {
    if (fs.existsSync(p)) fs.unlinkSync(p);
  } catch {
    // ignore
  }
}

const ua = String(process.env.npm_config_user_agent || "");
const isPnpm = ua.includes("pnpm/") || process.env.PNPM_SCRIPT_SRC_DIR;

if (!isPnpm) {
  console.error("");
  console.error("══════════════════════════════════════════════════════");
  console.error("  Aurora usa pnpm — não use npm install / yarn.");
  console.error("══════════════════════════════════════════════════════");
  console.error("");
  console.error("  1) Instale pnpm 10+ (ou 9.15+):");
  console.error("       npm install -g pnpm@10");
  console.error("");
  console.error("  2) Na raiz do monorepo:");
  console.error("       pnpm install");
  console.error("");
  console.error("  Deploy: ver DEPLOY.md");
  console.error("");
  process.exit(1);
}
