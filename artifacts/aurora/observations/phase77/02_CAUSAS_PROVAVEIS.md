# Fase 7.7 — Documento 2: Causas Prováveis

---

## A) Loop `"Entendi. Posso te ajudar…"`

| # | Causa | Evidência | Prob. |
|---|--------|-----------|-------|
| A1 | `reply_general()` é template fixo sem variação | `general_assistant.py:190-195` | Alta |
| A2 | `GENERAL_CHAT` sempre cai nesse template (exceto oi/ola) | `try_general_assistant` 217-224 | Alta |
| A3 | NRF detecta similaridade e “regenera” com o **mesmo** `reply_general` | `natural_response_filter.py:61-75,147-180` + router late NRF | **Muito alta** |
| A4 | Early NRF no GA usa `regenerate=_txt` (mesmo texto) | router ~1631-1636 | Alta |
| A5 | Ownership GA às vezes não trava late NRF (ou forced path sem lock) | forced incomplete payload sem `finalize_early_ownership` | Média-Alta |

**Não é recursão de stack.** É **loop sticky entre turnos**: mesmo template → similar → regenerate → mesmo template.

---

## B) Erro `[error] 'confidence'`

| # | Causa | Evidência | Prob. |
|---|--------|-----------|-------|
| B1 | `ConfidenceSection(**payload["confidence"])` sem guarda | router final ~3628 | Certa (ponto de crash) |
| B2 | Forced nonsport dict **omite** `confidence` / `risk` / `bankroll_recommendation` | router ~2415-2430 | **Muito alta** |
| B3 | MEMORY_QUERY → GA retorna None → forced path incompleto | `general_assistant.py:214-216` | Alta |
| B4 | Shells de exceção DT/HPL sem confidence | router DT block; `human_presence.py` | Média |

Impacto: request inteiro falha → frontend vê erro genérico → usuário reforma → mais fallback → fricção.

---

## C) Inteligência percebida baixa vs inteligência interna

| # | Causa | Evidência |
|---|--------|-----------|
| C1 | Respostas válidas de sport/emotional substituídas por late polish / NeverEmpty / NRF | ownership só no early stack |
| C2 | Intent correta no Master, mas payload final = GA general | perda após intent |
| C3 | `_run_fallback` brochure para intents desconhecidas | router dispatch else |
| C4 | Emotional/HPL sem `rewrite_locked` | ResponseReview/credibility podem tocar |

---

## D) Gargalo — respostas objetivas

1. **Quem aciona o fallback?**  
   - Early: `intelligence_fallback.try_intelligence_fallback`  
   - Mid: forced nonsport (`reply_general` / dict incompleto)  
   - Dispatch: `_run_fallback`  
   - Late: `natural_response_filter.filter_or_regenerate`  
   - Outer: exception → Inference V2 soft payload  

2. **Quando?**  
   - `payload is None` + condições de cada camada; ou template similar; ou intent unknown; ou exception.

3. **Existe sobrescrita de respostas?**  
   **Sim** — late NRF, NeverEmpty, ResponseReview, credibility, LLM chat, emotional guard, PIE (se unlocked).

4. **Respostas válidas estão sendo descartadas?**  
   **Provável sim** quando late layers regeneram com `reply_general` ou NeverEmpty filler; ownership gap facilita.

5. **Existe curto-circuito?**  
   **Sim** — early Master→GA→HCE→NRE com lock; e forced nonsport que bloqueia NL/sport. O problema é o curto-circuito **ruim** (Entendi) + crash de schema.
