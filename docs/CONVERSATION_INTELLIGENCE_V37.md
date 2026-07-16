# Aurora v3.7 — Conversation Intelligence Foundation

## Status

Additive inbound pipeline (backend):

```
Message → Normalization → Conversation Context → Intent → Confidence → (existing gates)
```

- **Does not** implement Aurora Casual
- **Does not** edit Resolver, FollowUp engine, Integrity, Premium Live, MatchHeader, Personalization, engines, or payload schemas
- On doubt → clarification (never invents fixtures)

## Module

`artifacts/aurora/src/conversation/message_intelligence.py`

Wired in `copilot_unified_router.py` immediately after session/context load, before SmallTalk.

## Tests

`artifacts/aurora/tests/test_conversation_intelligence_v37.py`
