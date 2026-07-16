# Aurora v3.6.1 — Conversation Personalization (Phase 1 Activation)

## Status

- Feature flag: `conversationPersonalizationEnabled = true`
- Gear / panel: **rendered** (header next to Aurora)
- Prefs: save/restore via `localStorage` (`aurora_conversation_preferences_v1`)
- Casual formatter: **not connected**
- `applyPresentation`: **not used** in UI
- `presentationSnapshot`: **not applied** (Phase 1 stamps nothing)
- Engines / payloads / Premium Live / MatchHeader / FollowUp / AuroraResponse: untouched

## Phase 1 scope

Visual activation only: open settings, toggle options, persist preferences.
Changing Técnica/Casual (or any slider) does **not** change Aurora replies.

## Later phases

Wire presentation formatters only after explicit approval.
