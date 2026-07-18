# Fase 8.2-D — Router Order

Ordem relevante em `copilot_unified_router.py` (sport path):

| # | Camada | Arquivo | Efeito na pergunta Fluminense |
|---|--------|---------|-------------------------------|
| 0 | MasterIntent | `master_intent_router.py` | `SPORT_QUERY` → abre pipeline sport |
| 1 | ContextRecovery | `context_recovery.py` | **Rewrite** para `jogo do {time}` (branch calendar **antes** de opinion) |
| 2 | DeepThinking | `response_review.py` | Escreve `ctx.deep_thinking` |
| 3 | HumanInference | `human_inference.py` | `_CALENDAR` (`jogo do`) **antes** de `_OPINION` (`achou`) → `topic_kind=calendar` |
| 4 | WEB / Emotional / Profile / … | vários | — |
| 5 | **NaturalConversation** | `natural_conversation.py` | 8.2-B `_is_recent_match_opinion` só vê texto **já mutado**, ou opinion bloqueada por `natural_may_emit_opinion` |
| 6 | **IntelligenceFallback** | `intelligence_fallback.py` | Se `is_calendar_authority` → `fallback_kind=calendar_authority` |
| 7 | Ownership late / NRF / … | 7.9 | Não é a causa deste misroute |

---

## Precedências que vencem 8.2-B

1. **ContextRecovery calendar branch** (linhas ~284–308) casa `jogo d[oe]` **antes** do branch opinion (~310).
2. **HIE `_CALENDAR`** (~302) antes de **`_OPINION`** (~364).
3. **`natural_may_emit_opinion`** (`brain_authority.py`) retorna False se `topic_kind ∈ {calendar,fixture,kickoff,outlook}`.
4. **IntelFallback calendar_authority** sobrescreve / preenche quando Natural falha ou payload ainda claimable.

---

## Onde 8.2-B entra

Somente dentro de `detect_natural_intent()`, **depois** de Recovery/HIE terem rodado no router.

Smoke 8.2-B chama o detector **direto**, sem passos 1–3.
