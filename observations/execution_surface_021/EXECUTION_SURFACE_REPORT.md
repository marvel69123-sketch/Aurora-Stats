# Mission 021 — Execution Surface Report

**MISSION ID:** `execution_surface_021`  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** SURFACE_EXTRACTION (documentation only)  
**CODE SoT:** `artifacts/aurora/`  
**PRIMARY MAP:** `EXECUTION_SURFACE_MAP.md`  
**PREDECESSOR:** Mission 020 (~`caed099` / `caf175f`)

**Nenhuma alteração de código: SIM**

---

## AEAP notes

| Item | Value |
|------|-------|
| Level chosen | **Level 2 — Module Audit** |
| Level 3? | **No** |
| Why L2 | Execution surface spans mega-router `_run_*`, legacy `copilot_engine`, analyze/live I/O, CM write touchpoints, and Tool Use ad-hoc calls. Mission 020 proved absence of EM module; this mission **deepens the same surface** with caller graphs and Destino Futuro classification. |
| Why not L3 | No new systemic contradiction requiring Master/SSOT re-litigation; pillar #11 already Ausente/Substituir. Evidence is module-local + adjacent. |
| Product files changed | **0** |

---

# Answers 1–15 (PO Prompt — Surface Extraction)

### 1. Which files participate in execution today?

**Primary (SoT):**

| File | Role |
|------|------|
| `artifacts/aurora/src/routers/copilot_unified_router.py` (~5260) | Orchestration + all `_run_*` |
| `artifacts/aurora/src/core/copilot_engine.py` (~841) | Legacy dispatch + `_handle_*` |
| `artifacts/aurora/src/routers/copilot_router.py` (~299) | Legacy HTTP `/chat` |
| `artifacts/aurora/src/routers/analyze.py` (~1066) | `analyze_fixture` I/O + cost cache |
| `artifacts/aurora/src/routers/live.py` | `_build_live_response` for live paths |
| `artifacts/aurora/src/ops/cost_protection.py` | Request budget + analyze cache keys |
| `artifacts/aurora/src/main.py` | Mounts both copilot routers |

**Frozen engines consumed:** `methodology_engine`, `learning_engine`, `confidence_engine`, `market_engine`, `methodology_v1`, `decision_center`, `knowledge_engine`, `intelligence_engine`, `live_intelligence_engine`.

**Adjacent:** `web_intelligence`, `partial_analysis`, `fixture_integrity`, `inference_context`, `communication` (match_card), `learning_db` / `knowledge_db` / `memory_db`, CM projections (`conversation_state.apply_after_analysis`, langgraph shadow).

**Mirror `aurora/`:** inventory awareness only (Mission 020 drift OPEN).

---

### 2. What are all `_run_*` functions?

In `copilot_unified_router.py` only:

| Function | Start line |
|----------|------------|
| `_run_analyze` | 437 |
| `_run_live` | 977 |
| `_run_bankroll` | 1020 |
| `_run_learning` | 1105 |
| `_run_knowledge` | 1185 |
| `_run_greeting` | 1239 |
| `_run_help` | 1268 |
| `_run_identity` | 1307 |
| `_run_capabilities` | 1338 |
| `_run_fallback` | 1499 |

No other `_run_*` definitions under `artifacts/aurora/src` for this surface (Mission 021 grep).

---

### 3. Who calls each `_run_*`?

All callers are inside `_copilot_inner` (same file), except helpers used by `_run_analyze` itself.

| Function | Call sites (line) | Trigger intent / condition |
|----------|-------------------|----------------------------|
| `_run_analyze` | 3864 | `analyze_match` (with home/away) |
| `_run_analyze` | 3983 | `live_team_analysis` after live match found |
| `_run_analyze` | 4182 | Outer exception / soft 404 recovery |
| `_run_live` | 4075 | `live_opportunities` |
| `_run_bankroll` | 4103 | `bankroll_review` |
| `_run_learning` | 4106 | `learning_recap` |
| `_run_knowledge` | 4109 | `knowledge_search` |
| `_run_greeting` | 4112 | `greeting` |
| `_run_identity` | 4115 | `identity` |
| `_run_capabilities` | 4118 | `capabilities` / `assistant_capabilities` |
| `_run_help` | 4121 | `help` |
| `_run_fallback` | 3813 | `analyze_match` missing entities |
| `_run_fallback` | 4124 | `else` unknown intent |

