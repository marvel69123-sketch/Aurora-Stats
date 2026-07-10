---
name: Aurora Copilot Architecture
description: Key decisions and gotchas for the Aurora conversational copilot endpoint
---

# Aurora Copilot Architecture

## Routing priority in copilot()
Three-tier dispatch (in order):
1. **Emotional** — fires when `intent == "unknown"` AND `conversation_engine.detect()` confidence ≥ 0.80
2. **Follow-up** — fires when `intent == "unknown"` AND `ctx.last_match` is set AND `follow_up_engine.is_followup()` is True
3. **Normal NL routing** — all other intents via nl_router

**Why:** This order prevents the NL router from swallowing emotional/follow-up messages that look like "unknown" to the keyword router.

## Live fixtures key fix
`_run_live()` uses `live.get("matches", [])` NOT `"live_matches"` — the processed format from `live.py::_build_live_response` uses `"matches"` as the top-level key.

**Why:** The raw API-Football key `"live_matches"` was used in the old placeholder; `_build_live_response` normalises it to `"matches"`.

## live_intelligence_engine processed format
`score_fixture(fx)` expects the processed format from `_build_live_response`:
- `fx["fixture_id"]`, `fx["status"]["minute"]`, `fx["league"]["name"]`
- `fx["home"]["name"]`, `fx["home"]["score"]`, `fx["away"]["name"]`, `fx["away"]["score"]`
NOT raw API-Football format with `fx["teams"]["home"]["name"]`.

## Session_id persistence
- Backend: `session_id = body.session_id or secrets.token_hex(8)` — always returned in response
- Frontend: `useChat.ts` reads `session.backendSessionId`, passes as `session_id` in body, stores `response.session_id` as `backendSessionId` on the session object (persisted to localStorage)

## context_json migration
`chat_db.py::_migrate_add_context_columns()` safely adds `context_json TEXT DEFAULT '{}'` via `PRAGMA table_info` check — no failure on existing DBs.

## ConversationContext shape stored in context_json
```json
{
  "last_match": "Home x Away",
  "last_home": "Home",
  "last_away": "Away",
  "last_intent": "analyze_match",
  "last_analysis": { /* full payload minus brain/aurora_version */ },
  "user_profile": { "experience_level": null, "risk_preference": null, "bankroll": null, "preferred_markets": [] }
}
```
