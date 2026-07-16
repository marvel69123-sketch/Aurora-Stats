# Aurora v3.6.0 — Conversation Personalization (Foundation)

## Status

- Feature flag: `conversationPersonalizationEnabled = false`
- Gear / panel: implemented, **not rendered** while flag is false
- Casual formatter: prepared with Technical fallback
- **Not wired** into `AuroraResponse` render path (presentation apply reserved for activation sprint)
- Engines / payloads / Premium Live / MatchHeader / FollowUp: untouched

## Architecture

```
Engines (frozen) → Payload neutro → Formatter (FE) → Technical | Casual → UI
```

Prefs live in `localStorage` (`aurora_conversation_preferences_v1`).
New aurora messages may stamp `presentationSnapshot` when the flag is on
(history is never rewritten).

## Activation

Set `conversationPersonalizationEnabled` to `true` in
`artifacts/web/src/lib/conversationPersonalization/flags.ts` only after
explicit product approval.
