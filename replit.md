# Aurora

Aurora is a Python FastAPI service that proxies API-Football and returns live football match statistics — fixtures, events, lineups, standings, player stats, and more.

## Run & Operate

- `cd artifacts/aurora && uvicorn src.main:app --host 0.0.0.0 --port 8000` — run Aurora locally
- `pnpm --filter @workspace/api-server run dev` — run the Node.js API server (port 8080)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- Required env: `API_FOOTBALL_KEY` — API-Football API key
- Required env: `DATABASE_URL` — Postgres connection string (Node API server)

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

- `artifacts/aurora/` — Python FastAPI service (Aurora)
  - `src/main.py` — FastAPI app entry point, docs at `/aurora/docs`
  - `src/client.py` — httpx wrapper for API-Football requests
  - `src/routers/copilot_unified_router.py` — main chat endpoint (`POST /aurora/copilot`)
  - `src/routers/fixtures.py` — fixture endpoints (live, stats, events, lineups, players)
  - `src/routers/leagues.py` — league search/lookup
  - `src/routers/teams.py` — team search, lookup, and statistics
  - `src/routers/players.py` — player stats, top scorers, top assists
  - `src/routers/standings.py` — league standings table
  - `src/core/conversation_llm.py` — OpenAI layer (enhance + chat + needs_llm LLM router)
  - `src/core/conversation_engine.py` — rule-based emotional/educational responses
  - `src/core/follow_up_engine.py` — follow-up resolution (14 types)
  - `src/core/live_intelligence_engine.py` — live match opportunity scoring
  - `src/core/nl_router.py` — natural language intent router
  - `src/chat_db.py` — SQLite session + message + context persistence
- `artifacts/api-server/` — Node.js/Express API (base scaffold)
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
- The shared reverse proxy routes `/aurora/*` to port 8000, alongside the Node API on `/api/*` (port 8080). Both are declared in `artifacts/api-server/.replit-artifact/artifact.toml` as separate `[[services]]` entries.
- FastAPI docs (`/aurora/docs`, `/aurora/redoc`) are mounted under the `/aurora` prefix so they work correctly through the proxy.
- All API-Football calls go through `src/client.py` which reads `API_FOOTBALL_KEY` from environment and raises HTTP errors on failure.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- The proxy does NOT rewrite paths — Aurora must handle full `/aurora/...` prefixes itself (FastAPI `prefix=` on routers handles this).
- `API_FOOTBALL_KEY` must be set as a Replit secret.
- API-Football free tier has rate limits — responses are not cached; add caching if needed.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
