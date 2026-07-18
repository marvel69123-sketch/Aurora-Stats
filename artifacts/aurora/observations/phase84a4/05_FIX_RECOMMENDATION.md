# Phase 8.4-A.4 — Fix recommendation (NÃO implementar nesta fase)

## Fix mínimo recomendado (próxima fase)

1. **Ownership:** após Natural emitir `match_opinion` / `match_opinion_renderer=True`, marcar owner+lock (ex. `SPORT` ou kind dedicado) para `should_skip_competing_social` / `can_presence_claim` **bloquearem** IntelFallback.
2. **IntelFallback:** se payload já tem `match_opinion_renderer` ou `response_type=match_opinion`, **não substituir** `executive_summary`.
3. **Sync path:** se loop está rodando, não cair em `render_from_plan` team-summary para recent-match opinion — reutilizar texto Natural ou chamar mop sync.
4. Remover instrumentação 8.4-A.4 (`_forensics_84a4`, flags temporárias) após o fix.

## Não fazer no fix

- Não redesenhar routing 8.2-E
- Não alterar UX templates globais sem necessidade
- Não “corrigir” só o título panorama sem fechar o overwrite

## Critério de aceite pós-fix

Pergunta Fluminense → texto mop (sem “leitura rápida”/“panorama”/Agenda)  
entities: `overwrite_by` ausente ou ≠ `intelligence_fallback`  
`renderer_stage=match_opinion_renderer` e summary alinhado
