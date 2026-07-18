# Fase 7.9-B — Documento 5: Resultados dos Transcripts

## Unit tests

```text
3 passed (test_nrf_anti_loop_79b.py)
```

## Métricas agregadas

| Métrica | Valor |
|---------|-------|
| Entendi total (todas as falas) | 6 |
| Máx repetições consecutivas Entendi | **1** |
| Casos com LOOP_DETECTED/BYPASS | 3 |
| Loop sticky (≥2 seguidos) | **NÃO (OK)** |

## Por caso

| Caso | Resultado |
|------|-----------|
| P1 vc está em loop | T1 Entendi → T2 **bypass** |
| P2 para de repetir isso | T1 SYSTEM (não Entendi) → T2 Entendi (1ª vez OK) |
| P3 não funciona | T1 Entendi → T2 **bypass** |
| P4 estou triste | T1 Entendi (único; sem loop) |
| T2 vague→frustração | META → Entendi → **bypass** |
| T5 tempo+general | SPORT stub → Entendi → SYSTEM (sem sticky) |

## Source final observado

- 1ª Entendi: `source=GA` / `action=keep`
- Repetição bloqueada: `source=bypass` / `action=bypass`

---

**PARADO.** Aguardando aprovação para Fase 7.9-C.
