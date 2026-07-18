# Fase 8.2-D — Diagnóstico Final

**Tipo:** PRODUCTION ROUTING AUDIT  
**Status:** INVESTIGAÇÃO CONCLUÍDA — **NENHUMA CORREÇÃO IMPLEMENTADA**

---

## PROBLEMA

↓

Em produção, `"o que você achou do jogo do fluminense ontem?"` ainda chega com  
`fallback_kind=calendar_authority` e `opinion_time=false`, apesar do smoke 8.2-B 7/7.

---

## CAUSA RAIZ

↓

**8.2-B funciona no detector, mas não controla o turno.**  
ContextRecovery reescreve a pergunta para `jogo do Fluminense` (calendar antes de opinion); HumanInference grava `topic_kind=calendar`; Brain Authority bloqueia opinion; IntelligenceFallback emite `calendar_authority`.

---

## EVIDÊNCIA

↓

| Prova | Detalhe |
|-------|---------|
| 1 arquivo Natural | `artifacts/aurora/src/conversation/natural_conversation.py` |
| 8.2-B no HEAD | `_is_recent_match_opinion` + commit `e93609b` |
| Detector isolado | `team_opinion` / `recent_match=True` |
| Recovery audit | `→ 'jogo do Fluminense' goal=calendar_or_fixture` |
| HIE | `intent=calendar_or_fixture topic_kind=calendar` |
| Gate | `natural_may_emit_opinion=False` |
| Fallback | `fallback_kind=calendar_authority opinion_time=False` |
| `opinion_time=false` | definido em `intelligence_fallback._payload` (não override misterioso) |
| Audit mode | só export frontend — mesma rota backend |

---

## GRAVIDADE

↓

**P0 de produto** — patch “aprovado” no smoke não muda UX real.  
**P0 de processo** — testes isolados mascaram SoT upstream (Recovery/HIE).

---

## RISCO

↓

- Falsa confiança em 8.2-B / smokes de detector.
- Repair (8.2-A) mitiga *depois* do erro; o misroute inicial permanece.
- Próximos patches em Natural sem tocar Recovery/HIE repetirão a falha.

---

## RECOMENDAÇÃO (só direção — NÃO feito nesta fase)

↓

1. Precedência **opinion/recent-match** em `context_recovery` **antes** do branch `jogo do`.  
2. Mesma precedência em `human_inference` (`_OPINION` / recent-match **antes** de `_CALENDAR`).  
3. `natural_may_emit_opinion`: não bloquear quando a mensagem atual é recent-match opinion.  
4. Smoke de **pipeline completo** (Master→Recovery→HIE→Natural→Fallback), não só `detect_natural_intent`.  
5. Validar `backend_commit` na UI em produção.

---

## Respostas às 7 perguntas

| # | Pergunta | Resposta |
|---|----------|----------|
| 1 | Qual arquivo em produção? | `artifacts/aurora/src/conversation/natural_conversation.py` via `copilot_unified_router` |
| 2 | Mais de um natural_conversation? | **Não** |
| 3 | Outro roteador antes? | **Sim** — ContextRecovery + HIE (+ DT) |
| 4 | Override de opinion_time? | **Sim** — payload IntelFallback `calendar_authority` seta `opinion_time=false` |
| 5 | Cache / build / path morto? | Path morto do patch: **não**; override vivo: **sim**. Deploy lag: possível secundário |
| 6 | Build tem commit correto? | Repo main **tem** `e93609b`; confirmar runtime via `backend_commit` |
| 7 | Audit mode ≠ produção? | **Não** na rota — só na riqueza do export |

---

## POR QUE continua em calendar_authority?

Porque a frase é tratada como **agenda** por Recovery/HIE (`jogo do`) **antes** da 8.2-B decidir, e o Fallback calendar é a resposta final — o smoke nunca exercitou essa cadeia.

---

## 1 INVESTIGAÇÃO = 1 CONCLUSÃO

**Conclusão:** a divergência smoke vs produção não é “Natural antigo”; é **SoT upstream (Recovery + HIE + calendar authority)** anulando a 8.2-B.

**Parar aqui. Nenhum código modificado.**
