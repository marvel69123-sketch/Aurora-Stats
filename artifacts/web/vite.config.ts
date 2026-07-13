import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import fs from "fs";
import runtimeErrorOverlay from "@replit/vite-plugin-runtime-error-modal";

// Defaults so `pnpm build` works from workspace root without Replit service env.
const rawPort = process.env.PORT || "22333";
const port = Number(rawPort);
if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

const basePathRaw = process.env.BASE_PATH || "/";
// Guard: Git Bash/MSYS rewrites "/" → "C:/Program Files/Git/" on Windows.
const basePath =
  !basePathRaw ||
  basePathRaw.includes("Program Files") ||
  /^[A-Za-z]:/.test(basePathRaw) ||
  !basePathRaw.startsWith("/")
    ? "/"
    : basePathRaw.endsWith("/")
      ? basePathRaw
      : `${basePathRaw}/`;
const auroraUiBuild =
  process.env.AURORA_UI_BUILD ||
  `chatgpt-${new Date().toISOString().replace(/[:.]/g, "").slice(0, 15)}`;

// Workspace root = artifacts/web/../..
const workspaceRoot = path.resolve(import.meta.dirname, "..", "..");
const attachedAssets = path.resolve(workspaceRoot, "attached_assets");
if (!fs.existsSync(attachedAssets)) {
  fs.mkdirSync(attachedAssets, { recursive: true });
}

export default defineConfig({
  base: basePath,
  define: {
    __AURORA_UI_BUILD__: JSON.stringify(auroraUiBuild),
  },
  plugins: [
    react(),
    tailwindcss(),
    runtimeErrorOverlay(),
    ...(process.env.NODE_ENV !== "production" &&
    process.env.REPL_ID !== undefined
      ? [
          await import("@replit/vite-plugin-cartographer").then((m) =>
            m.cartographer({
              // Point at workspace artifacts/ parent (Replit cartographer root)
              root: path.resolve(import.meta.dirname, ".."),
            }),
          ),
          await import("@replit/vite-plugin-dev-banner").then((m) =>
            m.devBanner(),
          ),
        ]
      : []),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src"),
      "@assets": attachedAssets,
    },
    dedupe: ["react", "react-dom"],
  },
  // Keep app root inside artifacts/web — never the monorepo root
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: path.resolve(import.meta.dirname, "dist/public"),
    emptyOutDir: true,
  },
  server: {
    port,
    strictPort: true,
    host: "0.0.0.0",
    allowedHosts: true,
    fs: {
      strict: true,
      allow: [workspaceRoot],
    },
  },
  preview: {
    port,
    host: "0.0.0.0",
    allowedHosts: true,
  },
});
