# STICKY-BLEED-001 — Why old fixture leaks after episode rotation

**Type:** Investigation only — **NO CODE CHANGES**  
**Date:** 2026-07-21  
**Evidence:** `observations/parallel_human_audit_001/raw_topic_boundary_on.json` (S2 T2)  
**Related:** TOPIC-BOUNDARY-001 (`topic_boundary_v2.py`), OWNER-001 honesty/SRF path

---

## Verdict

`episode_id` rotation is **real but insufficient**. The user-visible bleed is not “owner TTL refusing to die.” It is a **ordering + incomplete cleanup** failure:

1. **CSL does not replace slots** when a new `A x B` arrives while prior `teams` already has length ≥ 2 (unless SLL applied clubs).  
2. **Sport-intent `skill_compare_strength` rewrites the new fixture onto CSL’s old teams** *before* Topic Boundary V2 runs.  
3. Boundary then clears some sticky keys and seeds Liverpool into CSL, but the **router message is already Flamengo-shaped**.  
4. Analyze + honesty run on Flamengo; **`sport_referent_frame` / `entity_v2_last_bind` / `short_conversation_memory` are never cleared** → `Mantendo foco Flamengo…` prefix.  
5. **`note_csl_after_response` overwrites** the new-episode CSL seed with Flamengo home/away from the wrong analysis.

So: episode rotates; **subject of the turn does not**.

---

## Fact pattern (audit S2 T2, V2 ON)

| Signal | Observed |
|--------|----------|
| User | `Liverpool x Chelsea` |
| `episode_id` | **rotated** `6af4d299…` → `036e2b46…` |
| End-of-turn `csl_fixture` / teams | still **Flamengo vs Palmeiras** |
| `entities.home` / `away` | **Flamengo** / **Palmeiras** |
| `sport_intent` | `compare_strength` |
| User text | **`Mantendo foco Flamengo x Palmeiras…`** + Flamengo partial analysis |
| Mentions Liverpool/Chelsea | **false** |

---

## Call chain (bleed)

```
T2: "Liverpool x Chelsea"
  → SLL          (often no club list if not applied)
  → CSL resolve  ★ KEEP Flamengo/Palmeiras (teams already filled; no SLL refresh)
  → Sport Intent ★ REWRITE → "analisar Flamengo x Palmeiras (comparativo de forca)"
  → TopicBoundaryV2 ★ NEW_EPISODE (overlap/new_fixture) — clears last_*, releases lock,
                     seeds CSL with Liverpool… but MESSAGE already wrong
  → analyze_match on rewritten Flamengo message
  → Entity v2 ASSUME + honesty ★ Mantendo foco from uncleared SRF
  → note_csl ★ writes Flamengo from payload → wipes Liverpool seed
```

---

## Investigation checklist

### 1. Owner TTL

| Finding | Detail |
|---------|--------|
| V2 calls | `release_owner_lock(reason=episode_boundary:…)` |
| TTL constants | `OWNER_LOCK_TTL_SEC=75`, `OWNER_LOCK_MAX_TURNS=5` |
| Bleed role | **Secondary.** Lock is released; analyze / post-sport then re-activates SPORT lock on the *wrong* fixture. TTL is not what keeps Flamengo in the summary. |

### 2. Continuity cache

| Finding | Detail |
|---------|--------|
| V2 pops | `conversation_continuity`, `pronoun_continuity`, `advanced_football_continuity`, `ci_pending` |
| Response selector | On `episode_boundary`, skips continuity/OS generators (skill-only pool) |
| Bleed role | **Not the T2 author.** T2 owner is `partial_analysis` (analyze path), not soft-hold. Continuity skip helps FUs after switch but does not fix the rewritten analyze message. |

### 3. Recent entities memory

| Store | Cleared by V2? | Bleed role |
|-------|----------------|------------|
| `last_match` / `last_home` / `last_away` / `last_analysis` | **Yes** (`clear_fixture_context`) | Cleared mid-turn; re-seeded by wrong analyze |
| `short_conversation_memory` | **No** | Orphan prior fixture/team for pronoun / continuity helpers |
| `sport_referent_frame` (SRF) | **No** | Primary source of `Mantendo foco {fixture_label}` |
| `entity_v2_last_bind` | **No** | Honesty falls back to prior bind assumptions |
| `conversation_focus` | Cleared via `clear_focus_on_boundary` | OK if that helper runs |

### 4. Orphan state

After V2 apply, ctx can be **internally inconsistent**:

- `episode_id` / `episode_boundary` / `topic_boundary_v2` → new episode  
- `csl` briefly seeded with Liverpool (then overwritten at note)  
- `sport_referent_frame` still Flamengo  
- `short_conversation_memory` still Flamengo  
- Router `message` already rewritten to Flamengo compare  

