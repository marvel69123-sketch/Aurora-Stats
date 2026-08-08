# MISSION 050 — Router Follow-up Parity

**MISSION:** 050 — Router Follow-up Parity (bare market chips)  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CODE SoT:** `artifacts/aurora/`  
**PRIOR:** Mission 049 RCA (`observations/aurora_pilot_observation_049/`)

```text
STATUS ..................... FIXED (parity + sticky sport exception)
ROLLOUT % CHANGED .......... NO
PGR / ACTIVATION FLAGS ..... NOT MODIFIED
CM MODULES EDITED .......... NO
EM MODULES EDITED .......... NO
COMMIT / PUSH .............. NO
DEPLOY MIRROR aurora/ ...... NOT SYNCED (SoT-only this mission)
```

---

## Executive verdict

Bare market replies (`gols`, `cartões`/`cartoes`, `BTTS`/`ambas`, `over`, `under`, plus existing `escanteios`) now share the **same short-FU / continuity acceptance path** as `escanteios`. After fixture/market-prompt sticky context, MasterIntent classifies them as **SPORT_QUERY** (`sticky_market_chip`) instead of **GENERAL_CHAT** / `short_general`, so the sport pipeline and QuickFollowUpGate can run.

---

## What changed

### Shared token helper (new)

`artifacts/aurora/src/conversation/market_short_followup.py`

- Shared `MARKET_TOKEN_ALT` / `BARE_MARKET_FOLLOWUP`
- `is_bare_market_followup()`, `bare_market_kind()`, `has_sport_sticky_context()`

### Detector parity

| Module | Change |
|--------|--------|
| `core/follow_up_engine.py` | Bare chips: `gols`, `golos`, `cartoes`, `btts`, `ambas marcam`, `over`, `under` (+ keep `escanteios`) |
| `sport_continuity_guard.py` | `_SHORT_FU` + early `is_bare_market_followup` |
| `ownership_stability.py` | `_CONTINUITY_FU` + early bare-market check |
| `sport_intent_layer.py` | MARKET_QUESTION accepts bare `\bgols?\b`, `\bover\b`, `\bunder\b` |
| `conversation_continuity.py` | Market kinds in `SPORT_FOLLOWUP_KINDS` / `_is_short_followup` + FU bridge + contextual reply |
| `master_intent_router.py` | Sticky exception: bare market + sport sticky ctx → `SPORT_QUERY` / `allow_sport_pipeline=True` |

Cold-start bare `gols` (no sticky fixture/anchor) still falls through to `short_general` — intentional.

---

## Files touched

```text
artifacts/aurora/src/conversation/market_short_followup.py          (NEW)
artifacts/aurora/src/conversation/master_intent_router.py
artifacts/aurora/src/conversation/sport_continuity_guard.py
artifacts/aurora/src/conversation/ownership_stability.py
artifacts/aurora/src/conversation/sport_intent_layer.py
artifacts/aurora/src/conversation/conversation_continuity.py
artifacts/aurora/src/core/follow_up_engine.py
artifacts/aurora/tests/test_router_followup_parity_050.py           (NEW)
observations/aurora_router_followup_parity_050/REPORT.md            (this file)
```

**Not touched:** Context Manager architecture, Execution Manager, `progressive_gate_review.py` / PGR env defaults, rollout %.

---

## Test results

```text
pytest artifacts/aurora/tests/test_router_followup_parity_050.py \
       artifacts/aurora/tests/test_conversation_5b.py \
       artifacts/aurora/tests/test_sport_intent_layer_intent001.py \
       artifacts/aurora/tests/test_master_intent_p0.py \
       -k "not test_mixed_50_zero_contamination"
→ 33 passed, 1 deselected
```

Mission 050 suite (`test_router_followup_parity_050.py`): **7 passed** covering:

- shared detector parity (`gols` ≈ `escanteios`, cartões, BTTS, over, under)
- `follow_up_engine` bare chips
- SCG / ownership short-FU
- sport_intent MARKET_QUESTION
- continuity kinds
- MasterIntent sticky ≠ `short_general`
- post-market-prompt sport path parity

**Note:** `test_mixed_50_zero_contamination` fails independently — GA capabilities reply contains the substring `mercado` matched by `SPORT_LEAK`. Not introduced by this mission (no capabilities/PGR edits).

---

## Confirmation — constraints

| Constraint | Status |
|------------|--------|
| CM architecture / modules | **Untouched** |
| Execution Manager | **Untouched** |
| Rollout % / PGR flags / activation env defaults | **Untouched** |
| Commit / push | **Not done** |
| Focus Router + Conversational short-FU | **Yes** |

---

## Residual risks

1. Bare `over`/`under` as global FU patterns may fire inside longer sports questions that end with those tokens — mitigated by `\s*$` / short-message gates in most detectors.
2. Sticky MasterIntent depends on session memory (`last_match`, SCG anchor, continuity, CSL, …). If a deploy clears those before the chip turn, classification falls back to `short_general` (SCG/FU detectors still help when anchor exists).
3. Deploy mirror `aurora/` not synced — ops must deploy from `artifacts/aurora/` or sync intentionally.
4. Full end-to-end copilot path for empty `last_analysis` still uses continuity prose rather than numeric markets (by design — no invented odds).

```text
MISSION 050 .................... COMPLETE
FIX APPLIED .................... YES
% CHANGE ....................... NO
CM/EM IMPLICATED ............... NO
```
