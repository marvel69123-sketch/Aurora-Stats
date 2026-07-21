# AURORA-INTENT-001 — Semantic Sports Intent Layer

**TYPE:** IMPLEMENTATION  
**PRIORITY:** P0  
**MODE:** Additive façade — **no engine modifications**

Inspired by Rasa dialogue policies (intent → action/skill) and Athena topic response generators.

---

## Architecture

```text
User → SLL → CSL → Sport Intent Layer (NEW) → existing router / skills sinks
                                      │
                                      ├─ classify explicit intent
                                      ├─ map intent → skill id
                                      └─ optional message rewrite (skill shaping)
```

### Explicit intents

| Intent | Skill | Typical cues |
|--------|-------|--------------|
| `compare_strength` | `skill_compare_strength` | ou/x/vs, quem ganha, mais forte |
| `bet_viability` | `skill_bet_viability` | vale a pena, aposta, kelly, edge |
| `calendar_query` | `skill_calendar_query` | quando joga, agenda, amanhã |
| `home_away_analysis` | `skill_home_away` | mando de campo, em casa / fora |
| `recent_form` | `skill_recent_form` | fase, forma, quem está melhor |
| `market_question` | `skill_market_question` | gols, escanteios, over/under, mercados |

Skills **reshape / contextualize** messages using CSL slots (teams/fixture). They do not invent odds, xG, or replace methodology/market/confidence engines.

Short market follow-ups (`e os gols?`) are **not** rewritten so `follow_up_engine` remains the sink.

---

## Feature flag

- `ENABLE_SPORT_INTENTS=1` (default) — on  
- `ENABLE_SPORT_INTENTS=0` — rollback / no-op  

---

## Files

| File | Change |
|------|--------|
| `src/conversation/sport_intent_layer.py` | **NEW** classifier + skills |
| `src/routers/copilot_unified_router.py` | Wire after CSL; stamp entities |
| `tests/test_sport_intent_layer_intent001.py` | **NEW** |
| `observations/intent_001/*` | Docs + smoke |

**Untouched:** methodology / market / confidence / intelligence / learning engines, ownership & continuity guards, SLL, CSL module internals, entity_safety.

---

## Injection points

1. After `apply_csl_resolve` → `message = apply_sport_intent_resolve(message, ctx)`  
2. End-of-turn → `note_sport_intent_on_payload(ctx, payload)` stamps `sport_intent`, `sport_skill`, `sport_intent_confidence`

---

## Validation

- **29** unit tests passed (intent + CSL + SLL suites)  
- Smoke:  
  - `Flamengo ou Palmeiras?` → `compare_strength`  
  - `Quem está melhor?` → `recent_form` + teams from CSL  
  - `e o mando de campo?` → `home_away_analysis`

---

## Rollback

```powershell
$env:ENABLE_SPORT_INTENTS = "0"
```
