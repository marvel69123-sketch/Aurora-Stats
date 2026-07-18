# Fase 8.2-D — Dead Paths / Overrides

## Não é path morto do arquivo

`natural_conversation.py` **é** o módulo vivo. Não há cópia fantasma.

## Paths que “matam” o efeito da 8.2-B

### 1) ContextRecovery rewrite (vivo, dominante)

`context_recovery.py` — branch calendar **antes** de opinion:

- Casa `jogo d[oe]` dentro de “achou do **jogo do** fluminense…”
- Reescreve para `jogo do Fluminense`
- Nota: `completed:team_calendar`, `message_rewritten`

→ O detector 8.2-B **não vê** a frase original no router.

### 2) HumanInference calendar-before-opinion (vivo)

`human_inference.py`:

```text
_CALENDAR = … jogo d[oe] …     # linha ~39
# … bloco calendar (~302) …
# … bloco opinion (~364) …
```

Após rewrite (ou mesmo no original), `jogo do` ativa calendar → `topic_kind=calendar`.

### 3) Brain Authority gate (vivo)

`natural_may_emit_opinion()` → False se `is_calendar_authority(ctx)`.

Em `try_natural_conversation`, se `kind==team_opinion` e gate False → **`return None`**.

### 4) IntelligenceFallback calendar_authority (vivo)

`intelligence_fallback.py`:

```python
if is_calendar_authority(ctx):
    return _payload(..., kind="calendar_authority")
# entities: opinion_time = False  (só true para historical_copa / local_team_thinking)
```

→ Assinatura exata do audit de produção.

### 5) Override de `opinion_time`

Não há um “setter tardio” misterioso.  
`opinion_time=false` nasce do payload IntelFallback (`opinion_time` só liga para kinds específicos — `calendar_authority` **não** está na lista).

### 6) Cache / build antiga

Possível **em paralelo** (Autoscale / deploy lag), mas **insuficiente** como única causa: a simulação no código atual já reproduz `calendar_authority` com 8.2-B presente.

### 7) Ownership 7.9

Não é o gerador de `calendar_authority`. Pode apenas permitir que IntelFallback claim quando Natural não locka.
