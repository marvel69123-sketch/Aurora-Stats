# Fase 8.2-A — Regression Risks

| Risco | Mitigação | Residual |
|-------|-----------|----------|
| Falso positivo em frases normais | Regex estreita; smoke com `oi` / Flamengo / identity | Baixo — “me explica melhor” ainda não é repair (fora do escopo) |
| Repair roubar turno esportivo | Só dispara em sinal; bloqueia sport naquele turno | Aceitável — correção humana deve pausar sport |
| Memória `repair_memory` sumir no Autoscale | Mesma limitação de ctx da 5B; best-effort | Médio em multi-VM (igual anti-loop hist) |
| Conflito com HCE short_loose | Repair roda **antes** do GA; HCE não sobrescreve `assistant_kind=conversation_repair` | Baixo |
| NRE reescrever repair | `hce_kind` na lista de preservação NRE | Baixo |
| Ownership 7.9 | Não modificado; repair usa `human_conversation` + `hce_kind` (caminhos já existentes) | Baixo |
| Intent Master 7.9-E | Intocado; smoke 11/11 mantido | Nenhum observado |

## Fora de escopo (ainda quebrado)

- Misroute `team_calendar` vs opinion (`jogo do` / ontem) — fase futura
- GA Entendi para outros `GENERAL_CHAT` sem sinal de repair
