# Fase 8.2-C — Regression Risks

| Risco | Mitigação | Residual |
|-------|-----------|----------|
| Pronome sem memória → rewrite errado | Sem `last_team` → não reescreve | Baixo |
| Repair engolido | `is_repair_signal` early-return | Nenhum (smoke T3) |
| Autoscale perde ctx | Mesma limitação 5B | Médio multi-VM |
| Falso positivo “dele” em frase longa | Regex focada em follow-ups curtos/opinativos | Baixo |
| Conflito com ReferenceResolver (focus) | Short memory roda **antes**; focus depois no sport path | Baixo — complementary |
| GA routing alterado | Não — só reescreve mensagem | Nenhum |

## Fora de escopo

- Corrigir calendar_authority / Recovery (8.2-D)
- Memória cross-sessão / Redis
