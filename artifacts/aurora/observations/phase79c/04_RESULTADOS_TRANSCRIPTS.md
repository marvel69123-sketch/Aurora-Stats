# Fase 7.9-C — Documento 4: Resultados dos Transcripts

## Unit
```text
8 passed (test_ownership_79c + test_turn_ownership_74)
```

## Métricas

| Métrica | Valor |
|---------|-------|
| Respostas emocionais sobreviventes | **1** (`aurora é minha maior criação`) |
| pride→EMOTIONAL locked | **True** |

## Por probe

| Mensagem | Owner early | Locked early | Owner final | Source |
|----------|-------------|--------------|-------------|--------|
| estou triste | none (defer) | False | GA | GA |
| me sinto sozinho | none (defer) | False | GA | GA |
| vc está em loop | none (defer) | False | GA | GA |
| não vou desistir de você | none (defer) | False | GA | GA |
| aurora é minha maior criação | none (defer) | False | **EMOTIONAL** | EMOTIONAL |
| T3 o que voce faz? | META | True | META | META |
| T5 então me ajuda | META | True | META | META |

**Nota:** sadness / “não vou desistir” não batem em `emotional_presence` patterns — ownership defer funciona; claim emocional exige detecção no engine (fora do escopo 7.9-C).

---

**PARADO.** Aguardando aprovação para Fase 7.9-D.
