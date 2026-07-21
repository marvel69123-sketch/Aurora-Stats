# SPORT-INTENT-HIJACK-FIX-001

## Root cause

`_skill_compare_strength` reused CSL teams whenever the message lacked `teams[0]` or contained `x`/`vs`/`ou`. With CSL still holding Flamengo×Palmeiras, `Liverpool x Chelsea` was rewritten to `Entre Flamengo e Palmeiras…` / `analisar Flamengo x Palmeiras…`.

## Fix (always-on safety inside sport intent)

File: `artifacts/aurora/src/conversation/sport_intent_layer.py` only.

- Detect explicit message fixture sides (`A x|vs|ou B`).
- On detection: refresh `csl.teams`/`csl.fixture` via CSL get/set, stamp `ignore_previous_fixture` / `sport_intent_new_fixture` / `force_refresh_entities`, update cheap `last_match`/`last_fixture` refs.
- Skills prefer message-derived sides; `_skill_compare_strength` returns `None` when the message already names both sides (no CSL rewrite).
- Bare follow-ups without sides keep normal CSL continuity (`Quem está melhor?` → Entre Flamengo e Palmeiras…).
- Soft single-entity lines (`E o Grêmio?`) are not treated as new fixtures.

## Flag

No new flag. Respects existing `ENABLE_SPORT_INTENTS` (default ON; `0`/`false`/`off` = no-op).

## Tests

`artifacts/aurora/tests/test_sport_intent_hijack_fix_001.py`

1. Flamengo CSL + `Liverpool x Chelsea` → Liverpool/Chelsea; FU uses refreshed CSL.
2. Flamengo CSL + `Quem está melhor?` → continuity preserved.
3. Inter CSL + `E o Grêmio?` → no wipe / no Flamengo hijack.
4. Unit coverage for `_skill_compare_strength` + flag disabled no-op.
