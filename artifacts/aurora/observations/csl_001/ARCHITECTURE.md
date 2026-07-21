# AURORA-CSL-001 — Conversation State Layer

**TYPE:** IMPLEMENTATION  
**PRIORITY:** P0  
**MODE:** Façade only — no engine / routing / FROZEN rewrites

---

## 1. Architecture

```text
User message
    │
    ▼
 Sports Language Layer (SLL)     ← UNTOUCHED
    │  normalized_text, clubs[]
    ▼
 Conversation State Layer (CSL)  ← NEW façade
    │  slots + optional follow-up inject
    ▼
 Aurora Router / existing path   ← UNTOUCHED logic
    │
    ▼
 Engines (FROZEN) + guards (FROZEN)
    │
    ▼
 CSL note_after_response         ← update slots from payload/ctx
```

### Responsibilities
1. Store explicit sports conversation state on `ctx["csl"]`
2. Track: teams, fixture, topic, last_intent, phase, date_context, episode_id
3. Contextualize bare follow-ups using prior teams (message rewrite only)
4. Stamp `entities.csl` contract for observability — **never** replace Aurora reasoning

### State contract
```json
{
  "teams": ["Flamengo", "Palmeiras"],
  "topic": "comparison",
  "last_intent": "fixture_compare",
  "date_context": null,
  "episode_id": "uuid",
  "fixture": "Flamengo x Palmeiras",
  "phase": "SLOT_READY"
}
```

### Follow-up inject
| Prior state | User | Injected message |
|-------------|------|------------------|
| teams=[Flamengo, Palmeiras] | `Quem está melhor?` | `Entre Flamengo e Palmeiras, quem está melhor?` |

### Feature flag
- `ENABLE_CSL=1` (default) — on  
- `ENABLE_CSL=0` — rollback / no-op  

### Non-goals / forbidden
- No edits to methodology / market / confidence / intelligence / learning engines  
- No ownership / continuity / ambiguous / fiction guard edits  
- No SLL / entity_safety / sport_referent_frame edits  
- No MasterIntent / NL router rewrites  

---

## 2. Files modified / added

| File | Role |
|------|------|
| `src/conversation/conversation_state_layer.py` | **NEW** CSL façade |
| `src/routers/copilot_unified_router.py` | Wire `apply_csl_resolve` after SLL; `note_csl_after_response` at end-of-turn |
| `tests/test_conversation_state_layer_csl001.py` | **NEW** unit tests |
| `observations/csl_001/*` | Architecture, regression, smoke |

---

## 3. Injection points

1. **Turn start** — immediately after SLL, before short_memory / MasterIntent:
   `message = apply_csl_resolve(message, ctx)`
2. **Turn end** — with other note_* helpers (after fiction note, skip on hard reset):
   `payload = note_csl_after_response(ctx, message, payload)`

---

## 4. Tests

```text
tests/test_conversation_state_layer_csl001.py
+ SLL / entity-safety / sports_language suites
→ 38 passed
```

Covers: flag off, contract shape, follow-up inject, two-turn Mengão→melhor, no inject without teams, no inject on new compare, payload stamp.

---

## 5. Regression report (EVAL-001, 110q)

| Metric | Post-SLL (002A) | Post-CSL (001) | Δ |
|--------|-----------------|----------------|---|
| Success | 91.8% | **91.8%** | 0 |
| SPORT_REASONING | 3 | **2** | −1 |
| ENTITY_CORRUPTION | 3 | **2** | −1 |
| OWNER_LOCK | 3 | 5 | +2 |
| **HPS** | 83.7 | **83.7** | 0 |

**Verdict:** No success-rate regression. Reasoning/entity slightly better; owner-lock up on a few sticky sessions (out of CSL scope — FROZEN guards). Smoke two-turn compare→follow-up: CSL slots persist; phase=`FOLLOWUP`.

---

## 6. Rollback

```powershell
$env:ENABLE_CSL = "0"
# equivalents: false | off | no
```

With flag off, `apply_csl_resolve` returns the message unchanged (`skipped_reason=flag_disabled`). No code revert required for emergency disable.
