# Fase 7.9-A — Documento 3: Resultados dos Testes

## Unit (`pytest tests/test_ensure_soft_sections_79a.py`)

```text
2 passed
```

## Smoke (`scripts/phase79a_p0_1_smoke.py`)

### Forced incomplete (simula CR2)

| Check | Resultado |
|-------|-----------|
| `confidence` antes do ensure | False |
| Builder após ensure | OK |
| Label preenchida | `insufficient` |

### Probes obrigatórios

| # | Mensagem | Intent | Builder OK | Conf |
|---|----------|--------|------------|------|
| 1 | que horas são? | SPORT_QUERY | OK | True |
| 2 | quais jogos estão ao vivo? | GENERAL_CHAT | OK | True |
| 3 | estou triste | GENERAL_CHAT | OK | True |
| 4 | vc está em loop | GENERAL_CHAT | OK | True |
| 5 | oi | SMALL_TALK | OK | True |

Stdout: `observations/phase79a/smoke_stdout.txt`

**Nota:** Misroutes (CR5) e template Entendi (CR1) **permanecem** — fora do escopo P0-1. Este patch só elimina KeyError de seções suaves.
