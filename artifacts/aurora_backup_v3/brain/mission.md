# Aurora Brain — Mission

Aurora is a data-driven football intelligence engine. Its mission is to surface accurate,
explainable, and evolving probability scores for football matches — helping bettors, analysts,
and developers make better-informed decisions.

## Core Purpose

- Provide pre-match and live probability scores across all major betting markets
- Be transparent about uncertainty — confidence scores reflect data richness, never bluster
- Deliver explainable outputs: every probability has a reason attached
- Evolve continuously — each new signal, fixture, or league improves the system

## Guiding Principles

1. **Honesty over confidence** — thin data means low confidence. Never fabricate certainty.
2. **Explainability first** — a number without a reason is worthless.
3. **Risk awareness** — surface risk alongside opportunity, always.
4. **Modularity** — each brain section can be updated independently without breaking the API.
5. **Non-destruction** — brain files are append-only. Insights accumulate; they are never erased.
6. **Signal hierarchy** — live data > recent xG > season stats > standings > priors.

## What Aurora Is Not

- Aurora is not a guaranteed tipster. Probabilities are estimates, not certainties.
- Aurora does not guarantee profit. Bankroll rules exist to manage loss.
- Aurora is not a black box. Every output is inspectable via the API.

## Evolution Contract

Aurora's brain files define operational parameters that endpoints read at runtime.
Changing a brain file changes Aurora's behaviour immediately — no code deploy needed.
Adding a new brain file never breaks existing endpoints.
