# 8.4-A.9 — Root Cause

## Symptom

Questions like “o que você faz?”, “suas funcionalidades”, “o que sabe fazer?”
fell into `GENERAL_CHAT` / weak `SYSTEM_QUERY→identity` and returned the sticky
GeneralAssistant loop:

> Entendi. Posso te ajudar com isso de forma direta…

## Why

1. **MasterIntent `_SYSTEM`** only partially covered capability phrases.
   Misses: `suas funcionalidades`, `o que sabe fazer`, `como você funciona`,
   `aurora funcionalidades`, bare `funcionalidades` / `recursos`.
2. Short non-sport (≤6 tokens) defaulted to **`GENERAL_CHAT`** → `reply_general`.
3. Even when SYSTEM matched (“o que você faz”), GA mapped **all** `SYSTEM_QUERY`
   to `intent=identity` with a thin `reply_system` bullet list — not a dedicated
   capabilities intent.
4. After `oi` + identity, **Credibility SOCIAL** could force `intent=small_talk`
   even when the capabilities body was already correct.

## Not the cause

Opinion renderer, follow-up engine, calendar, partial analysis, market engine —
out of scope and unchanged in behavior for sport turns.
