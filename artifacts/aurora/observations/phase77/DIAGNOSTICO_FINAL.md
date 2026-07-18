# Fase 7.7 — Diagnóstico Final

Status: **INVESTIGAÇÃO CONCLUÍDA — SEM CORREÇÃO DE COMPORTAMENTO**  
Observabilidade: **IMPLEMENTADA** (`pipeline_trace.py` + hooks no router)

---

## Causa Raiz Mais Provável

**Loop sticky de fallback conversacional:**  
`GENERAL_CHAT` → `reply_general` (“Entendi. Posso te ajudar…”) → `NaturalResponseFilter` marca template similar → regenera com o **mesmo** `reply_general` → usuário recebe o mesmo texto indefinidamente.

Em paralelo, o **forced nonsport** pode emitir payload **sem** chave `confidence`, e o builder faz `payload["confidence"]` → **KeyError**, derrubando o turno e empurrando o usuário a reformular (friction ↑, inteligência percebida ↓).

### Probabilidade

| Hipótese | Probabilidade |
|----------|---------------|
| Sticky Entendi via NRF regenerate-same | **85%** |
| KeyError `'confidence'` no forced incomplete payload | **80%** |
| Ambas coexistindo nos 5 transcripts (Cenário C) | **75%** |
| Necessidade de nova engine / modelo maior | **<5%** |

---

## Módulos Suspeitos

### P0
1. `general_assistant.reply_general`
2. `natural_response_filter.filter_or_regenerate` (+ early/late wiring)
3. Forced nonsport dict incompleto em `copilot_unified_router`
4. `CopilotResponse(..., confidence=payload["confidence"])` sem guarda

### P1
5. Gap de `turn_ownership` (lock só no early stack; forced path sem re-lock)
6. `MEMORY_QUERY` → GA `None` → forced path
7. Late polish (NeverEmpty / ResponseReview) em turnos unlocked

### P2
8. `_run_fallback` brochure
9. Emotional/HPL sem owner mark
10. Credibility / LLM chat rewrite residual

---

## Correções Recomendadas (ordem — NÃO feitas nesta fase)

1. **ensure_soft_sections** em todo payload final (anti-KeyError)  
2. **Anti-sticky regenerate** (escape phrase ≠ Entendi)  
3. **Ownership finalize** após forced nonsport  
4. **MEMORY path** com payload completo  
5. Owner mark em emotional/HPL bem-sucedidos  
6. NeverEmpty só se vazio real  

Anti-loop / Recovery Mode: ver `04_PLANO_CORRECAO.md` (proposta apenas).

---

## Respostas do gargalo

| # | Pergunta | Resposta |
|---|----------|----------|
| 1 | Quem aciona o fallback? | IntelFallback, forced GA, `_run_fallback`, NRF regenerate, outer exception |
| 2 | Quando? | `payload is None` / similar template / intent unknown / crash |
| 3 | Sobrescrita? | **Sim** (late layers) |
| 4 | Descarte de válidas? | **Provável** quando unlocked |
| 5 | Curto-circuito? | **Sim** (early stack + forced nonsport) |

---

## Intent audit (perda)

| Classe | Detectada? | Onde se perde |
|--------|------------|---------------|
| emotional | Sim (`emotional_presence`) | Sem lock → late rewrite |
| meta | Sim (HCE) | Geralmente preservada se owned |
| social | Sim (Master/NRE) | GA general Entendi compete |
| football | Sim (Master/HIE/NL) | Blocked se nonsport; DT pode bloquear analyze |
| utilities | Sim (MATH/SYSTEM/MEMORY) | MEMORY → None → Entendi/crash |

---

## Entregáveis

| Doc | Path |
|-----|------|
| 1 Pipeline | `observations/phase77/01_PIPELINE_COMPLETO.md` |
| 2 Causas | `observations/phase77/02_CAUSAS_PROVAVEIS.md` |
| 3 Ranking | `observations/phase77/03_RANKING_CULPADOS.md` |
| 4 Plano | `observations/phase77/04_PLANO_CORRECAO.md` |

---

## Próximo passo oficial

Com logs `[INTENT]…[FINAL_RESPONSE]` em produção/interno, **confirmar** as hipóteses nos próximos transcripts — só então aprovar correção cirúrgica P0 (ainda sem engines novas).
