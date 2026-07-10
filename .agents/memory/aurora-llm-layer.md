---
name: Aurora LLM Layer
description: OpenAI integration as conversational polish layer over Aurora rule engines
---

# Aurora LLM Layer (conversation_llm.py)

## Architecture rule (absolute)
OpenAI is a **narrative layer only**. It never replaces Aurora's calculations (odds, stats, Kelly, EV, live scores). Numbers in `best_markets`, `confidence`, `risk`, `bankroll_recommendation`, `positive_factors`, `negative_factors` are always preserved.

**Why:** The value of Aurora is its structured data. LLM fabricates plausible-sounding numbers; never let it touch the payload's numerical fields.

## LLM Router logic (needs_llm)
```
_NO_LLM_INTENTS = {analyze_match, live_opportunities, bankroll_review, learning_recap, knowledge_search}
_LLM_INTENTS    = {emotional, fear, had_losses, beginner, wants_to_learn, confused, wants_safer, follow_up, unknown, user_profile_query}
greeting / identity / capabilities / help → False (templates are fine)
fallback: True if >10 words AND ctx has last_match
```

**Why:** Cost control. Structured analysis responses are already excellent from the rule engine. LLM adds value only for nuanced conversation.

## Environment variables
- `AI_INTEGRATIONS_OPENAI_BASE_URL` — auto-provisioned by Replit (setupReplitAIIntegrations)
- `AI_INTEGRATIONS_OPENAI_API_KEY` — auto-provisioned (dummy string, works with BASE_URL)
- Both must be present in the **running workflow** — restart the workflow after provisioning.

**How to apply:** If LLM fails with "not set" error, restart the Aurora workflow. The vars are set at process start, not hot-reloaded.

## Model
`gpt-5.4-mini` — cost-effective, fast enough for conversational layer. `max_completion_tokens=800`.

## Cache
In-process TTL cache (5 min, 256 entries) keyed on normalised message + context hash. Prevents repeated LLM calls for identical inputs within the same process lifetime.

## Integration point in copilot()
LLM block runs AFTER all Aurora engines, BEFORE saving the Aurora message to DB. If `has_structure` (best_markets or positive_factors present) → `enhance()`. Otherwise → `chat()`, merge only narrative keys.

## aurora_version field
- `"Copilot v1.0"` — rule-engine only response
- `"Copilot v1.0 + LLM"` — LLM layer was invoked
