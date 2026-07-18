# Fase 7.8 — Relatório de Evidência
Gerado: 20260718T024345Z
Modo: somente evidência (sem correções)

## Prova / Refutação

### H1 — NRF regenera Entendi
**CONFIRMADA**

- `T1 — GENERAL_CHAT sticky (reconstrução Cenário C)` / `não é isso`: NRF regenerou e saída ainda contém Entendi
  `[NRF_OUTPUT] action=regenerate similar=True score=80.0 reasons= text_prefix=Entendi. Posso te ajudar com isso de forma direta.  Se for sobre futebol, me dig same_as_input=True same_as_regen=True enten`
- `T1 — GENERAL_CHAT sticky (reconstrução Cenário C)` / `não é isso`: saída idêntica ao regenerate (reply_general)
  `[NRF_OUTPUT] action=regenerate similar=True score=80.0 reasons= text_prefix=Entendi. Posso te ajudar com isso de forma direta.  Se for sobre futebol, me dig same_as_input=True same_as_regen=True enten`
- `T1 — GENERAL_CHAT sticky (reconstrução Cenário C)` / `não é isso`: similar=True com template Entendi
  `[NRF_OUTPUT] action=regenerate similar=True score=80.0 reasons= text_prefix=Entendi. Posso te ajudar com isso de forma direta.  Se for sobre futebol, me dig same_as_input=True same_as_regen=True enten`
- `T1 — GENERAL_CHAT sticky (reconstrução Cenário C)` / `não é isso`: Entendi em turnos consecutivos
  `turn_repeat`
- `T1 — GENERAL_CHAT sticky (reconstrução Cenário C)` / `quero outra coisa`: NRF regenerou e saída ainda contém Entendi
  `[NRF_OUTPUT] action=regenerate similar=True score=80.0 reasons= text_prefix=Entendi. Posso te ajudar com isso de forma direta.  Se for sobre futebol, me dig same_as_input=True same_as_regen=True enten`
- `T1 — GENERAL_CHAT sticky (reconstrução Cenário C)` / `quero outra coisa`: saída idêntica ao regenerate (reply_general)
  `[NRF_OUTPUT] action=regenerate similar=True score=80.0 reasons= text_prefix=Entendi. Posso te ajudar com isso de forma direta.  Se for sobre futebol, me dig same_as_input=True same_as_regen=True enten`
- `T1 — GENERAL_CHAT sticky (reconstrução Cenário C)` / `quero outra coisa`: similar=True com template Entendi
  `[NRF_OUTPUT] action=regenerate similar=True score=80.0 reasons= text_prefix=Entendi. Posso te ajudar com isso de forma direta.  Se for sobre futebol, me dig same_as_input=True same_as_regen=True enten`
- `T1 — GENERAL_CHAT sticky (reconstrução Cenário C)` / `quero outra coisa`: Entendi em turnos consecutivos
  `turn_repeat`

### H2 — Forced nonsport sem confidence
**CONFIRMADA**

- Forced dict keys: `['best_markets', 'brain', 'entities', 'executive_summary', 'final_recommendation', 'intent', 'is_live', 'match']`
- forced_has_confidence: **False**
- GA completo tem confidence: **True**
- Consumidor: `copilot_unified_router CopilotResponse(... ConfidenceSection(**payload['confidence']))`

### H3 — Ownership perdido
**PARCIALMENTE REFUTADA no early stack (owner GA/HCE/NRE com lock); gap permanece no forced path sem finalize**

- Owner inicial após finalize: tipicamente `GA` / `META` / `HCE` com `locked=True`
- Owner final: **mesmo** (sem perda no early stack)
- Momento do loop: **early NRF (antes do lock)**, não late NRF
- Gap confirmado: forced incomplete **não** chama `finalize_early_ownership`

### Achados extras (probes)
| Probe | Intent | Resultado |
|-------|--------|-----------|
| estou triste | GENERAL_CHAT | Entendi (emotional não venceu) |
| pare de repetir | GENERAL_CHAT | Entendi |
| vc está em loop | GENERAL_CHAT | Entendi + regenerate similar |
| quais jogos estão ao vivo? | GENERAL_CHAT | Entendi (**misroute**) |
| que horas são? | SPORT_QUERY | stub sport (**misroute**) |

## Causas raiz definitivas (após evidência)

1. **H1 CONFIRMADA (mecanismo):** `filter_or_regenerate` + `reply_general` idempotente → template Entendi se reproduz quando similar=True ou regenerate=mesmo texto.
2. **H2 CONFIRMADA (estrutural):** dict forced nonsport omite `confidence`/`risk`/`bankroll_recommendation`; builder usa `payload['confidence']`.
3. **H3 PARCIAL:** early GA/HCE/NRE recebem owner+lock; **forced incomplete não chama finalize_early_ownership** → owner=none, late NRF pode correr; skip late NRF lista NRE/HCE/META mas GA só via `rewrite_locked`.

## Linha temporal típica (GENERAL_CHAT loop)

```text
[INTENT] GENERAL_CHAT sport_ok=False
[ENGINE] general_assistant kind=general
[NRF_INPUT] text=Entendi…
[NRF_OUTPUT] action=keep|regenerate (similar)
[OWNER] after_early_finalize owner=GA locked=True
[PAYLOAD_BEFORE] late_nrf has_confidence=True
[NRF_OUTPUT] action=skipped_owned  (se locked)
[PAYLOAD_AFTER] late_nrf
[OWNER] final owner=GA
```
No turno 2+, early NRF já regenera Entendi **antes** do lock.
