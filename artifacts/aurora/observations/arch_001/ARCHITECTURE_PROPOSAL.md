# AURORA-ARCH-001 — Sports Language + Conversational State (Design Only)

**MODE:** REVIEW / DESIGN ONLY — **NO CODE CHANGES**  
**PRIORITY:** P0  
**INPUT EVIDENCE:** EVAL-001 (110q, 84.5% success; dominant `SPORT_REASONING` 10.9%)

---

## Executive verdict

Introduce two **additive façade layers** that normalize language and expose a typed conversation frame **before** existing engines run.

| Do | Don’t |
|----|--------|
| Add Sports Language Layer as single SoT for nicknames/compare normalization | Rewrite Aurora engines / markets / analyze |
| Add Conversational State Layer as typed “slots + phase” on top of existing ctx | Replace ownership_stability / sport_continuity (FROZEN) |
| Borrow **concepts** from Rasa slots + LangGraph phases | Adopt Rasa/LangGraph as runtime frameworks |

**Principle:** Engines stay strategic assets. Perception improves by feeding them cleaner entities and clearer phase — not by reinventing them.

---

## Research synthesis (reusable concepts)

| Source | Reusable concept | Aurora mapping |
|--------|------------------|----------------|
| **Rasa** | Intent + entities + **typed slots**; deterministic flows (CALM: LLM for understanding, rules for business) | Slots = `{home, away, team, date, ask_kind}`; flows ≈ dialog_mode + ownership rules already present |
| **LangGraph** | Explicit **phase state machine**; structured state authoritative over free text; conditional edges | Phases = `COMPARE | CALENDAR | FORM | FOLLOWUP | CLARIFY | GA`; edge = “slots filled → allow engine” |
| **Sports alias systems** | One normalization table; context-sensitive disambiguation (Inter BR vs Milan) | Unify `TEAM_ALIASES` + `_TYPO_TEAMS` + nicknames behind Sports Language façade |
| **Entity normalization pipelines** | Tokenize → alias → validate → ground-in-message → confidence | Already started in PATCH-001 `entity_safety`; extend, don’t fork |

**Not reusable as drop-in:** Rasa training pipelines, LangGraph as dependency (would rewrite orchestration of `copilot_unified_router`).

---

## 1. Proposed architecture

```text
USER MESSAGE
    │
    ▼
┌─────────────────────────────────────┐
│  L1  Sports Language Layer (NEW)    │  ← nickname / compare / Inter disambig
│  out: normalized_text, clubs[],     │
│       ask_kind, entity_conf[]       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  L2  Conversational State Layer     │  ← typed slots + phase (NEW façade)
│  (NEW)  reads/writes session ctx    │
│  out: phase, slots, can_dispatch    │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  EXISTING (UNTOUCHED CORE)          │
│  MasterIntent → Recovery* → NL →    │
│  sport_understanding → engines →    │
│  ownership / continuity (FROZEN) →  │
│  render / judge                     │
└─────────────────────────────────────┘

* Recovery becomes a consumer of L1 output, not a second nickname SoT.
```

### Layer contracts (design)

**Sports Language Layer (SLL)**
- Input: raw user text (+ optional locale hint BR/EU)
- Output:
  - `normalized_message` (e.g. `mengão ou verdão` → `Flamengo ou Palmeiras`)
  - `clubs: [{raw, canon, confidence}]`
  - `ask_kind: compare | calendar | form | favorite | bet | other`
  - `pair_separator: ou|x|vs|…|null`
- Rules: never invent fixtures; never map stopwords to clubs (keep PATCH-001); context for Inter/ATM

**Conversational State Layer (CSL)**
- Typed slots (Rasa-like): `home`, `away`, `focus_team`, `date_hint`, `ask_kind`, `phase`
- Phases (LangGraph-like, thin):  
  `OPEN → SPORT_PARSE → SLOT_READY → ENGINE → FOLLOWUP → RELEASE`
- Authority: **slots beat fused string entities** (`"Mengao Ou Verdao"` illegal as a team)
- Gate: `can_dispatch_sport_engine` only if slots grounded + phase ∈ {SLOT_READY, FOLLOWUP}
- Integrates with existing `dialog_mode` / ownership by **advising**, not replacing locks

---

## 2. What should be ADDED

| Add | Why | Invasiveness |
|-----|-----|--------------|
| Formal **SLL module** as SoT for nicknames/compare normalization | EVAL hot cell: slang/EU compares → `general_chat` | Low–Med |
| Formal **CSL slot schema** + phase enum on `conversation_manager` ctx | Prevent fused entities; clarify when to ask vs answer | Low–Med |
| Single **eval gate**: EVAL-001 regress suite must stay ≥84.5% + slang-compare subset ≥ target | Evidence-based | Low |
| Observability events: `SLL_EXPAND`, `CSL_PHASE`, `SLOT_SET` | Stop hypothesis churn | Low |

---

## 3. What should be REPLACED (narrow)

