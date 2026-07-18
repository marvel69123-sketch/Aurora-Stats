# Fase 8.1 — Auditoria GeneralAssistant

---

## O que é

Módulo: `artifacts/aurora/src/conversation/general_assistant.py`

| Função | Papel |
|--------|-------|
| `try_general_assistant(message, master_intent, ctx)` | Short-circuit nonsport |
| `reply_general(message)` | Template fixo Entendi (ignora conteúdo) |
| `_payload(..., skip_llm=True)` | Marca resposta final sem LLM |

Wire no router: MasterIntent → se `not allow_sport_pipeline` → GA → (opcional HCE override) → NRE scrub → ownership → late NRF.

---

## Respostas obrigatórias

### 1) Ele está dominando o sistema?

**Sim, no uso real deste transcript.**

- 9/13 turnos user → resposta GA Entendi.
- Só 3 turnos escaparam: identity (system), Flamengo opinion, Fluminense calendar (Natural).
- Após o primeiro misroute (turno 3), **todo** feedback humano virou GA.

### 2) Ele sobrescreve respostas?

**Neste transcript: não sobrescreveu Natural** — ele **ocupou** os turnos que o MasterIntent classificou como `GENERAL_CHAT`.

Mecanismo:
- MasterIntent fail-open → `GENERAL_CHAT` (0.55 / 0.75).
- HCE **não** reivindica frustração / “não entendeu” / “aurora?” / “?”.
- Sem owner emocional/meta → GA vira a resposta.

Risco estrutural pós-7.9-C: GA `assistant_kind=general` pode ser **deferred** e depois **hard-locked** (`turn_owner=GA`), o que faz o late NRF **pular** (`rewrite_locked`) — preservando Entendi.

### 3) Ele ignora contexto?

**Sim.**

Evidência de código:
```python
def reply_general(message: str) -> str:
    return (
        "Entendi. Posso te ajudar com isso de forma direta.\n\n"
        ...
    )
```
- Não lê `ctx`, histórico, último time, nem a mensagem.
- Audit: `memory_used=false` em todos os turnos GA.
- Após “Fluminense / não entendeu / último jogo”, ainda pede “me diga o time ou o confronto”.

---

## Domínio vs pipeline 7.9

| Camada 7.9 | Efeito no GA general |
|------------|----------------------|
| 7.9-A soft sections | evita KeyError; **não muda** o texto |
| 7.9-B NRF anti-loop | só muda texto se hist Entendi estiver no `ctx` **e** early NRF rodar |
| 7.9-C/D ownership | pode **travar** GA e impedir late rewrite |
| 7.9-E misroutes | cobre utility/live/emotional — **não** cobre repair/frustration |

---

## Conclusão

GeneralAssistant **é o segundo sistema conversacional defeituoso**. Não compete com engines esportivas nos turnos esportivos; **captura o restante da conversa humana** com um template cego + `skip_llm`.
