# TOPIC-BOUNDARY-002 — Sticky context bleed fix

**Date:** 2026-07-21  
**Flag:** `ENABLE_TOPIC_BOUNDARY_V2` (default **0**)  
**Rollback:** `ENABLE_TOPIC_BOUNDARY_V2=0`  
**Related:** STICKY-BLEED-001, TOPIC-BOUNDARY-001

---

## Verdict

Sticky bleed after episode rotation is fixed **behind the existing V2 flag**, without redesigning Topic Boundary, engines, Response Selector, Ownership, or SLL.

| Criterion | Status |
|-----------|--------|
| Episode rotates | Pass |
| Subject rotates (`csl.fixture` / `teams` / `topic`) | Pass |
| No sticky bleed (SRF / bind / short sport mem) | Pass |
| No old fixture contamination via `note_csl` | Pass |
| Soft FU same episode unchanged | Pass |
| Flag default OFF (no prod regression path) | Pass |

---

## Root cause (confirmed)

1. Boundary ran **after** CSL + sport-intent rewrite.  
2. Orphan states (`sport_referent_frame`, `entity_v2_last_bind`, short sport memory) survived episode bump.  
3. `note_csl_after_response` rewrote CSL from the wrong analyze payload.

---

## Changes

### 1. Execution order (`copilot_unified_router.py`)

```
SLL → TopicBoundaryV2 → CSL → Sport Intent → short memory → fiction → …
```

`episode_boundary` / subject-guard stamps are **not** cleared by the per-turn flag pop after boundary.

### 2. Orphan cleanup (`topic_boundary_v2.apply_episode_boundary`)

On new episode, clears:

- `sport_referent_frame` (`clear_srf`)
- `entity_v2_last_bind`
- short sport memory keys
- follow-up / referent sticky keys

Does **not** clear global history, user preferences, or about-you session profile.

### 3. Full subject replace

`_bump_csl_episode` replaces `teams`, `fixture`, `topic` (no prior preserve).  
CSL resolve, when `episode_boundary`, re-applies `csl_subject_guard` and replaces compare sides from the message even if slots were already filled.

### 4. `note_csl` guard

`csl_subject_guard` blocks payload home/away/match that are disjoint from the new episode subject; sets `note_csl_blocked`.

### 5. Partial boundary

`current_message_entities` recognizes single-team asks (`Inter joga hoje?`) so low-overlap boundary fires.

---

## Observability logs / ctx stamps

| Signal | Meaning |
|--------|---------|
| `boundary_detected` | New episode applied |
| `boundary_reason` | e.g. `new_fixture`, `low_entity_overlap` |
| `subject_replaced` | CSL subject fully replaced |
| `orphan_state_cleared` | Orphan clear ran |
| `srf_cleared` | SRF cleared |
| `entity_bind_cleared` | `entity_v2_last_bind` cleared |
| `note_csl_blocked` | End-of-turn CSL write blocked |

Audit lines: `[AUDIT] boundary_detected|subject_replaced|orphan_state_cleared|srf_cleared|entity_bind_cleared|note_csl_blocked`.

---

## Tests

```text
tests/test_topic_boundary_v2_001.py  (regression)
tests/test_topic_boundary_v2_002.py  (scenarios 1–4 + note_csl block)
→ 16 passed
```

---

## Non-goals (untouched)

- `ownership_stability` internals  
- `sport_continuity_guard` internals  
- `response_selector`  
- methodology / market / confidence / intelligence / learning engines  
- SLL logic  

---

## Enablement

Keep `ENABLE_TOPIC_BOUNDARY_V2=0` until human audit on live router confirms scenarios 2–3.  
Enable per environment: `ENABLE_TOPIC_BOUNDARY_V2=1`.