**External modules:** none import `_run_*` by name.

**Legacy analogue callers:** `copilot_router.chat` → `copilot_engine.dispatch` → `_handle_*` (not `_run_*`).

---

### 4. What belongs to the HTTP Router (must remain Router/Orchestration)?

- FastAPI handlers: `copilot` (L1664), models, response coerce.  
- `_copilot_inner` conversational stack: Master Intent, fiction/sport guards, `sport_pipeline_blocked`, CUE, HCE, continuity short follow-up, NL routing, follow-up reuse without engines.  
- Static conversational payloads: `_run_greeting`, `_run_help`, `_run_identity`, `_run_capabilities`, `_run_fallback`.  
- Post-payload presentation: formatter, personality, credibility, `_suggest_follow_ups`, match_card response coerce.  
- Session DB save / HTTP session_id lifecycle.

---

### 5. What belongs to a future Execution Manager (classification only)?

- Coordinating the **Frozen sports engine sequence** and returning a structured analyze payload: `_run_analyze` core (L543–584 + assembly of markets/confidence/stake).  
- Live opportunities execution: `_run_live`.  
- Thin “run this DB-backed report” helpers: `_run_bankroll`, `_run_learning`, `_run_knowledge`.  
- `live_team_analysis` bridge logic that ends in `_run_analyze`.  
- Analyze-only helpers: `_resolve_fixture_confidence`, `_parse_stake`, `_compose_final`, `_extract_data_sources`.

**Not claimed for EM:** intent classification, CM writers, API client internals, Frozen formulas themselves.

---

### 6. What belongs to Tool Use / data plane?

- `analyze_fixture` / `api_football_get` / analyze cache in `cost_protection`.  
- `live._build_live_response`.  
- `web_intelligence.gather_web_for_thinking` / `maybe_enrich_with_web` (ad-hoc; no registry).  
- Request-level `cost_protection.begin_request/end_request` around the HTTP turn (ops wrapping Tool Use).

---

### 7. What belongs to Context Manager (incl. contamination risk)?

- `_save_analysis_context` (L1563–1615): writes `last_home/away/match/analysis/...`, `shift_fixture_memory`, `apply_after_analysis`.  
- Inline ctx seeding on `live_opportunities` when no prior match (L4076–4089).  
- LangGraph / STS shadow adapters in `_copilot_inner` (L1821, L1861).  

**Risk:** if EM rebuild absorbs `_save_analysis_context`, it reopens CM ownership. Classify as **CM**, not EM.

---

### 8. What belongs to Frozen Engines?

Formulas and `run`/`generate`/`consult`/`build_live_payload` inside:

`methodology_engine`, `learning_engine`, `confidence_engine`, `market_engine`, `methodology_v1`, `decision_center`, `knowledge_engine`, `intelligence_engine`, `live_intelligence_engine` (+ integrity/partial modules that gate markets).

**Destino Futuro:** Engines Frozen — **consume only**.

---

### 9. Where is duplicated code?

1. **Analyze pipeline:** `_run_analyze` vs `copilot_engine._handle_analyze` vs `_handle_explain` (near-identical engine order).  
2. **Dual HTTP:** `/aurora/copilot` vs `/aurora/chat`.  
3. **Bankroll vs learning:** both `get_learning_stats` with different narrative skins.  
4. **Intent stacks:** Master/NL/CUE (unified) vs `detect_intent` regex (legacy).  
5. **Live:** intelligence engine on unified only; legacy formats raw live list.

---

### 10. Where is dead (or effectively unreachable) logic?

- **Not dead:** all `_run_*` are reachable from `_copilot_inner` branches.  
- **Avaliar / low external surface:** `_run_*` are file-private — good for extraction, not unused.  
- **Legacy explain path** may be product-low if clients only use unified `/copilot` — still **mounted** via `main.py` → treat as **legado-ativo**, not proven dead.  
- Capabilities **inline fallback** (L1344–1383) is fail-open, not dead.

---

### 11. What is legacy-only logic?

