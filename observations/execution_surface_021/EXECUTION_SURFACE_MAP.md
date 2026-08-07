# Mission 021 — Execution Surface Map (SURFACE_EXTRACTION)

**MISSION ID:** `execution_surface_021`  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** SURFACE_EXTRACTION / diagnostic (documentation only)  
**CODE SoT:** `artifacts/aurora/`  
**MIRROR:** `aurora/` — awareness only; **drift not fixed**  
**PREDECESSOR:** Mission 020 (`observations/execution_manager_discovery_020/`)  
**STATUS:** COMPLETE (docs only)

**Nenhuma alteração de código: SIM**

---

## Scope lock

| Allowed | Forbidden |
|---------|-----------|
| Map where future EM responsibilities live **today** | Product code / Spec / ADR / Blueprint edits |
| Classify Destino Futuro (Router / EM / Tool Use / CM / Engines Frozen / Avaliar / Legado) | Architecture proposal or rebuild |
| Deep inventory of `_run_*`, callers, adjacent I/O | Comparative research mission |
| AEAP Level 2 Module Audit | Level 3 unless systemic evidence (not found) |

---

## AEAP

```text
AUDIT BUDGET
Nível escolhido: LEVEL 2 (Module Audit)
Elevação L3: NÃO — superfície é o blob de execução já delimitado em Mission 020;
  Master/SSOT não precisam reabrir.
Arquivos novos (produto): 0
Arquivos modificados (produto): 0
Arquivos SoT lidos / grepped (amostra principal):
  copilot_unified_router.py (~5260 LOC)
  copilot_engine.py (~841 LOC)
  copilot_router.py (~299 LOC)
  analyze.py (~1066 LOC)
  live.py (call sites), cost_protection, web_intelligence touchpoints
Reuso: Mission 020 Discovery; Audit 001 §3.10–3.12; FROZEN_MODULES; conversation_pipeline
```

---

## 1. EXECUTION SURFACE MAP

