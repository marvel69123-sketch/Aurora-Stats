# Fase 7.7 — Documento 1: Pipeline Completo

Status: AUDITORIA (sem correção)  
Fonte: `artifacts/aurora/src/routers/copilot_unified_router.py` (`async def copilot`)

---

## Visão real (não o diagrama ideal)

Não existe um Planner/Entity Resolver isolados como módulos únicos. O fluxo real é um **orquestrador único** com short-circuits e rewrites tardios.

```text
Usuário (web)
  ↓
POST /copilot  →  copilot_unified_router.copilot
  ↓
[INTENT] MasterIntentRouter.apply_master_intent
  ↓
[ENGINE] GeneralAssistant (se !sport)
  ↓
[ENGINE] HumanConversationEngine (pode sobrescrever GA)
  ↓
[ENGINE] NaturalResponseEngine (social / polish)
  ↓
[PLANNER] turn_ownership.finalize_early_ownership  ← ÚNICO lock precoce
  ↓
se sport_ok && payload=None:
  ContextRecovery → HIE → WEB → CUE → Emotional → HPL → Natural
  → IntelligenceFallback → SmallTalk → Reasoner/CIL → CRL → MessageIntel
  ↓
se !sport_ok && payload=None:
  [FALLBACK] forced HCE/GA / reply_general incompleto
  ↓
FollowUp / NL Router / Engine dispatch (analyze|live|bankroll|…|_run_fallback)
  ↓
Late polish: LLM → i18n → personality → credibility → formatter
  → ResponseReview → NeverEmpty → ThinkingDelay → EmotionalGuard
  → NaturalResponseFilter (pode regenerar reply_general)
  → PIE → HCE note
  ↓
[FINAL_RESPONSE] CopilotResponse(**payload["confidence"] …)
  ↓
Frontend (não auditado nesta fase — sem alteração)
```

---

## Etapas — arquivo, ordem, I/O, sobrescrita

| # | Etapa | Arquivo | Ordem | Recebe | Retorna | Sobrescrita possível? |
|---|--------|---------|-------|--------|---------|------------------------|
| 1 | Intent Detection | `conversation/master_intent_router.py` | 1 | `message`, `ctx` | `MasterIntent` (intent, allow_sport, confidence) | Fail-open → sport_ok=True |
| 2 | GeneralAssistant | `conversation/general_assistant.py` | 2 | message, master_intent | payload soft OU None (MEMORY) | HCE pode sobrescrever |
| 3 | HCE | `conversation/human_conversation_engine.py` | 3 | message, ctx, existing GA | payload continuity/meta | NRE polish; ownership lock |
| 4 | NRE | `conversation/natural_response_engine.py` | 4 | message, payload/ctx | social payload ou polish | Ownership lock |
| 5 | Ownership | `conversation/turn_ownership.py` | 5 | payload | `turn_owner`, `rewrite_locked` | Só early stack |
| 6 | Recovery | `conversation/context_recovery.py` | 6* | message, ctx | message reescrito | Só se sport + payload None |
| 7 | Entity / HIE | human inference + CUE | 7* | message | entities / rewrite | Pode forçar analyze_match |
| 8 | Social rivals | emotional / HPL / natural / intel_fallback | 8* | message | payload | Ownership skip se locked |
| 9 | Forced nonsport | router ~2393 | 9 | — | GA ou dict incompleto | **Sem confidence** no dict inline |
| 10 | Engine Selection | router dispatch | 10 | intent, entities | analyze/live/…/fallback | `_run_fallback` help menu |
| 11 | Fallback late | `natural_response_filter.py` + `reply_general` | late | summary | regenerate | **Sticky Entendi loop** |
| 12 | Response Builder | `CopilotResponse(...)` | last | payload | HTTP JSON | **KeyError se falta confidence** |
| 13 | Frontend | `artifacts/web` | — | CopilotResponse | UI | Fora do escopo 7.7 |

\* Etapas 6–8 só entram se `_sport_ok and payload is None`.

---

## Observabilidade (Fase 7.7)

Módulo: `conversation/pipeline_trace.py`  
Tags: `[INTENT] [ENTITIES] [PLANNER] [ENGINE] [FALLBACK] [RECOVERY] [FINAL_RESPONSE]`  
Env: `AURORA_PIPELINE_TRACE=1` (default on) / `0` para desligar.
