# AEP Phase 2 — Failure Detection

| Flag | Meaning |
|------|---------|
| `loop_detected` | Sticky GA / empty / “Entendi. Posso te ajudar…” |
| `context_lost` | Short FU/pronoun after sport without continuity signals |
| `intent_flip` | Unexpected intent (e.g. `general_chat` on `e dele?`) |
| `fallback_abuse` | `intelligence_fallback` / calendar steal on continuity turns |
| `invalid_entity` | Fiction expected INVALID but not marked |
| `hallucination_risk` | Invention markers on INVALID / fiction path |
| `frustration_detected` | User repair/frustration phrasing |
| `useless_reply` | Empty / tiny / “Interessante.?” replies |

## Conversation failure

Any critical flag on any turn → conversation `success=false`.

## Metrics derived

- **Conversation Success Rate** — % conversations with no critical flags
- **Loop Rate** — loop flags / runs
- **Context Preservation** — follow-up turns without `context_lost`
- **Intent Accuracy** — capabilities + INVALID tags hitting expected signals
- **Average Turns Before Failure** — mean first failing turn index
