# 8.4-A.9 — Repair Reclassification

## Expanded repair signals

`você não entendeu` · `preste atenção` · `pensa um pouco` · `não foi isso` ·
`aff` · `releia` (+ prior loop/correction patterns)

## Behavior

On repair signal:

1. Read `repair_memory.last_user_question` (+ `last_intent`)
2. Re-run capability detection / MasterIntent on that question
3. If capabilities (or SYSTEM identity) → return the **reclassified payload**
4. Else → classic repair clarification reply

## Audit

- `repair_reclassified`
- `previous_intent`
- `new_intent`
- (+ capability audits when new intent is capabilities)

## Example

```
o que sabe fazer?     → assistant_capabilities
você não entendeu     → repair_reclassified + assistant_capabilities
```
