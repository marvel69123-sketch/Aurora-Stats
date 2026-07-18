# Fase 7.9-A — Documento 2: Diff Resumido

## Novo: `ensure_soft_sections.py`

```python
def ensure_soft_sections(payload):
    # se confidence/risk/bankroll ausentes ou não-dict → preenche defaults seguros
    # idempotente; não toca executive_summary nem engines
```

Defaults:
- `confidence`: score=0.0, label=insufficient, data_sources=["SoftSections"]
- `risk`: level=Unknown, flags=[], invalidation_conditions=[]
- `bankroll_recommendation`: stake=0, no_bet=True

## Router (`copilot_unified_router.py`)

Imediatamente **antes** de `return CopilotResponse(...)`:

```python
payload = ensure_soft_sections(payload) or payload
```

Nenhuma outra etapa do pipeline foi modificada.
