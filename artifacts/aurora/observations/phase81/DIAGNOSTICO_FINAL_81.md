# Fase 8.1 — Diagnóstico Final

**Modo:** INVESTIGAÇÃO FORENSE — zero implementação  
**Transcript:** `aurora_audit_20260718_002712.json` (sessão `vgpnk4k2`)  
**Relatórios:** `01`…`08` neste diretório

---

## PROBLEMA

↓

Em uso real, a conversa **degrada em poucos turnos**: misroute esportivo (opinião → agenda), depois loop idêntico de  
“Entendi. Posso te ajudar com isso de forma direta.”, sem repair/meta, com usuário frustrado — apesar dos testes 7.9-A…E terem passado.

---

## CAUSA RAIZ

↓

**Dois sistemas em paralelo; o segundo ainda é o gargalo.**

1. **Sistema A (esporte / Natural)** — parcialmente estabilizado nas 7.9, mas com bug semântico residual: regex de `team_calendar` (`jogo do`) captura pedidos de opinião retrospectiva **antes** de `team_opinion`; `ontem`/`último jogo` não viram kind dedicado (`last_match_opinion` **inexiste**).

2. **Sistema B (GeneralAssistant / `reply_general` + `skip_llm`)** — default hardcoded para quase todo `GENERAL_CHAT`. Não há intents de repair/frustration/meta-feedback. Qualquer “não entendeu / aurora? / ? / loop / inútil” vira Entendi cego.

3. **Anti-loop 7.9-B** — depende de `recent_assistant_replies` no `ctx`. Em produção Autoscale + reload SQLite via `ConversationContext` (que **descarta** chaves extras), o hist esfria; late NRF ainda pode ser skipped se GA estiver `rewrite_locked`. Resultado: Entendi×N igual ao pré-patch.

4. **Por que os testes passaram:** smokes 7.9 validam patches isolados (confidence, NRF com hist quente, ownership, misroutes utility/live/emotional). **Não** reproduzem a combinação real: opinion→calendar + frustração sem repair + GA skip_llm + hist frio / deploy timing.

---

## EVIDÊNCIA

↓

| Evidência | Onde |
|-----------|------|
| 9× texto Entendi byte-idêntico | messages do audit |
| `sources=["GeneralAssistant"]`, `assistant_kind=general`, `skip_llm=true` | diagnostics turns 1,4,6–12 |
| Fluminense: `natural_kind=team_calendar`, `calendar_date=2026-07-18` | turn 3 e 5 |
| Regex calendar antes de opinion; só `amanha` em offset | `natural_conversation.py` |
| `reply_general` ignora `message`/`ctx` | `general_assistant.py` |
| Sem intents repair/frustration | `master_intent_router.py` + grep |
| Meta HCE só fonte/confiança | `meta_question_handler.py` |
| Hist anti-loop só em NRF; strip no from_dict | `natural_response_filter.py` + `conversation_context.py` |
| Sem markers 7.9 no entities export | audit `entities_snapshot` |
| `memory_used=false` em todos os turns | audit |

---

## GRAVIDADE

↓

**P0 conversacional** — quebra percepção de inteligência em sessão real curta (<6 min).  
Misroute Fluminense = **P0 produto**.  
Ausência de repair = **P0 experiência**.  
Lacuna de teste vs produção = **P0 processo**.

---

## RISCO

↓

- Patches 7.9 criam **falsa confiança** (“testes 100%”) enquanto o caminho dominante do chat humano continua sendo GA template.
- Ownership lock em GA pode **piorar** o sticky se late NRF for skipped e hist estiver frio.
- Usuário aprende que correção verbal (“não entendeu”) **não funciona** → abandono.

---

## RECOMENDAÇÃO

↓

*(Somente direção — **não implementar nesta fase**)*

1. Tratar **GeneralAssistant general** como gargalo P0: deixar de ser default cego; exigir kind/contexto ou repair.
2. Precedência Natural: `achou` + `jogo` + `ontem/último` → opinion/last-match, **nunca** calendar-hoje.
3. Intents mínimas: `conversation_repair` / frustration / ping (`aurora?` / `?`).
4. Anti-loop: não depender só de hist volátil; detectar Entendi×N na própria sessão de mensagens ou bloquear reemit do template.
5. Harness de regressão = **replay deste transcript** (não só probes 7.9-E).

---

## Cenário C ou novo gargalo?

### Resposta explícita

**Ainda Cenário C no eixo conversacional (sticky Entendi / fallback GA),**  
**e as correções 7.9 revelaram / deixaram exposto um gargalo adicional:**

| Camada | Estado |
|--------|--------|
| KeyError confidence (7.9-A) | tratado no código; não é o sintoma deste transcript |
| NRF anti-loop (7.9-B) | **não efetivo nesta sessão real** |
| Ownership (7.9-C/D) | markers ausentes no export; não salvou a UX |
| Misroutes utility/live/emo (7.9-E) | fora do caminho deste transcript |
| **Novo foco claro** | Natural `team_calendar` vs opinion + **vácuo total de repair** + GA `skip_llm` |

**Não é “precisa de modelo maior”.**  
É o **segundo sistema conversacional** (GA + falta de repair + misroute calendar) dominando o uso real.

---

## Pergunta final

> Por que a Aurora continua parecendo ruim mesmo após todas as correções estruturais?

Porque as correções estabilizaram **falhas de pipeline/ownership/NRF em testes controlados**, mas o turno humano típico ainda cai em **`GENERAL_CHAT` → `reply_general` (Entendi) com `skip_llm`**, sem memória de assunto e sem intent de recovery — e o pedido de opinião do Fluminense ainda é engolido por **agenda**. O usuário sente estupidez e loop; os testes não olhavam para essa conversa.

---

## 1 INVESTIGAÇÃO = 1 CONCLUSÃO

**Conclusão única:** o mau uso real não refuta 7.9-A…E como patches locais; prova que o gargalo dominante restante é o **GeneralAssistant + ausência de repair + misroute calendar/opinion**, ainda dentro do Cenário C conversacional.

**Parada aqui. Nenhum código modificado.**