This orphan SRF + rewritten message is the **exact** “Mantendo foco + Flamengo analysis” shape.

### 5. Owner stability reuse

| Finding | Detail |
|---------|--------|
| Soft-hold reuse | Blocked on new episode in response_selector |
| Force / claim after GA | Not needed for T2; analyze owns turn |
| `_sport_anchor` / continuity score | Can still see short_memory / SRF remnants if those aren’t cleared — risk for **later** soft FUs even when T2 is analyze |

Bleed on T2 is **not** primarily `_build_hold_payload`; it is **intent rewrite + analyze + honesty**.

### 6. CSL episode cleanup

| Finding | Detail |
|---------|--------|
| V2 `_bump_csl_episode` | New `episode_id`, `teams=current_entities`, `fixture=new_fixture`, phase SLOT_READY/OPEN |
| **Pre-V2 CSL resolve bug** | `hydrate` keeps prior `state.teams`. Refresh to new clubs only if `sll.applied && sll.clubs`. Else `elif is_compare and len(state.teams) < 2` — **skipped when prior teams already ≥ 2**. New `Liverpool x Chelsea` **does not replace** Flamengo slots. |
| Sport intent | `_skill_compare_strength`: if message has `x`/`vs`/`ou` and CSL has ≥2 teams, returns `analisar {csl[0]} x {csl[1]} (comparativo de forca)` **even when the user’s sides are different**. |
| Pipeline order | `CSL → Sport Intent → TopicBoundary` — boundary cannot undo the rewrite. |
| End-of-turn | `note_csl_after_response` sets teams/fixture from payload `home`/`away`/`match` → Flamengo wins again. |

---

## Exact overwrite / leak points

| # | Point | Mechanism |
|---|-------|-----------|
| A | **CSL resolve** (`conversation_state_layer.py` ~409–425) | No slot replace for new fixture when prior teams filled and SLL didn’t apply |
| B | **Sport intent skill** (`sport_intent_layer.py` `_skill_compare_strength` ~235–236) | Rebinds `A x B` message onto **CSL teams**, not message teams |
| C | **Pipeline order** (router ~1816–1871) | Intent rewrite **before** episode boundary |
| D | **Incomplete V2 cleanup** (`apply_episode_boundary`) | Misses SRF, `entity_v2_last_bind`, `short_conversation_memory` |
| E | **Honesty** (`entity_resolver_v2` ASSUME + `partial_inference_honesty`) | Prefixes `Mantendo foco` from orphan SRF |
| F | **note_csl** | Re-hydrates CSL from wrong analyze payload |

---

## Why `episode_id` looks “correct” but product doesn’t

V2 successfully:

- detects `new_fixture` / low overlap  
- rotates UUID  
- releases owner lock + expires sport_anchor  
- clears `last_*` continuity blobs  

It does **not** control the already-rewritten message or the uncleared SRF/short-memory. End-of-turn CSL note then **proves** the wrong subject by writing Flamengo back into `csl_fixture`.

---

## Minimal patch directions (proposal only — do not implement here)

Ordered by leverage:

1. **CSL:** On explicit new fixture/compare in message (or SLL clubs), **replace** `teams`/`fixture` even when prior slots are full (topic switch).  
2. **Sport intent:** Compare skill must use **message-side teams** when they disagree with CSL; never rewrite `Liverpool x Chelsea` → Flamengo.  
3. **Order:** Run Topic Boundary **before** sport-intent rewrite (or re-run intent after boundary).  
4. **V2 cleanup:** Also clear/reset `sport_referent_frame`, `entity_v2_last_bind`, `short_conversation_memory` on new episode.  
5. **note_csl:** On `episode_boundary` / new episode, prefer message/current fixture over payload if they diverge (guardrail).

---

## Answers to tasked surfaces

| Surface | Contributes to bleed? | Notes |
|---------|----------------------|-------|
| Owner TTL | Weak / indirect | Released; re-locked on wrong analyze |
| Continuity cache | Cleared; not T2 author | Selector skip OK for holds |
| Recent entities memory | **Yes** | short_memory + SRF uncleared |
| Orphan state | **Yes** | Inconsistent episode vs SRF/message |
| Owner stability reuse | Low on T2 | High residual risk on later FUs |
| CSL episode cleanup | **Partial** | UUID rotates; slots/subject not |

---

## Conclusion

Sticky bleed after episode rotation is **not** a failed UUID write. It is **subject hijack before boundary** (CSL sticky slots + sport-intent rewrite) plus **orphan SRF/honesty** and **CSL note overwrite**. Fixing rotation alone cannot fix user text until those points are addressed.
