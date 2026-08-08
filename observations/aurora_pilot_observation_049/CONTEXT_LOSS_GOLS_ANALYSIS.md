# CONTEXT LOSS — bare `"gols"` after market prompt

**Mission:** 049  
**Evidence:** `aurora_audit_20260807_231646.json` (session `svz4xoza` / backend `9678179574c639af`)  
**SoT:** `artifacts/aurora/`  
**Probe date:** 2026-08-07 (local classification via `.venv`)

---

## 1. Symptom

After Aurora asked the user to choose a market slice (`diga gols, escanteios, cartões ou BTTS`), the user answered **`gols`**. Aurora replied with a generic soft template and dropped the fixture thread for that turn:

> Pode falar comigo normalmente em que posso ajudar?

Immediate recovery on the next turn with **`mercado de gols`** (fixture context restored via ownership soft-hold).

---

## 2. Classification matrix (reproduced locally)

| Message | MasterIntent | sport_ok | sport_intent | follow_up_engine | continuity `_is_short_followup` | SCG `is_sport_short_followup` | MI `_FOLLOW_MARKET_ONLY` |
|---------|--------------|----------|--------------|------------------|--------------------------------|------------------------------|--------------------------|
| `gols` | **GENERAL_CHAT** `short_general` | **False** | None | **None** | None | **False** | **True** |
| `e gols` | GENERAL_CHAT `short_general` | False | market_question | goals_market | None | False | True |
| `escanteios` | GENERAL_CHAT `short_general` | False | market_question | corners_market | None | **True** | True |
| `mercado de gols` | **SPORT_QUERY** | **True** | market_question | goals_market | None | True | False |
| `qual melhor mercado?` | SPORT_QUERY | True | market_question | None | None | False | False |

**Asymmetry smoking gun:** bare `escanteios` is recognized by SCG + follow_up_engine; bare `gols` is not. Only `message_intelligence._FOLLOW_MARKET_ONLY` treats bare `gols` as a market follow-up — but that path is moot once MasterIntent hard-blocks the sport pipeline.

---

## 3. Failure chain (order of operations)

```text
User: "gols"
  → ResponseSelector / Continuity early claim: MISS
       (_is_short_followup has no goals kind; is_active_sport_followup=False)
  → SportIntent skill: MISS (MARKET_QUESTION regex has bare escanteios/cartões/mercados,
       but gols only as "e (os )?gols?")
  → SCG short-FU detector: MISS (_SHORT_FU lists escanteios, not gols)
  → OwnershipStability _CONTINUITY_FU: MISS (no gols token)
  → MasterIntent: GENERAL_CHAT / short_general → allow_sport_pipeline=False
       → hard_clear_sport_context (turn block; session last_match kept)
  → QuickFollowUpGate: never entered (is_followup("gols")=False)
  → GeneralAssistant / NRF soft fallback
       → "Pode falar comigo normalmente … em que posso ajudar?"
```

Recovery turn:

```text
User: "mercado de gols"
  → MasterIntent: SPORT_QUERY (token "mercado" in _SPORT)
  → Ownership soft-hold / continuity path
       → "Continuando sobre **Gremio x Sao Paulo**…"
```

---

## 4. Code evidence (quotes)

### MasterIntent — bare short non-sport → GENERAL_CHAT

`artifacts/aurora/src/conversation/master_intent_router.py`:

- `_SPORT` includes `mercado` / `odds` / analyze / fixtures — **not** `gols`.
- Short messages without `x` fall through:

```text
# Short non-sport → general (never invent teams)
if len(folded.split()) <= 6 and not re.search(r"\bx\b", folded):
    return MasterIntentResult("GENERAL_CHAT", 0.75, "short_general", False)
```

### follow_up_engine — goals require `"e … gols"`; corners allow bare token

`artifacts/aurora/src/core/follow_up_engine.py`:

```text
(r"escanteios?\s*$",                             "corners_market"),
(r"e\s+(?:os\s+)?gols?",                         "goals_market"),
# Phase 8.4-A.8 bare shorts: mercados/placar/… — NO bare gols
```

### sport_intent MARKET_QUESTION — same asymmetry

`artifacts/aurora/src/conversation/sport_intent_layer.py`:

```text
\bescanteios?\b|…|\bmercados?\b|
e\s+(?:os\s+)?(?:gols?|escanteios?|…)   # gols only with leading "e "
```

### SCG short-FU — escanteios present, gols absent

`artifacts/aurora/src/conversation/sport_continuity_guard.py` `_SHORT_FU`.

### Soft reply source

`natural_response_filter.py` / `intelligence_fallback.py`:

```text
"Pode falar comigo normalmente — em que posso ajudar?"
```

(Audit export may normalize the em-dash; semantic match is exact.)

### Prior markets turn — ResponseSelector skill

Assistant text matches `response_selector._author_skill_text` for `market_question`:

```text
Mercados no confronto **{label}**.
Ainda sem lista numérica fechada neste turno — diga gols, escanteios, cartões ou BTTS…
```

So the product **solicited** the token `gols`, then failed to accept it as the answer.

---

## 5. What did NOT cause this

| Hypothesis | Verdict |
|------------|---------|
| Topic Boundary V2 orphan clear / NEW_EPISODE | Unlikely — next turn still had Gremio x Sao Paulo |
| Sole-writer funnel / CM PGR | Not required; reproduces with default-OFF classification |
| EM shadow/live | Not on this path |
| Fixture wipe | Session fixture survived (`mercado de gols` recovery) |

---

## 6. Fix sketch (engineering ticket — DO NOT apply in 049)

Minimal, high-leverage (observe-only mission — no patch here):

1. Add bare `gols?` / `golos?` to:
   - `follow_up_engine._FOLLOWUP_PATTERNS` (parity with `escanteios?\s*$`)
   - `sport_intent` MARKET_QUESTION (bare `\bgols?\b`)
   - `sport_continuity_guard._SHORT_FU` and preferably `ownership_stability._CONTINUITY_FU`
   - `master_intent._SPORT` **or** sticky-context exception: if `last_match`/sport anchor active and message is pure market token → keep `SPORT_QUERY`
2. Regression tests: after markets prompt / partial analysis, bare `gols` | `escanteios` | `cartoes` | `btts` must stay on SPORT and not emit GA soft template.
3. Optionally treat ResponseSelector’s own prompt chips (“diga gols…”) as an expected slot-fill turn.

---

## 7. Confidence

**Root cause confidence: HIGH (~0.90)**  
Primary: MasterIntent `short_general` + missing bare-`gols` short-FU coverage.  
Secondary: follow_up_engine / SCG asymmetry vs `escanteios`.  
CM/EM: not implicated at this confidence.
