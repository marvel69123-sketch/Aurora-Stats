# Fase 7.9-B — Documento 3: Antes vs Depois

## Antes (7.8)

```text
Turno 1: Entendi…
Turno 2: NRF similar=True → regenerate=reply_general → Entendi…
Turno 3: Entendi… (loop infinito)
Máx consecutivos Entendi: ≥2 (ilimitado)
```

## Depois (7.9-B)

```text
Turno 1: Entendi… (primeira vez permitida)
Turno 2: NRF_LOOP_DETECTED → NRF_BYPASS → frase alternativa
Turno 3: bypass rotativo (não Entendi)
Máx consecutivos Entendi: 1
```

## Unit regenerate×3

| # | Antes | Depois |
|---|-------|--------|
| 1 | Entendi | Entendi |
| 2 | Entendi | bypass (“Me conta de outro jeito…”) |
| 3 | Entendi | bypass (“Ok — vamos tentar de novo…”) |
