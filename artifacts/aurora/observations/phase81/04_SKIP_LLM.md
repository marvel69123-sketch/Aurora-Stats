# Fase 8.1 — skip_llm

---

## Quando ativa?

`skip_llm=True` é setado em entities por short-circuits conversacionais, entre outros:

| Origem | Condição típica |
|--------|-----------------|
| `general_assistant._payload` | qualquer resposta GA |
| `human_conversation_engine._payload` | HCE |
| `emotional_presence` | presença emocional |
| `natural_response_engine` (social direct) | ACK/farewell etc. |
| `intelligence_fallback` / `conversation_focus` / `user_profile_memory` | caminhos soft |

No transcript: **todos** os turnos Entendi têm `entities_snapshot.skip_llm = true`.

---

## Quem ativa? (neste caso)

`GeneralAssistant._payload` → `try_general_assistant` → router early stack.

Router também respeita o flag em presença/LLM gates (`_skip_llm_presence` / entidades / meta) para **não** chamar rewrite LLM.

---

## Por quê?

Design: respostas “sociais / utilitárias / presença” devem ser baratas, determinísticas e não passar pelo chat LLM esportivo.

Efeito colateral: o default GA (`reply_general`) **nunca** é enriquecido por modelo — sempre o mesmo parágrafo.

---

## Quais efeitos produz?

| Efeito | Evidência |
|--------|-----------|
| Resposta instantânea template | 9× Entendi idêntico |
| Zero adaptação à frustração | “inútil / loop / para” → mesmo texto |
| Zero uso de memória curta na geração | `memory_used=false` |
| Anti-loop depende só de NRF/hist, não de LLM | se hist frio → loop infinito de template |
| `fallback_used=false` no audit | skip_llm GA **não** conta como fallback — mascara degradação |

---

## Conclusão

`skip_llm` não é bug por si. No caminho GA general, ele **congela** o pior template do sistema e impede recovery inteligente. No transcript, é o multiplicador do loop.
