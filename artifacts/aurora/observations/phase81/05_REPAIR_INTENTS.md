# Fase 8.1 — Conversation Repair Intents

---

## Intents pedidas vs existência

| Intent / classe | Existe como intent Master/Natural? | Existe handler próximo? | Cobriu o transcript? |
|-----------------|------------------------------------|-------------------------|----------------------|
| `conversation_repair` | **Não** | Não | — |
| `clarification` | Parcial (`message_intelligence` / confidence clarify) | Clarificação de fixture/confiança | **Não** nos turns de frustração |
| `user_confusion` | **Não** | Não | — |
| `meta_feedback` | **Não** | Não | — |
| `frustration` | **Não** | Emotional tem tristeza/apoio; **não** “você é inútil / para de loop” | Não |
| `conversation_rescue` | **Não** | Não | — |

---

## Exemplos do transcript × roteamento real

| User | Esperado (humano) | Intent real | Handler |
|------|-------------------|-------------|---------|
| nao voce nao entendeu oque eu quis dizer | repair / reask | `general_chat` conf 0.55 | `reply_general` |
| pensa um pouco no que eu estou dizendo aurora | repair / think | `general_chat` 0.55 | `reply_general` |
| aurora? | presence / ping | `general_chat` 0.75 | `reply_general` |
| ? | clarify | `general_chat` 0.75 | `reply_general` |
| cara voce e muito inutil serio | frustration | `general_chat` 0.75 | `reply_general` |
| paraaa de fica em loop | anti-loop / repair | `general_chat` | `reply_general` |
| pare imediamente | stop / repair | `general_chat` | `reply_general` |
| cansei de testar | exit / frustration | `general_chat` | `reply_general` |

---

## Meta que existe — e o que não é

`meta_question_handler.is_meta_question` cobre:
- fonte dos dados / confiança / “por que você acha” / “está inventando”

**Não cobre:**
- “não entendeu”, “pensa um pouco”, “aurora?”, “?”, loop, inutilidade, parar.

HCE chama meta só via esse regex (`human_conversation_engine`).

---

## MasterIntent

`master_intent_router.py` intents:
`SMALL_TALK | GENERAL_CHAT | SPORT_QUERY | LIVE_MATCH | MEMORY_QUERY | MATH_QUERY | SYSTEM_QUERY | UTILITY_QUERY | EMOTIONAL_QUERY`

Fail-open:
- ≤6 tokens → `GENERAL_CHAT` 0.75 `short_general`
- resto nonsport → `GENERAL_CHAT` 0.55 `default_general`

Nenhum branch de repair/frustration.

---

## Conclusão

**Essas intents de repair/frustration/meta-feedback não existem** no roteador.  
O usuário pediu recovery conversacional; o sistema só tinha `GENERAL_CHAT` → Entendi.
