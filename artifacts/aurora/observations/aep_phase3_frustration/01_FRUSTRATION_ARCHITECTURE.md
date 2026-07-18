# AEP Phase 3 — Frustration Analytics Architecture

## Goal

Measure **perceived** conversational quality: detect frustration signals, track recovery, and surface top friction causes — without changing production engines.

## Layout

```
src/conversation/frustration_observability.py   # stamp-only (entities + debug)
scripts/run_frustration.py
tests/frustration/
  scenarios.py
  engine.py
  metrics.py
  results/last_frustration.json
```

## Flow

```
User message
  → Aurora reply (unchanged)
  → note_frustration_observability (entities stamp)
  → debug.frustration when developer audit / debug=true
  → run_frustration.py aggregates sessions → JSON metrics
```

## Integrations

| Surface | How |
|---------|-----|
| AEP | Harness reads `frustration_*` entity fields / expanded markers |
| Conversation Simulator | `frustration_analytics` slice on simulation report |
| developer_audit_mode | `payload.debug.frustration` via `attach_debug_to_payload` |

## Isolation

No changes to Market / Opinion / FollowUp / Calendar / Ownership / Partial Analysis engines. Reply text is never rewritten by this layer.