| Replace | With | Note |
|---------|------|------|
| Duplicate nickname maps (`_TYPO_TEAMS` slang ∩ SLL ∩ aliases) | **One façade API** that other modules call | Internally can still keep `TEAM_ALIASES` as API-Football SoT |
| Treating raw phrase as `entities.team` (`City Ou United`) | Slot pair `{home, away}` after SLL | Behavior change at entity write sites only |
| Clarification / “Entendi… me diga o time” when two clubs already resolved | Prefer engine or honest partial sport answer | Policy in CSL gate, not NRF rewrite of all GA |

**Do not replace:** analyze engines, markets, confidence_engine, API-Football client, ownership_stability core, sport_continuity_guard core.

---

## 4. What should remain UNTOUCHED

| Asset | Reason |
|-------|--------|
| Sports engines (`analyze_fixture`, markets, methodology, live) | Strategic; EVAL failures are upstream |
| `ownership_stability` / `sport_continuity_guard` (FROZEN) | High regression; CSL **wraps** with advice only |
| `TEAM_ALIASES` as provider resolve SoT | Keep; SLL feeds *into* resolver, doesn’t delete it |
| MasterIntent / NL router scoring core | Extend inputs (normalized message), don’t redesign classifiers first |
| Bankroll / learning / knowledge routers | Out of EVAL hot path |
| PATCH-001 entity stopwords / judge grounding | Preserve; SLL must call the same safety rules |

---

## 5. Regression risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Over-expansion of nicknames (`real` adjective → Real Madrid) | High | Confidence + compare/sport-lex gate (already sketched in SLL design) |
| Inter Milan vs Internacional wrong default | High | Message-context cues; EVAL cases for both |
| CSL fighting ownership lock (double policy) | Critical | CSL never forces unlock; only blocks *new* lock when slots invalid (align with PATCH-001 R3) |
| Normalized rewrite breaks Natural calendar phrasing | Med | Keep original in `raw_user_message`; engines see both |
| `dialog_mode=SPORT` + `intent=general_chat` mismatch | Med (current bug pattern) | CSL `can_dispatch` forces sport route when slots ready — **this is the intended fix** |
| Alias table drift vs SLL | Med | Single export + mirror sync in CI |
| Latency | Low | In-memory maps; no new LLM call required for v1 |

**High-risk if done wrong:** touching FROZEN ownership/continuity implementations directly.

---

## 6. Estimated HPS improvement

Baseline (EVAL-001): Success **84.5%**, HPS **76.4** (entity-weighted).

| Scenario | Assumed recovery of SPORT_REASONING (12 fails) | New success | Est. HPS |
|----------|-----------------------------------------------|------------:|---------:|
| Conservative (50% of slang/EU compares fixed) | +6 | ~90% | ~84 |
| Target (75% of compare×REASONING fixed) | +9 | ~93% | ~88 |
| Stretch (all 12 + 2 help-template entity leaks) | +14 | ~97% | ~93 |

**Design target for first migration slice:** +6 to +9 success points on EVAL-001 → **HPS ≈ 84–88**, without touching engines.

Confidence in estimate: **MEDIUM** (depends on nickname coverage completeness and whether rewrite reaches NL before GA).

---

## 7. Migration strategy (minimal invasive)

### Phase A — Sports Language façade (1 slice)
1. Declare SLL as **SoT** for nicknames/compare expand.  
2. Make `context_recovery` / NL **call SLL only** (no second map growth).  
3. Freeze ownership/continuity.  
4. Gate: EVAL slang-compare subset (mengão/flu/city/galo…) must pass recovery→intent≠general_chat for ≥N cases.  
5. Ship behind flag `AURORA_SPORTS_LANGUAGE=1` (default on after bake).

### Phase B — Conversational State slots (2nd slice)
1. Add typed slots on ctx; writers: SLL + recovery only.  
2. Ban fused team strings as `entities.team`.  
3. `can_dispatch_sport` when `ask_kind=compare` and 2 grounded clubs.  
4. Wire **one** decision point in router: if can_dispatch → skip GA clarification template.  
5. Do **not** rewrite ownership_stability.

### Phase C — Hardening
1. Inter/ATM/real disambiguation matrix + eval.  
2. Help templates BR-only (perception).  
3. Multi-turn continuity eval (currently under-measured).

### Rollback
- Flag off SLL/CSL → previous path.  
- No engine schema migration.  
- Slots are additive keys on ctx.

---

## Mapping to current hot failure

```text
"Mengão ou Verdão?"
  today: fused entity / general_chat / Entendi…
  target:
    SLL → Flamengo, Palmeiras, ask_kind=compare
    CSL → phase=SLOT_READY, can_dispatch=true
    existing sport_understanding + engines → sport answer (or honest partial)
```

---

## Success criteria check

| Criterion | Design status |
|-----------|---------------|
| Clear migration plan | ✓ Phases A–C |
| No high-risk regressions | ✓ Engines + FROZEN guards untouched; flags + eval gates |
| Minimal invasive | ✓ Façades + one dispatch gate |

---

## CONFIDENCE

**HIGH** that EVAL’s dominant gap is **upstream language→slot→dispatch**, not sports engines.  
**HIGH** that Rasa/LangGraph should inform **shape**, not replace Aurora runtime.  
**MEDIUM** on HPS delta until Phase A is measured on EVAL-001.

---

*No code was changed in this task.*
