# AURORA-TOPIC-BOUNDARY-001 — Episode Boundary V2

**TYPE:** IMPLEMENTATION  
**PRIORITY:** P0  
**MODE:** Additive façade — **no engine / FROZEN guard rewrites**  
**PRIOR ART:** ARCH-003 Phase 4, CSL-001 `episode_id`, fiction/context-jump guard

---

## Objective

Replace aggressive continuity behavior with **episode boundary detection**.

Inspired by Athena topic boundaries and episodic memory systems:

> If entity overlap is low **OR** a completely new fixture appears → create a new episode.

A new episode stops sticky/aggressive continuity from the previous sport context.

---

## Feature flag

| Value | Behavior |
|-------|----------|
| `ENABLE_TOPIC_BOUNDARY_V2=0` (default) | No-op — legacy continuity / `is_topic_switch` regex unchanged |
| `ENABLE_TOPIC_BOUNDARY_V2=1` | Detect + apply episode boundaries before continuity claims |

Rollback:

```powershell
$env:ENABLE_TOPIC_BOUNDARY_V2 = "0"
```

---

## Architecture

```text
User → SLL → CSL → Intent → short_memory → fiction_jump
                 → TopicBoundaryV2 (NEW, flag)  ← before continuity / response selector
                 → ResponseSelector / OS / SCG …
```

### Detection rules

1. **New fixture** — message has `A x B` (or vs) and sticky prior fixture differs  
2. **Low entity overlap** — Jaccard(prior sticky teams, current message teams) `< 0.34`  
3. **Keep** — soft follow-ups (`Quem está melhor?`, market shorts) with no new entities  
4. **Keep** — same fixture restated

Prior entities are read from sticky continuity keys (`last_*`, sport_anchor, focus, continuity blob) — **not** live CSL slots (CSL may already refresh on the same turn).

### Apply (new episode)

- `clear_fixture_context` + `clear_focus_on_boundary`  
- `expire_sport_anchor` / `release_owner_lock` (**public APIs only**)  
- Drop continuity session blobs  
- Rotate CSL `episode_id`; seed teams/fixture from **current** message  
- Signals: `ctx["episode_boundary"]=True`, `ctx["episode_id"]`, `ctx["topic_boundary_v2"]`, `brain_boundary_cleared`, `block_hydrate_legacy`

Response selector skips sticky continuity generators when `episode_boundary` is set (wrap only).

---

## KEEP / WRAP / REPLACE

| Module | Decision |
|--------|----------|
| methodology / market / confidence / intelligence / learning | **KEEP (FROZEN)** |
| ownership_stability / sport_continuity_guard internals | **KEEP** — call release/expire only |
| fiction_context_jump_guard / ambiguous_context_guard | **KEEP (FROZEN)** |
| CSL / SLL | **KEEP** — façade write of `episode_id` / seed slots only |
| `message_intelligence.is_topic_switch` | **WRAP** — V2 when flag on + ctx |
| `brain_authority` topic boundary | **KEEP** — late path unchanged |
| `response_selector.collect_early_candidates` | **WRAP** — skip sticky gens on new episode |

---

## Files

| File | Change |
|------|--------|
| `src/conversation/topic_boundary_v2.py` | **NEW** detector + apply |
| `src/conversation/message_intelligence.py` | WRAP `is_topic_switch(message, ctx=None)` |
| `src/routers/copilot_unified_router.py` | Wire early V2; pass ctx to topic switch |
| `src/conversation/response_selector.py` | Skip sticky gens when `episode_boundary` |
| `tests/test_topic_boundary_v2_001.py` | **NEW** unit tests |
| `observations/topic_boundary_001/*` | This doc |

---

## Episode storage / signals

| Key | Meaning |
|-----|---------|
| `ctx["csl"]["episode_id"]` | Rotated UUID for new episode (CSL contract) |
| `ctx["episode_id"]` | Mirror for non-CSL consumers |
| `ctx["episode_boundary"]` | Per-turn True when boundary applied this turn |
| `ctx["topic_boundary_v2"]` | Decision dict (reason, overlap, entities, …) |

---

## Validation

```powershell
cd artifacts/aurora
$env:ENABLE_TOPIC_BOUNDARY_V2 = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_topic_boundary_v2_001.py -q
```

**Result (2026-07-21):** `10 passed` (`test_topic_boundary_v2_001.py`).

Covered:

- Flag off → sticky `last_match` preserved on new fixture phrase  
- `Santos x Corinthians` after Flamengo sticky → new episode, anchor expired  
- `Quem está melhor?` → keep episode  
- Same fixture restated → keep  
- CSL same-turn refresh does not hide switch  
- `is_topic_switch` WRAP under flag on/off  
