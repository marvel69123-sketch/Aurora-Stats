# Fase 8.1 — Anti-loop 7.9-B vs transcript real

---

## O que 7.9-B faz (código atual)

Em `natural_response_filter.filter_or_regenerate`:

1. Detecta sticky Entendi se o texto atual começa com `Entendi. Posso te ajudar` **e** o hist `ctx["recent_assistant_replies"]` já tem Entendi.
2. Emite `[NRF_LOOP_DETECTED]` + `[NRF_BYPASS]` e troca por frase alternativa (`_BYPASS_REPLIES`).
3. Smokes internos validaram isso **com hist quente no mesmo processo**.

---

## O que o transcript mostra

9 respostas **byte-idênticas** à frase completa de `reply_general` — incluindo o parágrafo do futebol.

Se o bypass 7.9-B tivesse actuado, o texto teria mudado para uma das alternativas (ex.: “Pode falar comigo normalmente…”).

**Portanto: o anti-loop não alterou nenhuma resposta desta sessão.**

---

## Hipóteses (ordenadas por evidência)

### H1 — Deploy sem 7.9-B (ou parcial) — probabilidade alta

Evidência:
- `entities_snapshot` **sem** `turn_owner`, `rewrite_locked`, `nrf_last_action`, markers 7.9-C/D.
- Export `2026-07-18T03:27:12Z` na mesma janela das correções 7.9.
- Comportamento idêntico ao Cenário C pré-patch (fase 7.7/7.8).

### H2 — Anti-loop executou early, mas hist estava vazio a cada turno — probabilidade alta em produção Autoscale

Evidência de código:
- Hist vive só em `ctx["recent_assistant_replies"]`.
- Persistência cross-VM **não garantida** (`conversation_context.py` — Autoscale).
- Reload SQLite via `ConversationContext.from_dict().to_dict()` **remove** chaves extras → hist some no cold get.

Efeito: `sticky_keep` nunca fica true → early NRF sempre `keep` Entendi.

### H3 — Late NRF bypassado por ownership lock — probabilidade média (pós-7.9-C/D)

Código late NRF:
```python
if rewrite_locked or human_conversation or turn_owner in {NRE, HCE, META}:
    # skip
```
Se GA for hard-locked, late NRF **não** roda. O anti-loop fica **100% dependente** do early NRF + hist.

### H4 — Outro fallback produziu Entendi sem NRF — probabilidade baixa neste audit

Sources apontam `GeneralAssistant`; não há `_run_fallback` brochure no texto.

---

## Respostas obrigatórias

| Pergunta | Resposta |
|----------|----------|
| Não foi executado? | **Provável no deploy que serviu a sessão** (H1), ou executou sem hist (H2) |
| Foi bypassado? | Late NRF **pode** ser skipped por lock (H3); early depende do hist |
| Houve outro fallback? | Não — foi o próprio GA default, repetido |

---

## Por que os testes passaram e o real falhou

| Teste 7.9-B | Uso real |
|-------------|----------|
| Mesmo processo, ctx contínuo | Autoscale / cold ctx |
| Probes curtos “Entendi×N” | GA + misroute + frustração sem repair |
| Assert em logs NRF | Deploy pode não ter o patch |
| Não testa “não entendeu / loop / aurora?” | Esses viram Entendi fresco com hist vazio |

---

## Conclusão

O anti-loop 7.9-B **não protegeu esta conversa**. Ou não estava no binário servido, ou rodou sem memória de respostas anteriores. Em ambos os casos, o usuário viu o mesmo sticky loop do Cenário C.
