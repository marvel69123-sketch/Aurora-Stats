# LANGGRAPH-STATE-POC-001 — Architecture

**Date:** 2026-07-21  
**Phase:** 2 — shadow mode (log-only) + Phase 1 infrastructure  
**Flags:**
- `ENABLE_LANGGRAPH_STATE` default **OFF** (`0`) — production write path
- `ENABLE_LANGGRAPH_STATE_SHADOW` default **OFF** (`0`) — shadow compare only

**Shadow ≠ production activation.**

## Aspirational turn path (not production-active)

```text
User → SLL → LangGraph State (SportTopicState SSOT) → Engines → Response Selector
```

## Phase 2 live path (shadow)

```text
User → SLL → TB-V2 → CSL → Intent
              └→ maybe_shadow_compare (if SHADOW=1): OLD(ctx) vs NEW(isolated graph)
              → … engines / RS unchanged …
```

- Production writers remain CSL / SRF / short_mem / continuity / TB-V2.
- Shadow never writes subject stores; never changes `message` return value.

## Components

| Piece | Role |
|-------|------|
| `SportTopicState` | Dataclass SSOT shape: episode, fixture, teams, subject, topic, owner, date_context, followup_context, boundary_reason |
| LangGraph graph | Minimal `StateGraph`: `init_load` → `classify` → `{apply_boundary \| keep_followup \| apply_subject}` |
| Single writer (graph-internal) | `_commit` inside `langgraph_state_graph.py` — only path that stamps `sts` in the graph |
| Detection | Reuses `topic_boundary_v2` helpers — does **not** depend on `ENABLE_TOPIC_BOUNDARY_V2` |
| Adapter | `shadow_from_ctx` / `compare_shadow` / `maybe_shadow_compare` |

## Graph flow

```text
START → init_load → classify → apply_boundary | keep_followup | apply_subject → END
```

| Route | When | Effect |
|-------|------|--------|
| `apply_boundary` | new fixture / low entity overlap | `clear_for_new_episode` |
| `keep_followup` | soft FU / short message / in-episode team | keep fixture/teams/episode |
| `apply_subject` | seed or same-fixture restated / overlap OK | `replace_subject` |

## Dependency

`langgraph` is **optional** (`langgraph==0.4.8` commented in requirements).  
Missing package → sequential node fallback in shadow (`prefer_sequential`). Fail-open.

## Phase 3 (not implemented)

Sole-writer / followup read-through behind `ENABLE_LANGGRAPH_STATE` only after
shadow divergence is measured.
