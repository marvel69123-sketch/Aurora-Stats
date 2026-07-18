# Fase 7.9-C — Documento 3: Antes vs Depois

## Antes
```text
GA general → finalize → owner=GA locked=True
→ Emotional NÃO roda (payload already owned)
→ "aurora é minha maior criação" = Entendi…
```

## Depois
```text
GA general → finalize → DEFER (sem lock)
→ Emotional pode claim → owner=EMOTIONAL locked=True
→ "aurora é minha maior criação" = resposta emocional
→ Late filters respeitam rewrite_locked
```

| Caso | Antes | Depois |
|------|-------|--------|
| pride / maior criação | GA Entendi | **EMOTIONAL** locked |
| META (o que você faz?) | META | META (inalterado) |
| GA general sem presence | GA early lock | defer → GA no 2º pass |
| estou triste | GA (emotional não detecta sadness) | GA final (fora do escopo emotional.py) |