| Responsabilidade | Local Atual | Destino Futuro | Observações |
|------------------|-------------|----------------|-------------|
| HTTP entry unified Copilot | `copilot_unified_router.copilot` L1664–1729 | **Router** | `POST /aurora/copilot`; wraps `_copilot_inner` + `cost_protection.begin/end_request` |
| HTTP entry legacy chat | `copilot_router.chat` L105–180 | **Legado** | `POST /aurora/chat` → `detect_intent` + `dispatch` |
| Mount both routers | `main.py` L115–116 | **Router** | Dual surface; both under `/aurora` |
| Conversational Orchestration (intent/guards/layers) | `_copilot_inner` L1732+ (majority of file) | **Router** (Orchestration) | Master Intent, sport_pipeline_blocked, CUE, HCE, continuity — **not** EM |
| Intent → pipeline dispatch (unified) | `_copilot_inner` branches L3785–4124 | **Avaliar** → split | Dispatch *decision* stays Router/Orchestration; *execution* body → EM later |
| Full analyze engine sequence | `_run_analyze` L437–974 | **EM** | methodology→learning→confidence→market→methodology_v1→decision_center→knowledge→intelligence |
| Soft fixture fetch before engines | `_run_analyze` → `analyze_fixture` L460–469 | **Tool Use** / data plane | I/O owned by `routers/analyze`; EM *invokes*, does not *be* the client |
| Integrity INVALID early abort | `_run_analyze` L502–527 + caller L3851–3873 | **Avaliar** | Gate before engines; formula in `fixture_integrity` (Frozen-adjacent); sequencing today in router/EM blob |
| Partial / confidence / stake assembly | `_run_analyze` L586–808 | **EM** (orchestration of results) + **Router** (payload shape) | Mixed: inference penalty + UI fields in same function |
| Match card attach (analyze) | `_run_analyze` L962–973 | **Router** / FE contract | `communication.attach_match_card` — presentation adapter |
| Live opportunities pipeline | `_run_live` L977–1017 | **EM** | Calls `live._build_live_response` + `live_intelligence_engine.build_live_payload` |
| Live fixture feed I/O | `routers/live._build_live_response` (via `_run_live` L983) | **Tool Use** / data | Not engine formula |
| Live team → analyze bridge | `_copilot_inner` `live_team_analysis` L3949–4064 | **EM** (+ Tool Use for live search) | Searches live list then `_run_analyze(..., prefer_live=True)` |
| Bankroll review payload | `_run_bankroll` L1020–1102 | **EM** (thin) | `learning_db.get_learning_stats` + narrative assembly; no Frozen sports engines |
| Learning recap payload | `_run_learning` L1105–1182 | **EM** (thin) | Near-duplicate of bankroll data source |
| Knowledge search payload | `_run_knowledge` L1185–1236 | **EM** (thin) / **Avaliar** | `knowledge_db.search_knowledge_items` — DB query, not sports engines |
| Greeting / help / identity / capabilities | `_run_greeting` L1239, `_run_help` L1268, `_run_identity` L1307, `_run_capabilities` L1338 | **Router** | Conversational static/capability payloads; not engine execution |
| Unknown / fallback payload | `_run_fallback` L1499+ | **Router** | Helpful tip payload when intent unknown |
| Follow-up suggestions | `_suggest_follow_ups` L1386–1496 | **Router** | UX hints; not EM |
| Persist analysis into session ctx | `_save_analysis_context` L1563–1615 | **CM** (contamination risk) | Writes `last_*`, calls `shift_fixture_memory`, `conversation_state.apply_after_analysis` |
| Inline ctx seed on live | `_copilot_inner` L4076–4089 | **CM** (contamination risk) | Direct `ctx["last_match"]` writes outside sole-writer funnel |
| LangGraph STS shadow | `_copilot_inner` L1821, L1861 | **CM** | `langgraph_state_adapter` — context path; **not** EM |
| `sport_pipeline_blocked` flags | many sites ~L1919–2551 | **Router** / Understanding | Blocks whether `_run_*` sport path runs |
| Cost protection request scope | `copilot` L1723–1729 | **Tool Use** / ops | Wrap around whole turn; analyze cache inside `analyze.py` |
| Analyze cache / API-Football | `analyze.py` (~L556–651, `api_football_get`) | **Tool Use** / ops / data | Called from `_run_analyze` and legacy `_handle_analyze` |
| Web gather / enrich | `_copilot_inner` L2734–2738, L4594–4603 | **Tool Use** | Ad-hoc; skip for match_analysis engines path on gather |
| Legacy analyze sequence | `copilot_engine._handle_analyze` L701–757 | **Legado** | Same engine order; returns formatted **string**, not structured payload |
| Legacy explain (re-run engines) | `copilot_engine._handle_explain` L760–811 | **Legado** | Third copy of engine sequence |
| Legacy live/bankroll/learning/knowledge | `copilot_engine._handle_*` L814–841 | **Legado** | Parallel thin handlers + `_fmt_*` |
| Legacy intent regex | `copilot_engine.detect_intent` L200+ | **Legado** | Coexists with Master Intent / NL on unified |
| Frozen engine formulas | `methodology_engine`, `learning_engine`, `confidence_engine`, `market_engine`, `methodology_v1`, `decision_center`, `knowledge_engine`, `intelligence_engine`, `live_intelligence_engine` | **Engines Frozen** | Consumed by EM blob; **do not rewrite as EM** |
| Helpers conf/stake/compose | `_resolve_fixture_confidence` L281, `_parse_stake` L326, `_compose_final` L392 | **EM** (or shared util) | Used only by `_run_analyze` path today |
| Follow-up reuse (no re-engine) | `_copilot_inner` follow-up gates ~L3429–3731 | **Router** | Reuses `last_analysis`; skips `_run_*` when FOLLOWUP_REUSED |

---

## 2. RESPONSIBILITY MAP (layers)

```text
HTTP ROUTER
├── PERMANECE (Orchestration / HTTP / conversation)
│   ├── copilot() — request bind, session_id, cost_protection request scope
│   ├── _copilot_inner — Master Intent, guards, CUE/HCE/continuity, NL route
│   ├── sport_pipeline_blocked / non-sport forced paths
│   ├── follow-up reuse (last_analysis) without re-running engines
│   ├── response layers (formatter, personality, credibility, match_card coerce)
│   ├── _run_greeting / _run_help / _run_identity / _run_capabilities / _run_fallback
│   └── _suggest_follow_ups
│
├── EXTRAIR DEPOIS (candidato Execution Manager — classificação, não Spec)
│   ├── _run_analyze — sequência Frozen + assembly estruturado
│   ├── _run_live — live feed → live_intelligence_engine
│   ├── live_team_analysis bridge (live search → _run_analyze)
│   ├── _run_bankroll / _run_learning / _run_knowledge (thin DB→payload)
│   └── helpers: _resolve_fixture_confidence, _parse_stake, _compose_final, …
│
├── CONTAMINAÇÃO / FRONTEIRA CM (não é EM)
│   ├── _save_analysis_context (+ apply_after_analysis / shift_fixture_memory)
│   ├── ctx seed em live_opportunities (last_match/home/away)
│   └── langgraph_state_adapter shadow (STS / CM)
│
├── TOOL USE / DATA (adjacente; não core EM)
│   ├── analyze_fixture / api_football_get / analyze cache (cost_protection)
│   ├── live._build_live_response
│   └── web_intelligence gather + maybe_enrich
│
└── LEGADO (paralelo)
    ├── copilot_router.chat
    └── copilot_engine.dispatch / _handle_* / detect_intent / _fmt_*

ENGINES FROZEN (consumidos; permanecem fora do EM como lógica)
└── methodology → learning → confidence → market → methodology_v1
    → decision_center → knowledge → intelligence (+ live_intelligence)
```

