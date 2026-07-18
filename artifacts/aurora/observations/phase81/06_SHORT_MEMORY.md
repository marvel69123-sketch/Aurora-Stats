# Fase 8.1 — Memória Curta

---

## O que existe no código

| Mecanismo | Onde | Escopo |
|-----------|------|--------|
| `ConversationManager` + SQLite | `conversation_context.py` / `chat_db.py` | last_match, last_analysis, profile, turns… |
| `conversation_state` | `conversation_state.py` | estado esportivo / follow-ups de mercado |
| `human_conversation_state` (HCE) | HCE | await fixture / bankroll |
| `recent_assistant_replies` | **somente** NRF `note_assistant_reply` | anti-similaridade / anti-loop |
| DeepThinking topic | brain_authority | topic_team / calendar authority |

---

## Respostas obrigatórias

### A Aurora lembra da mensagem anterior?

**Parcialmente na infra; não no path GA deste transcript.**

- Audit: `memory_used=false` em todos os turns.
- Após Fluminense, GA responde como se não houvesse assunto.
- `reply_general` não consulta `ctx`.

Fragilidade estrutural (código):
1. Autoscale sem sticky session → memória best-effort (`conversation_context.py` docstring).
2. `ConversationManager.get` via SQLite faz `ConversationContext.from_dict(...).to_dict()` → **descarta** chaves extras (`recent_assistant_replies`, estados HCE, etc.) no reload frio.

### Ela sabe o assunto atual?

**Só quando Natural/Sport preenche entities.**

| Turno | Assunto real do user | O que o sistema “sabia” |
|-------|----------------------|-------------------------|
| 2 | Flamengo opinion | `team=Flamengo`, `team_opinion` |
| 3–5 | opinião último jogo Fluminense | `team_calendar` + data **hoje** |
| 4+ | correção / frustração | **nada** — GA sem topic |

Não há `last subject memory` consumido por GA/repair.

### Ela sabe quando errou?

**Não.**

- “nao voce nao entendeu” → `general_chat`, sem flag de repair, sem `recovery_mode`.
- Não há estado `repair_state` / `user_said_misunderstood`.
- Loop de Entendi trata cada turno como pedido novo genérico.

---

## Conclusão

Memória curta existe para **análise esportiva / follow-up de mercado**, não para **continuidade conversacional humana**. No transcript, a Aurora “esquece” o pedido de opinião e o pedido de correção no instante em que cai no GA.
