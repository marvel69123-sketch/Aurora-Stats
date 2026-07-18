# 8.4-A.10 — Root Cause

## Symptom (AEP v1)

```
Argentina x Brasil
↓
e dele?
↓
FAIL — fixture_reused_expected_True_got_False; loop_detected
intent=general_chat
```

Sticky GA loop: “Entendi. Posso te ajudar com isso de forma direta…”

## Why

1. **Short sport continuity (8.4-A.8)** only claims kinds like `mercados?` / `placar?` — not bare pronouns (`e dele?`, `e o outro?`).
2. **Short memory pronoun rewrite (8.2-C)** requires `last_team`, but after `Argentina x Brasil` the payload has `home`/`away` while `match` is a **string** — `_extract_team_from_payload` never persisted `last_team`.
3. MasterIntent/GA then classified the short pronoun as `general_chat` **before** any layer reused `ctx.last_match` (`Argentina vs Brazil`).

## Evidence

- Prior turn: `analyze_match` + `PARTIAL` + `preliminary_analysis` + `last_match` populated.
- Pronoun turn: no `followup_context_found`, no continuity claim, GA lock.

## Fix direction

New **Pronoun Continuity Layer** before GA/fallback: detect short pronouns → bind last fixture/team/entity (or INVALID) → claim payload with audit fields.
