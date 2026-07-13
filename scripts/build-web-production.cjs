#!/usr/bin/env node
/**
 * Cross-platform production web build (Windows + Replit).
 * Wipes stale dist, builds @workspace/web, verifies ChatGPT UI markers.
 */
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const WEB = path.join(ROOT, "artifacts", "web");
const DIST = path.join(WEB, "dist");
const PUBLIC = path.join(DIST, "public");

function fail(msg) {
  console.error("ERROR:", msg);
  process.exit(1);
}

console.log("== Aurora web production build ==");
if (!fs.existsSync(path.join(WEB, "package.json"))) {
  fail(`missing ${path.join(WEB, "package.json")}`);
}

fs.rmSync(DIST, { recursive: true, force: true });
console.log("cleared", DIST);

let basePath = process.env.BASE_PATH || "/";
if (
  !basePath ||
  basePath === "/" ||
  basePath.includes("Program Files") ||
  /^[A-Za-z]:/.test(basePath) ||
  !basePath.startsWith("/")
) {
  basePath = "/";
}

const buildId =
  process.env.AURORA_UI_BUILD ||
  `chatgpt-${new Date().toISOString().replace(/[:.]/g, "").slice(0, 15)}`;

const env = {
  ...process.env,
  CI: process.env.CI || "true",
  NODE_ENV: "production",
  PORT: process.env.PORT || "22333",
  BASE_PATH: basePath,
  AURORA_UI_BUILD: buildId,
  MSYS2_ARG_CONV_EXCL: "*",
};

execSync("pnpm --filter @workspace/web run build", {
  cwd: ROOT,
  env,
  stdio: "inherit",
});

const indexPath = path.join(PUBLIC, "index.html");
if (!fs.existsSync(indexPath)) fail(`missing ${indexPath}`);

fs.writeFileSync(path.join(PUBLIC, "aurora-ui-build.txt"), `${buildId}\n`);

let html = fs.readFileSync(indexPath, "utf8");
if (!html.includes('name="aurora-ui-build"')) {
  html = html.replace(
    "</head>",
    `  <meta name="aurora-ui-build" content="${buildId}" />\n  </head>`,
  );
  fs.writeFileSync(indexPath, html);
}
if (html.includes("Program Files")) {
  fail("index.html has corrupted BASE_PATH (MSYS path rewrite)");
}

const assetsDir = path.join(PUBLIC, "assets");
const jsBundle = fs
  .readdirSync(assetsDir)
  .filter((f) => /^index-.*\.js$/.test(f))
  .map((f) => path.join(assetsDir, f))[0];
if (!jsBundle) fail("no assets/index-*.js produced");

const bundle = fs.readFileSync(jsBundle, "utf8");
for (const s of ["Analisar uma partida", "Aurora — Inteligência Esportiva"]) {
  if (bundle.includes(s)) fail(`forbidden legacy UI string in bundle: ${s}`);
}
for (const s of [
  "Personalizar avatar",
  "Renomear conversa",
  "Como posso ajudar nas análises de hoje",
]) {
  if (!bundle.includes(s)) fail(`required new UI string missing: ${s}`);
}

console.log("OK served index:", indexPath);
console.log("OK bundle:", jsBundle);
console.log("OK aurora-ui-build:", buildId);
console.log("OK verified ChatGPT-style UI; legacy empty-state absent");
