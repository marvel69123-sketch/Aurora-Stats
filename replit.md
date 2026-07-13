# Aurora

Aurora is a Python FastAPI service that proxies API-Football and returns live football match statistics — fixtures, events, lineups, standings, player stats, and more.

## Live analysis (critical)

If `status.short` ∈ `1H | 2H | HT | ET | BT | P | SUSP | INT | LIVE` → `is_live=True`.
Never emit "análise pré-jogo" for live fixtures. See `AURORA_ARCHITECTURE.md` and `AURORA_AUDIT_REPORT.md`.

Canonical helpers: `src/core/fixture_status.py`.
Deploy tree: `artifacts/aurora/` (must stay in sync with `aurora/` for live fixes).

## Run & Operate


- `cd artifacts/aurora && uvicorn main:app --host 0.0.0.0 --port 8080` — run Aurora (deploy path)
- `bash scripts/verify-layout.sh` — fail-fast if monorepo layout is broken
- `pnpm --filter @workspace/web run dev` — frontend Vite
- `pnpm --filter @workspace/api-server run dev` — Node.js API scaffold
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- Required env: `API_FOOTBALL_KEY` — API-Football API key
- Required env: `DATABASE_URL` — Postgres (Node API server only)

## Stack

- **Aurora**: Python 3.12, FastAPI, uvicorn, httpx, openai
- **LLM**: OpenAI `gpt-5.4-mini` via Replit AI Integrations (no API key required)
- **API Server**: Node.js 24, TypeScript 5.9, Express 5
- DB: SQLite (Aurora chat history + session context); PostgreSQL + Drizzle ORM (Node API server)
- pnpm workspaces monorepo

## Conversational AI Architecture

```
User message
    ↓
Aurora NL Router (intent detection)
    ↓
Aurora Engines (calculations, stats, bankroll, live scoring)
    ↓                              ↓
Structured payload          LLM Router: needs_llm()?
(numbers untouched)              YES → OpenAI gpt-5.4-mini
                                  NO  → Template response
    ↓
Final response (narrative enhanced, numbers preserved)
```

**LLM fires for:** follow-up, emotional, beginner, confused, unknown, user profile  
**LLM never fires for:** analyze_match, live_opportunities, bankroll_review, learning_recap, knowledge_search

## Where things live

- `artifacts/aurora/` — Python FastAPI service (Aurora) — **source of truth**
  - `main.py` / `start.sh` — production entry (`uvicorn main:app` :8080)
  - `src/main.py` — FastAPI app, docs at `/aurora/docs`
  - `src/client.py` — httpx wrapper for API-Football requests
  - `src/routers/copilot_unified_router.py` — main chat endpoint (`POST /aurora/copilot`)
  - `src/routers/analyze.py` — fixture resolver (fuzzy / accents / apostrophes)
  - `src/core/nl_router.py` — intent router (`EARLY_OVERRIDE`: two teams → `analyze_match`)
  - `src/core/fixture_status.py` — live status canonical set
  - `src/core/live_intelligence_engine.py` — live opportunity scoring
- `artifacts/web/` — React/Vite frontend (`@workspace/web`)
- `artifacts/api-server/` — Node scaffold; Replit artifact.toml wires Aurora Python
- `aurora/` — optional local mirror (`bash scripts/sync-aurora-mirror.sh`)
- `lib/api-spec/openapi.yaml` — OpenAPI contract for Node API

## API Endpoints

All Aurora endpoints are prefixed `/aurora/`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/aurora/healthz` | Health check |
| GET | `/aurora/docs` | Interactive Swagger UI |
| GET | `/aurora/fixtures/live` | All currently live matches |
| GET | `/aurora/fixtures/` | Query fixtures (league, season, date, team, status) |
| GET | `/aurora/fixtures/{id}/statistics` | Match statistics |
| GET | `/aurora/fixtures/{id}/events` | Goals, cards, substitutions |
| GET | `/aurora/fixtures/{id}/lineups` | Team lineups |
| GET | `/aurora/fixtures/{id}/players` | Player ratings for a match |
| GET | `/aurora/leagues/` | Search/list leagues |
| GET | `/aurora/leagues/{id}` | Get a specific league |
| GET | `/aurora/teams/` | Search/list teams |
| GET | `/aurora/teams/{id}` | Get a specific team |
| GET | `/aurora/teams/{id}/statistics` | Team stats for a season |
| GET | `/aurora/players/` | Player statistics |
| GET | `/aurora/players/top-scorers` | Top scorers in a league |
| GET | `/aurora/players/top-assists` | Top assist providers |
| GET | `/aurora/players/{id}` | Specific player stats |
| GET | `/aurora/standings/` | League table/standings |

## Architecture decisions

- Aurora lives in `artifacts/aurora/` as a pure Python package — no pnpm/Node involvement.
- The shared reverse proxy routes `/aurora/*` to port **8080** (Aurora FastAPI; declared in `artifacts/api-server/.replit-artifact/artifact.toml`, code in `artifacts/aurora/`). Static web serves `/` from `artifacts/web`.
- FastAPI docs (`/aurora/docs`, `/aurora/redoc`) are mounted under the `/aurora` prefix so they work correctly through the proxy.
- All API-Football calls go through `src/client.py` which reads `API_FOOTBALL_KEY` from environment and raises HTTP errors on failure.
- Two named teams with `x/vs` always route to `analyze_match`, never `live_opportunities` (`EARLY_OVERRIDE` in `nl_router`).

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- The proxy does NOT rewrite paths — Aurora must handle full `/aurora/...` prefixes itself (FastAPI `prefix=` on routers handles this).
- `API_FOOTBALL_KEY` must be set as a Replit secret.
- API-Football free tier has rate limits — responses are not cached; add caching if needed.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
