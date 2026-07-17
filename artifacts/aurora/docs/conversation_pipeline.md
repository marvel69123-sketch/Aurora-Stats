# Aurora Conversation Pipeline Map (v4.5.1)

Documento de estabilização — quem escreve, quem altera, prioridade, fail-open.

## Ordem (router `copilot_unified_router`)

```
User message
  ↓
1. CUE (conversational_understanding)     — interpreta / reescreve
  ↓
2. HPL social (human_presence)            — short-circuit social
  ↓
3. Legacy small talk                      — fallback social
  ↓
4. State TTL / cancel / topic             — Conversation State (frozen)
  ↓
5. Context Reinforcement                  — scores + reassert last_*
  ↓
6. Reasoner                               — pensa, NÃO responde (frozen)
  ↓
7. CIL                                    — goal / humanize plan (frozen)
  ↓
8. CRL                                    — modo + draft short-circuit (frozen)
  ↓
9. Deep Reasoning                         — profundidade / opinião / cenários
  ↓
10. CI / FollowUp / NL / Engines          — se não short-circuit
  ↓
11. Integrity                             — strip invalid headers/markets
  ↓
12. Credibility                           — display_mode SOCIAL|FOLLOW_UP|REASONING|FULL_ANALYSIS
  ↓
13. Prediction Memory (passive)           — save only, TTL/purge
  ↓
14. CopilotResponse → UI
```

## Camadas e responsabilidades

| # | Camada | Input | Output | Escreve reply? | Prioridade | Fail-open |
|---|--------|-------|--------|----------------|------------|-----------|
| 1 | CUE | message, ctx | ConversationIntent, optional rewrite | Não | Alta em natural language | Sim → UNKNOWN |
| 2 | HPL | intent social | reply + soft payload | **Sim** (social) | Máxima em social | Sim → legacy ST |
| 3 | Small Talk | message | soft payload | Sim | Só se HPL miss | Sim |
| 4 | State | ctx | TTL clear / pending | Não | Infra | Sim |
| 5 | Context Reinforcement | ctx, message | scores em ctx | Não | Soft mirror | Sim |
| 6 | Reasoner | message, ctx | last_reasoning | Não | Interpretativo | Sim |
| 7 | CIL | message, ctx | thought, cil_reply_override | Pode refinar CRL | Sobre CRL draft | Sim |
| 8 | CRL | reasoning | ResponsePlan / payload | **Sim** se short-circuit | Draft base | Sim → FULL_ANALYSIS |
| 9 | Deep Reasoning | message, draft | chosen_answer profundo | **Sim** (override short-circuit) | **Ganha do draft CRL/CIL** em intents deep | Sim → v4.4 reflection |
| 10 | Engines | analyze/live | full report | Sim | Só pass-through | — |
| 11 | Integrity | payload | strip invalid | Não (remove UI) | Segurança fixture | — |
| 12 | Credibility | payload, reflection | metadata display_mode | Pode humanizar jargão | UI chrome | Sim |
| 13 | Prediction Memory | payload, reflection | prediction_id | Não | Passivo | Sim |
| 14 | UI (AuroraResponse) | response_metadata.credibility | badges/resumo | Não | FE | — |

## Prioridade de texto (quem “vence”)

1. **HPL social** (se social hit) — resposta final social  
2. **Deep Reasoning `chosen_answer`** — se short-circuit + intent profundo  
3. **CIL refine** sobre CRL draft — se Deep não forçou  
4. **CRL draft**  
5. **Engine executive_summary** — FULL_ANALYSIS  

## Intents forçados no Deep (v4.5.1)

- `vale a pena?` → worth_it  
- `por que?` → why  
- `o que mais te preocupa?` → worry  
- `mudaria sua opinião?` / `invalidaria` / `abandonar mercado` → **opinion_change**  
- `algo mais conservador?` → conservative  
- `algo mais agressivo?` → aggressive  

## Display modes (Credibility)

| Mode | Confiança UI | Resumo chrome | Badges | Quando |
|------|--------------|---------------|--------|--------|
| SOCIAL | Não | Não | Não | oi / obrigado / boa noite |
| FOLLOW_UP | Não | Não | Não | follow curto |
| REASONING | Não | Não | Não | deep / opinião |
| FULL_ANALYSIS | Sim | Sim | Condicional | analyze / live |

## Dependências (não editar)

State · Reasoner · CIL · CRL · FollowUp · Resolver · Engines · Integrity · Learning · Personalization

## Memory Foundation

- DB: `prediction_experience.db`  
- TTL predictions: 30 dias  
- TTL experience: 60 dias  
- Cap: 5000 predictions / 2000 experience rows  
- `purge_prediction_memory()` no init e opportunistic no store  

## Variation Layer

`response_variation_layer.py` — headers/openers anti-repetição; usado pelo Deep.
