# RESTORE_STATUS — 2026-07-20

## Commit pushed

- **HEAD / `origin/main`:** `0c52710` (`0c52710c1baa28926f9e3617d9de22ded1175091`)
- **Message:** `fix(aurora): unwrap FastAPI Query defaults in analyze_fixture`
- Confirmed aligned: local `main` tracks `origin/main` at the same SHA.

## Republish

**Republish must be done in the Replit UI** (Autoscale). Local `pnpm run deploy` only runs layout verify / build prep; it does not publish the Autoscale deployment. After GitHub has `0c52710`, use Replit → Deploy / Republish so prod picks up that commit.

## Local deploy prep (`pnpm run deploy`)

- **Exit code:** `1`
- **Stopped at:** layout verify (`scripts/verify-layout.sh`)
- **Error:** `DIVERGE: aurora/src/core/nl_router.py != artifacts/aurora/src/core/nl_router.py` (suggested unblocker: `bash scripts/sync-aurora-mirror.sh`)
- No further build/deploy steps were attempted after layout failure.

## Current prod probe (quick curl, 2026-07-20)

| Host | Result |
|------|--------|
| `https://aurora-stats.marvel69123-sketch.replit.app/aurora/healthz` | **TLS fail** — `curl: (35) schannel: failed to receive handshake` (`http_code=000`) |
| `https://aurora-stats-marvel69123-sketch.replit.app/aurora/healthz` | **404** — "This app isn't live yet" |
| `https://marvel69123-sketch-aurora-stats.replit.app/aurora/healthz` | **404** — "This app isn't live yet" |

**Prod status:** unhealthy / not live from this machine — no readable `backend_commit` from `/aurora/healthz`.
