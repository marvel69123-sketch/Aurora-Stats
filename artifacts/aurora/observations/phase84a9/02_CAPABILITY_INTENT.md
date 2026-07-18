# 8.4-A.9 — Capability Intent

## New intent

`assistant_capabilities` (MasterIntent: `CAPABILITIES_QUERY`)

## Module

`src/conversation/assistant_capabilities.py`

- `is_capabilities_ask` / `capability_source_phrase`
- `build_capabilities_reply` / `build_capabilities_payload`
- Audit stamps: `capability_intent_detected`, `capability_source_phrase`

## Wiring

| Layer | Change |
|-------|--------|
| `master_intent_router` | Classify capabilities **before** SYSTEM / short-general |
| `general_assistant` | `CAPABILITIES_QUERY` (+ leak guards) → capabilities payload |
| Router `_run_capabilities` | Reuses shared payload; accepts `capabilities` alias |
| NRE / Personality / Credibility | Skip rewrite of capabilities turns |

## Triggers (examples)

o que você faz · o que sabe fazer · suas funcionalidades · aurora funcionalidades ·
como você funciona · como pode me ajudar · o que consegue analisar · recursos ·
para que serve a Aurora · o que é capaz de fazer