| Item | Evidence |
|------|----------|
| Entire `copilot_engine` dispatch + `_fmt_*` | Only via `copilot_router` |
| `detect_intent` regex | Legacy chat |
| `_handle_explain` re-running full engines | No unified `_run_explain` equivalent (unified uses follow-up reuse / continuity) |
| Live without `live_intelligence_engine` | `_handle_live` |
| String responses vs structured `CopilotResponse` | Legacy chat contract |

---

### 12. Where is excessive coupling?

- Single file couples: HTTP + Understanding + Orchestration + EM-equivalent `_run_*` + CM context writes + Tool Use web enrich.  
- `_run_analyze` couples: Tool Use fetch + integrity + Frozen engines + inference/partial + DRS + UI narrative + match_card.  
- Callers couple post-integrity + `_save_analysis_context` to dispatch success path.  
- Any future EM edit today means editing the highest-risk conversation file (~5260 LOC).

---

### 13. Where are mixed responsibilities?

| Blob | Mix |
|------|-----|
| `_run_analyze` | EM + Tool Use call + payload/UI + data richness stamp |
| `_copilot_inner` dispatch | Router decision + EM invoke + CM save |
| `copilot()` wrapper | Router + ops cost_protection |
| `_run_live` | Tool Use live feed + EM live engine + match_card |
| Greeting/help `_run_*` | Named like EM helpers but **Router** conversational content |

---

### 14. What must stay (descriptive — not Spec)?

- Current Frozen **sequence and analyze payload semantics** users/clients rely on.  
- Soft analyze + integrity INVALID/PARTIAL behaviour.  
- Fail-open conversational layers around sport pipeline.  
- Cost protection budget/cache defaults.  
- Context Manager FROZEN boundaries (do not move sole-write into EM).  
- Engines listed in `docs/FROZEN_MODULES.md` untouched as formulas.  
- Unified structured response fields for integration clients.

---

### 15. What to extract later (classification — not Spec / not rebuild)?

| Extract candidate | Destino Futuro |
|-------------------|----------------|
| `_run_analyze` body (engine orchestration + structured assembly) | **EM** |
| `_run_live` (+ live_team bridge) | **EM** |
| Thin `_run_bankroll` / `_run_learning` / `_run_knowledge` | **EM** (or Avaliar thin reports) |
| Analyze helpers (`_resolve_fixture_confidence`, `_parse_stake`, `_compose_final`) | **EM** util |
| `_save_analysis_context` ownership clarification | **CM** (not EM) |
| `analyze_fixture` / live feed / web | **Tool Use** adapters |
| `copilot_engine` + `/chat` | **Legado** retirement mission |
| Greeting/help/identity/capabilities `_run_*` | Stay **Router** (rename/classify; not EM) |

**Explicit non-starts:** Spec, architecture proposal, comparative research, product code, EM rebuild.

---

# Dual Reporting

---

# REPORT 1 — ENGINEERING REPORT

## Identity

| Field | Value |
|-------|-------|
| Mission | 021 SURFACE_EXTRACTION — Future Execution Manager |
| Branch | `feat/aurora-response-selector-001` |
| Commit message | `docs(research): add Execution Surface Map` |
| Commit hash | *(filled after commit)* |
| Push | *(filled after push)* |
| Product code | **Nenhuma alteração de código: SIM** |
| Deliverables | `observations/execution_surface_021/EXECUTION_SURFACE_MAP.md`, `EXECUTION_SURFACE_REPORT.md` |

## Scope

| In | Out |
|----|-----|
| Execution Surface Map + Q&A 1–15 | Spec / ADR / Blueprint / Master edits |
| Layer diagram + `_run_*` inventory + callers | Comparative research |
| Destino Futuro classification only | EM rebuild / product mutation |
| AEAP L2 | Level 3; mirror drift fix |

## Evidence method

- Reused Mission 020 verdict (no `execution_manager` module).  
- Grep/read SoT: all `_run_*` defs + call sites; `copilot_engine` `_handle_*`; `main.py` mounts; `analyze.py` cost/API; web_intelligence; `_save_analysis_context`; langgraph shadow.  
- LOC: unified 5260; engine 841; legacy router 299; analyze 1066.

## Architecture / governance