---

## 3. Inventory — `_run_*` functions (SoT)

| Function | Lines | Sync | Primary callee(s) | External deps (evidence) |
|----------|-------|------|-------------------|---------------------------|
| `_run_analyze` | 437–974 | async | `_copilot_inner` L3864, L3983, L4182 | `analyze_fixture`; Frozen engines; `partial_analysis`; match_card; DRS stamp |
| `_run_live` | 977–1017 | async | `_copilot_inner` L4075 | `live._build_live_response`; `live_intelligence_engine.build_live_payload`; match_card |
| `_run_bankroll` | 1020–1102 | sync | `_copilot_inner` L4103 | `learning_db.get_learning_stats` |
| `_run_learning` | 1105–1182 | sync | `_copilot_inner` L4106 | `learning_db.get_learning_stats` |
| `_run_knowledge` | 1185–1236 | sync | `_copilot_inner` L4109 | `knowledge_db.search_knowledge_items` |
| `_run_greeting` | 1239–1265 | sync | `_copilot_inner` L4112 | `communication.official_greeting_*` |
| `_run_help` | 1268–1304 | sync | `_copilot_inner` L4121 | static strings |
| `_run_identity` | 1307–1335 | sync | `_copilot_inner` L4115 | `AURORA_TAGLINE` |
| `_run_capabilities` | 1338–1383 | sync | `_copilot_inner` L4118 | `assistant_capabilities.build_capabilities_payload` (fallback inline) |
| `_run_fallback` | 1499+ | sync | `_copilot_inner` L3813, L4124 | tip payload |

**Call graph (unified only):** all `_run_*` are **private** to `copilot_unified_router.py`. No other SoT module imports them by name (grep Mission 021). Entry is exclusively via `_copilot_inner` intent branches (plus entity-incomplete analyze using `_run_fallback`).

---

## 4. Legacy parallel inventory

| Symbol | File:lines | Called by | Notes |
|--------|------------|-----------|-------|
| `detect_intent` | `copilot_engine.py` ~200 | `copilot_router.chat` L141 | Regex/legacy intent |
| `dispatch` | `copilot_engine.py` 655–698 | `copilot_router.chat` L154 | Routes to `_handle_*` |
| `_handle_analyze` | 701–757 | `dispatch` | Engine sequence ≈ `_run_analyze` (string out) |
| `_handle_explain` | 760–811 | `dispatch` | **Second** full engine re-run for explain |
| `_handle_live` | 814–817 | `dispatch` | Live feed only; **no** `live_intelligence_engine` |
| `_handle_bankroll` / `_handle_learning` / `_handle_knowledge` | 820–841 | `dispatch` | Thin DB + `_fmt_*` |
| `_fmt_*` | 252–637 | handlers | Markdown/NL string formatting |

**Behavioral gap (map, not Spec):** unified live uses `live_intelligence_engine`; legacy live formats raw `_build_live_response` only.

---

## 5. Engine call sites (Frozen)

### Unified `_run_analyze` order (L543–584)

1. `methodology_engine.run`  
2. `learning_engine.run`  
3. `confidence_engine.run`  
4. `market_engine.run`  
5. `methodology_v1.run`  
6. `decision_center.run`  
7. `memory_db.recall_context` + `knowledge_engine.consult`  
8. `intelligence_engine.generate`  

### Legacy `_handle_analyze` / `_handle_explain` (L729–756 / L788–810)

Same core order; fewer integrity/partial/DRS/match_card surrounds.

### Live

- Unified: `live_intelligence_engine.build_live_payload` inside `_run_live`  
- Legacy: **not** called  

---

## 6. Tool / API / cache call sites inside run paths

