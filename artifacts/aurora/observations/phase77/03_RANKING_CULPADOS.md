# Fase 7.7 — Documento 3: Ranking de Culpados

Cenário C confirmado por evidência de código (alinhado aos 5 transcripts: loop de fallback + inteligência percebida baixa).

---

## P0 — Quebram experiência / podem derrubar o turno

| Rank | Módulo | Por quê |
|------|--------|---------|
| 1 | `general_assistant.reply_general` | Origem do template sticky |
| 2 | `natural_response_filter.filter_or_regenerate` | Regenera com o **mesmo** template → loop |
| 3 | `copilot_unified_router` forced nonsport dict | Payload sem `confidence` → KeyError |
| 4 | `copilot_unified_router` `payload["confidence"]` | Crash sem fail-open no builder |

---

## P1 — Amplificam perda de inteligência percebida

| Rank | Módulo | Por quê |
|------|--------|---------|
| 5 | `turn_ownership` (gap) | Lock só no early stack; emotional/intel/sport unlocked |
| 6 | Late NRF path (router) | Pode sobrescrever nonsport mesmo após boa resposta |
| 7 | `intelligence_fallback` / NeverEmpty | Preenche vazio com filler genérico |
| 8 | MEMORY_QUERY → GA None | Empurra para forced incomplete |

---

## P2 — Ruído / secundário

| Rank | Módulo | Por quê |
|------|--------|---------|
| 9 | `_run_fallback` help brochure | Intents unknown → menu genérico |
| 10 | ResponseReview / credibility / LLM chat | Rewrite tardio sem ownership |
| 11 | Emotional / HPL sem mark owner | Competição social residual |
| 12 | Frontend | Consumidor; não origem do loop (fora do escopo) |

---

## Não culpados (para esta auditoria)

- Modelos LLM maiores / prompts maiores  
- Necessidade de nova engine  
- Frontend UX (proibido alterar na 7.7)