- Master / Spec / ADRs / Blueprint: **not modified**.  
- Context Manager: **FROZEN** — classified contamination risks only.  
- REGRA 29: this Dual Reporting block.  
- Next: **await PO** — do not start Spec / comparative research / rebuild.

## Safety

- Docs-only under `observations/execution_surface_021/`.  
- Rollback = revert docs commit.  
- No flags / runtime change.

## Validations

| Check | Result |
|-------|--------|
| EXECUTION SURFACE MAP table | YES |
| RESPONSIBILITY MAP layers | YES |
| Q&A 1–15 | YES |
| AEAP L2 justified; L3 not used | YES |
| Code unchanged | YES |
| Spec / rebuild started | **NO** |

## Residual / next

- PO review of Surface Map.  
- Optional later (only if PO authorizes): Research/Spec EM with Tool Use + CM boundaries.  
- Mirror drift remains OPEN (Activation residual).

## Top 5 surface findings

1. **Ten `_run_*` helpers** live only in `copilot_unified_router.py`; sport-heavy EM candidates are `_run_analyze` / `_run_live` (+ live_team bridge); greeting/help/identity/capabilities/fallback are **Router**, not EM.  
2. **Callers are exclusively `_copilot_inner`** (3× `_run_analyze`, 1× each other intent branch) — encapsulation-ready, but coupled to integrity + `_save_analysis_context`.  
3. **Legacy triple duplication** of analyze engines: unified `_run_analyze` ≈ `_handle_analyze` ≈ `_handle_explain`.  
4. **CM contamination:** `_save_analysis_context` + live ctx seed + langgraph shadow sit on the execution surface but are **not** EM.  
5. **Tool Use adjacents** (`analyze_fixture`, live feed, web_intelligence, cost_protection) are invoked from/around run paths without a registry — classify out of core EM.

---

# REPORT 2 — PRODUCT OWNER REPORT

📋 PRODUCT OWNER REPORT

✅ O que fizemos hoje

Mapeamos, com precisão, **onde a Aurora executa de fato** as análises e os caminhos relacionados (ao vivo, banca, aprendizado, etc.). Produzimos um mapa de superfície e um relatório completo — **sem mudar o produto** e **sem desenhar a solução nova**.

🧠 O que isso significa

Já sabíamos (missão anterior) que o “Execution Manager” **não existe como peça separada**. Agora sabemos **exatamente quais funções e arquivos** fazem esse trabalho hoje, quem chama quem, o que é conversa/roteador, o que seria futuro “executor”, o que é ferramenta/API, o que toca contexto, e o que são motores congelados. Isso prepara uma decisão futura segura — ainda **não autorizada**.

👤 O usuário percebe diferença?

**Não.** Só documentos de pesquisa. Nenhuma mudança de comportamento.

⚠️ Existe algum risco?

Risco desta missão: **baixo** (somente documentação).  
Risco que o mapa deixa claro para o futuro: misturar “executar motores” com “gravar contexto da conversa” ou com “chamar APIs” pode quebrar análise ou reabrir o Context Manager. Por isso a próxima etapa depende da sua autorização.

🎯 O que ainda falta?

- Sua leitura e aprovação deste mapa de superfície.  
- Só depois (se você autorizar): pesquisa/especificação do Execution Manager.  
- Continuar **sem** iniciar reconstrução, Spec ou pesquisa comparativa até o seu OK.

📊 Quanto falta?

Para **esta** Missão 021 (mapear a superfície de execução): concluída após commit/push.

```text
████████████████████  100%
```

(A reconstrução do Execution Manager permanece em **0%** — deliberadamente não começou.)

🏗️ Analogia simples

Na missão anterior descobrimos que a “cozinha” está no meio da sala de atendimento. Nesta, fizemos o **inventário de cada fogão, panela e quem liga o gás**: o que fica na recepção, o que um dia vai para a cozinha, o que é geladeira (dados/API), o que é livro de receitas congelado (motores), e o que é a memória de “qual prato o cliente pediu” (contexto) — **sem reformar nada**.

📝 Resumo em uma frase

Mapeamos onde a execução vive hoje (funções `_run_*`, legado e fronteiras) — só documentação, produto intacto, aguardando o Product Owner.