| Site | Classification |
|------|----------------|
| `_run_analyze` → `analyze_fixture` (soft, force_refresh) | Tool Use / data |
| `analyze.py` → `api_football_get`, `cost_protection.analyze_cache_*` | Tool Use / ops |
| `_run_live` / live_team → `_build_live_response` | Tool Use / data |
| `copilot` → `cost_protection.begin_request/end_request` | Ops wrap (Router + Tool Use) |
| `web_intelligence` gather (pre-draft) / enrich (post-payload) | Tool Use (outside `_run_*` bodies) |

---

## 7. Context Manager touchpoints inside execution surface

| Touchpoint | Risk |
|------------|------|
| `_save_analysis_context` after successful analyze / live_team | **CM contamination** if future EM owns writers |
| Direct `ctx["last_*"]` on live_opportunities seed | Same |
| `conversation_state.apply_after_analysis` from `_save_analysis_context` | CM projection |
| `langgraph_state_adapter` shadow in `_copilot_inner` | CM — orthogonal to engine run |
| `sport_pipeline_blocked` | Orchestration gate — not CM sole-writer, but decides if EM-equivalent runs |

**Classification rule for this map:** context *commit* / subject persistence → **CM**; engine *sequence* → **EM**; HTTP/conversation layers → **Router**.

---

## 8. Duplication / dead / legacy-only (surface view)

| Kind | Evidence |
|------|----------|
| **Duplicated** | Analyze engine sequence: `_run_analyze` ≈ `_handle_analyze` ≈ `_handle_explain` |
| **Duplicated** | Bankroll vs learning both centered on `get_learning_stats` with different copy |
| **Duplicated** | Dual HTTP: `/copilot` vs `/chat` |
| **Legacy-only** | `explain_last` full re-pipeline; string `_fmt_*`; `detect_intent` regex |
| **Legacy-only** | Live path without `live_intelligence_engine` |
| **Dead / low-traffic (Avaliar)** | No SoT imports of `_run_*` outside unified router — not dead, but **encapsulation-ready** |
| **Not dead** | `_run_capabilities` fallback branch L1344–1383 — active fail-open |

---

## 9. Coupling & mixed responsibilities (observed)

- **Excessive coupling:** `_copilot_inner` owns Understanding + Orchestration + EM-equivalent dispatch + CM writes + Tool Use web enrich in one ~5260 LOC file.  
- **Mixed in `_run_analyze`:** I/O fetch + integrity + Frozen engines + inference/partial gates + stake/UI narrative + DRS stamp + match_card.  
- **Mixed in callers:** integrity post-check + `_save_analysis_context` sit *outside* `_run_analyze` but are part of “after execute” (Router/CM).

---

## 10. What must stay vs extract later (descriptive classification)

### Must stay (behavior / value — not Spec)

- Frozen engine **order and contracts** as currently exercised by `_run_analyze`.  
- Integrity / PARTIAL / soft-analyze fail-open culture.  
- Cost_protection defaults around analyze.  
- CM FROZEN sole-writer / STS path **not** folded into EM.  
- Structured CopilotResponse contract for unified clients.

### Extract later (classification only)

- `_run_analyze` / `_run_live` / thin `_run_bankroll|learning|knowledge` bodies → future **EM** boundary.  
- Legacy `copilot_engine` path → **Legado** retirement under separate mission.  
- `_save_analysis_context` ownership clarification → **CM**, not EM.  
- `analyze_fixture` / live feed / web → **Tool Use** / data plane adapters.

---

## 11. File inventory (execution-relevant SoT)

| Path | LOC (approx) | Role |
|------|--------------|------|
| `src/routers/copilot_unified_router.py` | 5260 | Primary surface |
| `src/core/copilot_engine.py` | 841 | Legacy executor |
| `src/routers/copilot_router.py` | 299 | Legacy HTTP |
| `src/routers/analyze.py` | 1066 | Fixture I/O + cache |
| `src/routers/live.py` | (via calls) | Live feed |
| `src/ops/cost_protection.py` | — | Budget/cache |
| `src/core/*_engine.py`, `decision_center`, `methodology_v1` | — | Frozen consumers |
| `src/conversation/web_intelligence.py` | — | Ad-hoc tools |
| `src/main.py` | — | Mounts |

Mirror `aurora/`: non-parity sizes noted in Mission 020 — **not audited for fix here**.

---

## Cross-ref

- Full Q&A 1–15 + Dual Reporting → `EXECUTION_SURFACE_REPORT.md`  
- Prior discovery → `observations/execution_manager_discovery_020/EXECUTION_MANAGER_DISCOVERY_REPORT.md`

**Await PO.** No Spec / comparative research / rebuild started.
