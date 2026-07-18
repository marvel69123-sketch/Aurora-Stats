# Fase 7.9-B — Documento 2: Diff Resumido

## `natural_response_filter.py`

1. `extremely_similar(a, b)` — igualdade / prefixo 40 / sticky Entendi  
2. `_pick_bypass(ctx)` — escolhe resposta alternativa rotativa  
3. Em `filter_or_regenerate`:
   - se keep seria Entendi já visto no hist → `[NRF_LOOP_DETECTED]` + `[NRF_BYPASS]`
   - se regenerate → `same_as_input` / (`same_as_regen` + `similar`) / `sticky_entendi` → **não reutiliza**; força bypass
4. Logs obrigatórios: `[NRF_LOOP_DETECTED]` e `[NRF_BYPASS]`

Nenhuma mudança fora deste arquivo de produção.
