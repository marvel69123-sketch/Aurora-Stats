# Aurora v3.7.1 — Conversation Intelligence Polish

## Fixes

1. **Market terms never become teams** — `e escanteios?` pass-through for FollowUp (no `Botafogo x Santos Escanteios` rewrite).
2. **Compare memory** — `prev_*` fixture shift on new analysis; compare intents use last + prev only (no invent).
3. **Human prefer-alt intents** — conversational short-circuit (`não gostei`, `tem algo melhor`, `mais conservador`, …).

## Untouched

Resolver, FollowUp engine, Integrity, Premium Live, MatchHeader, Personalization, engines, payloads.
