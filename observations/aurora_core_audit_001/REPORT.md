# AURORA CORE AUDIT 001 — Official Architecture Audit

**TYPE:** ARCHITECTURE_AUDIT (Missão Oficial 001)  
**MODE:** INVESTIGATION ONLY — no code changes outside this report  
**DATE:** 2026-08-06  
**CODE SoT:** `artifacts/aurora/` (per `AURORA_ARCHITECTURE.md`)  
**MIRROR:** `aurora/` (optional local mirror; proven drift on Topic Boundary V2 / LangGraph POC)  
**AUTHORITIES USED:** Logs (audit transcripts / run logs) → Tests → APIs → Code → Cache (never SoT) → Assumptions (forbidden as evidence)

---

## 1. Executive Summary

Aurora today is a **production sports-analysis + conversational Copilot stack**, not yet a modular **Aurora Core** (14 pillars). The strongest, freeze-worthy assets are the **sports engines** (methodology / market / confidence / intelligence / learning / decision_center / knowledge) and a set of **AEP P0 conversation guards** marked FROZEN in code headers. Conversational perception improved via SLL, CSL, Sport Intent, Response Selector, and Topic Boundary V2 — but **sport conversational subject state remains multi-writer** (14 write-owners documented), critical boundary/centralization flags default **OFF**, and several Aurora Core pillars (**Execution Manager**, coherent **Tool Use**, unified **Orchestration**, Core-grade **Context Manager**) are **absent or only implicit** inside a monolithic router.

**Documento Mestre Etapa 1:** **INSUFFICIENT EVIDENCE** — no file matching that title (or equivalent canonical Aurora Core Etapa 1 master doc) was found under `observations/`, `artifacts/aurora/observations/`, `artifacts/aurora/roadmap/`, `docs/`, or repo root. Governance for this audit therefore uses: (a) the 14 pillars stated in Missão Oficial 001, (b) prior architecture reports (ARCH-001/003, topic_*, sticky_bleed, langgraph POC), (c) `docs/FROZEN_MODULES.md`, (d) code/tests/logs.

**Final Verdict preview:** **NO** — not ready for Substitution Phase (see §9).

---

## 2. Architecture Map

### 2.1 Official Code / Deploy Map

| Path | Role | Evidence |
|------|------|----------|
| `artifacts/aurora/` | **SOURCE OF TRUTH + deploy** | `AURORA_ARCHITECTURE.md` L16–22 |
| `aurora/` | Optional mirror FROM artifacts | Same; TB-V2 / LangGraph files exist only under artifacts |
| `artifacts/web/` | React Copilot FE | `AURORA_ARCHITECTURE.md` L19 |
| `artifacts/aurora/src/main.py` | FastAPI app + routers | Code |
| `POST /aurora/copilot` | Primary conversational entry | `copilot_unified_router.py` |

### 2.2 Runtime Pipeline (as implemented — artifacts SoT)

Evidence: `artifacts/aurora/src/routers/copilot_unified_router.py` (~L1806–1853+) and `artifacts/aurora/docs/conversation_pipeline.md`.

```text
USER → POST /aurora/copilot
  conversation_manager.get(session)     # RAM TTL + SQLite best-effort
  SLL (sports_language)                 # nickname / compare normalize
  TopicBoundaryV2                       # ENABLE_TOPIC_BOUNDARY_V2 default OFF
  CSL (conversation_state_layer)        # ENABLE_CSL default ON
  Sport Intent Layer                    # ENABLE_SPORT_INTENTS default ON
  LangGraph shadow compare              # ENABLE_LANGGRAPH_STATE_SHADOW default OFF
  short_memory / fiction / dialog_mode / ownership / continuity / …
  CUE → HPL → State → Reinforcement → Reasoner → CIL → CRL → Deep Reasoning
  CI / FollowUp / NL / analyze|live engines
  Response Selector                     # ENABLE_RESPONSE_SELECTOR default ON
  Integrity → Credibility → Prediction Memory (passive)
  note_* cascade (CSL, short_mem, continuity, OS, SRF, …)
  → CopilotResponse
```

Sports analyze spine (when engines run):

```text
analyze_fixture → methodology_engine → confidence_engine → market_engine
  → methodology_v1 → decision_center → intelligence_engine → i18n_pt
```

Evidence: `AURORA_ARCHITECTURE.md` L28–51; engine modules under `artifacts/aurora/src/core/`.

### 2.3 Layer Inventory (mapped → Aurora Core pillars)

| Layer / module cluster | Approx. Core pillar | Notes |
|------------------------|---------------------|-------|
| SLL, CUE, MasterIntent, NL, Sport Intent, human_inference | Understanding | Multiple parallel classifiers |
| CSL, SRF, conversation_state, short_mem, focus, continuity, OS, SCG | Context Manager | **No single SSOT writer** |
| conversation_manager, memory_db, prediction_memory, chat_db | Memory | Session + long-term SQLite; cross-node gap documented |
| knowledge_engine + knowledge_db | Knowledge | Domain rules DB |
| entity_resolver (+ API `/teams?search`), web_intelligence (DDG/Wiki), data gateway | Search | Split: entity search vs web vs provider fetch |
| response_planner, CRL, CIL | Planning | Response-plan oriented, not agent plan graph |
| conversation_reasoner, deep_reasoning, methodology/market math | Reasoning | Conversational + sports math dual |
| reflection_credibility, deep_reasoning wrap | Reflection | Present; presentation-heavy |
| decision_center, dialog_mode, response_selector, followup_guard, TB-V2 | Decision | Fragmented decision surfaces |
| web_intelligence, API-Football client, data/gateway | Tool Use | Ad-hoc tools; no Tool Use Core API |
| *(none named)* | Execution Manager | **Ausente** as pillar |
| copilot_unified_router (+ flags) | Orchestration | Monolith; LangGraph shadow-only |
| learning_engine, evolution_engine, belief_revision | Learning | Read-mostly sports learning + conversational belief MVP |
| [AUDIT] logs, pipeline_trace, frustration/llm_judge obs, ops/* | Observability | Strong audit stamps; not unified Core telemetry |

### 2.4 Proven Drift (artifacts vs aurora mirror)

| Capability | `artifacts/aurora` | `aurora/` |
|------------|--------------------|-----------|
| `topic_boundary_v2.py` | Present | **Absent** (glob) |
| LangGraph state POC | Present | **Absent** (glob) |
| Prior investigation | `topic_transition_arch_001` noted live tree lacks V2 | Confirmed by file presence |

---

## 3. Pilar Assessment

Legend — Estado: Implementado | Parcial | Ausente · Qualidade: Excelente | Boa | Regular | Crítica · Recomendação: exactly one of Manter | Congelar | Melhorar | Substituir.

---

### 3.1 Understanding

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Regular |
| **Problemas encontrados** | Multiple understanding surfaces coexist (CUE, MasterIntent, NL router, Sport Intent, human_inference, SLL) without a single Core Understanding contract. Sport-intent historically hijacked CSL teams on new fixtures (proven + fixed in intent layer only). |
| **Evidências** | `artifacts/aurora/src/conversation/conversational_understanding.py`; `sports_language.py`; `sport_intent_layer.py`; `master_intent_router.py`; `core/nl_router.py`; `observations`/`artifacts/.../sport_intent_hijack_fix_001/REPORT.md`; tests `test_conversational_understanding_v43.py`, `test_sport_intent_layer_intent001.py`, `test_sports_language_patch002a.py` |
| **Impacto** | 🟠 |
| **Recomendação** | Melhorar |
| **Solução Pública** | — (not Substituir) |

---

### 3.2 Context Manager

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Crítica |
| **Problemas encontrados** | Sport conversational subject has **≥14 distinct session write-owners**; episode rotation alone was insufficient for sticky bleed (ordering + incomplete cleanup). TB-002 fix exists but flag **default OFF**. LangGraph STS is shadow-only. No Aurora Core Context Manager as sole writer. |
| **Evidências** | `observations/topic_state_centralization_001/REPORT.md` (§2.1, 14 writers); `observations/sticky_bleed_001/REPORT.md`; `observations/topic_boundary_002/REPORT.md` (flag default 0); `conversation_state_layer.py`; `sport_referent_frame.py`; `topic_boundary_v2.py`; `langgraph_state_adapter.py` (shadow); logs in `observations/topic_boundary_002/live_validation/run_log.txt` |
| **Impacto** | 🔴 |
| **Recomendação** | Substituir |
| **Solução Pública** | LangGraph TypedDict + checkpointer (host/state only — prior ARCH-003 / topic_transition reject domain adoption of full Rasa/LangGraph); Rasa `DialogueStateTracker` concepts; custom Aurora sole-writer SSOT (design in topic_state_centralization_001). |

---

### 3.3 Memory

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Regular |
| **Problemas encontrados** | Session memory is RAM+SQLite best-effort; Autoscale without sticky sessions → cross-node miss (`AURORA_ARCHITECTURE.md`). Multiple short-term memories (short_mem, prediction_memory, memory_db collections) without Core Memory API. Cache must not be treated as SoT (mission rule). |
| **Evidências** | `AURORA_ARCHITECTURE.md` L62–70; `artifacts/aurora/src/memory_db.py`; `conversation/short_conversation_memory.py`; `conversation/prediction_memory.py`; `chat_db` usage in router; `routers/memory_router.py`; `main.py` startup init |
| **Impacto** | 🟠 |
| **Recomendação** | Melhorar |
| **Solução Pública** | — |

---

### 3.4 Knowledge

| Field | Assessment |
|-------|------------|
| **Estado** | Implementado |
| **Qualidade** | Boa |
| **Problemas encontrados** | Domain knowledge consult exists; product bottleneck notes knowledge can be empty/weak when entity unbound (starvation upstream, not formula defect). Listed among frozen intelligence engines in `docs/FROZEN_MODULES.md`. |
| **Evidências** | `artifacts/aurora/src/core/knowledge_engine.py` (`consult`); `knowledge_db` init in `main.py`; `docs/FROZEN_MODULES.md` L18; `roadmap/next_product_bottleneck.md` L56–60 |
| **Impacto** | 🟡 |
| **Recomendação** | Congelar |
| **Solução Pública** | — |

---

### 3.5 Search

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Regular |
| **Problemas encontrados** | No single Search pillar: entity `/teams?search`, API-Football gateway, DuckDuckGo/Wikipedia web enrich are separate. Web path is fail-open additive, not Core tool/search contract. |
| **Evidências** | `core/entity_resolver.py` (`search_variants`, teams_search); `data/gateway.py`; `conversation/web_intelligence.py` (`_duckduckgo_snippet`, `_wikipedia_summary`); client `src/client.py` (per architecture doc) |
| **Impacto** | 🟡 |
| **Recomendação** | Melhorar |
| **Solução Pública** | — (narrow public option for date/time extract already identified under Planning/Understanding utilities: dateparser — see arch_003) |

---

### 3.6 Planning

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Regular |
| **Problemas encontrados** | Response planning exists (CRL / response_planner / CIL) for *how to answer*, not a Core multi-step agent plan with resource/tool budgets. Pipeline docs describe Plan as response-layer step. |
| **Evidências** | `conversation/response_planner.py`; `conversation_response_layer.py`; `conversation_intelligence_layer.py`; `docs/conversation_pipeline.md` L24–31; tests `test_conversation_response_layer_v41.py`, `test_conversation_intelligence_layer_v42.py` |
| **Impacto** | 🟡 |
| **Recomendação** | Melhorar |
| **Solução Pública** | — |

---

### 3.7 Reasoning

| Field | Assessment |
|-------|------------|
| **Estado** | Implementado |
| **Qualidade** | Boa |
| **Problemas encontrados** | Dual reasoning stacks: conversational reasoner/deep_reasoning (regex/heuristic enriched) vs sports math engines. Engines are healthy but often starved of rich inputs (product bottleneck). No claim of unified Core Reasoner. |
| **Evidências** | `conversation_reasoner.py`; `deep_reasoning.py`; `methodology_engine.py` / `market_engine.py` / `decision_center.py`; tests `test_conversation_reasoner_v40.py`, `test_deep_reasoning_v45.py`; `roadmap/next_product_bottleneck.md` L24, L73–75 |
| **Impacto** | 🟡 |
| **Recomendação** | Congelar |
| **Solução Pública** | — |
| **Nota de escopo** | Congelar applies to **sports engine math** (methodology/market/confidence/decision). Conversational reasoner heuristics: Melhorar would be alternate if treated separately — for pillar-level single recommendation: **Congelar** sports SoT; conversational reasoner remains non-Core-frozen utility (see Replacement §5 for utility regex surfaces). |

*Clarification for Frozen map:* sports Reasoning engines → Congelar; conversational Reasoner façade → not elevated to Frozen Core without further eval (see §4).

**Pillar-level recommendation retained as Congelar** for the strategic Reasoning asset (engines). Conversational reasoner listed under Melhorar utilities in §5 if treated as defective regex surface — **INSUFFICIENT EVIDENCE** that conversational reasoner must be *replaced* vs improved.

---

### 3.8 Reflection

| Field | Assessment |
|-------|------------|
| **Estado** | Implementado |
| **Qualidade** | Boa |
| **Problemas encontrados** | Reflection + credibility display modes exist; largely presentation / hypothesis framing, not closed-loop self-critique against ground truth. Fail-open additive. |
| **Evidências** | `conversation/reflection_credibility.py`; `deep_reasoning.py` (wraps reflection); tests `test_reflection_credibility_v44.py`; pipeline doc L12–13, L75–82 |
| **Impacto** | 🟢 |
| **Recomendação** | Manter |
| **Solução Pública** | — |

---

### 3.9 Decision

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Regular |
| **Problemas encontrados** | Sports Decision Center is mature (23 markets). Conversational *turn/episode decisions* are split across TB-V2, brain_authority, followup_guard, follow_up_engine, message_intelligence, Response Selector — **no single Decision pillar**. Transition report: “no single owner.” |
| **Evidências** | `core/decision_info` → `decision_center.py`; `topic_boundary_v2.py`; `core/followup_guard.py`; `response_selector.py`; `observations/topic_transition_arch_001/REPORT.md` §1.1–1.3; `docs/FROZEN_MODULES.md` (Decision Center frozen) |
| **Impacto** | 🟠 |
| **Recomendação** | Melhorar |
| **Solução Pública** | — for sports Decision Center (Congelar in §4). Conversational transition decision: KEEP CUSTOM TRANSITION (centralize) — not adopt Rasa/LangGraph as domain decision (`topic_transition_arch_001`, arch_003). |

---

### 3.10 Tool Use

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Crítica |
| **Problemas encontrados** | Tools exist as direct imports/calls (API-Football, web_intelligence, analyze/live) without a Tool Use registry, schema, permissioning, or Core tool contract. No `ToolRegistry` / `execution` abstraction found in `artifacts/aurora/src`. |
| **Evidências** | Grep: no `execution_manager` / `ToolRegistry` / `run_tool` in `artifacts/aurora/src`; `web_intelligence.py`; `data/gateway.py`; router `_run_analyze` / `_run_live`; `ops/cost_protection.py` (budget around calls, not tool API) |
| **Impacto** | 🔴 |
| **Recomendação** | Substituir |
| **Solução Pública** | Mature agent tool patterns to evaluate later (no implement): LangChain/LangGraph tool interfaces (concepts), OpenAI/Anthropic tool-calling schemas, custom thin Tool Registry. Prior policy: do not adopt full LangChain classic memory as runtime. |

---

### 3.11 Execution Manager

| Field | Assessment |
|-------|------------|
| **Estado** | Ausente |
| **Qualidade** | Crítica |
| **Problemas encontrados** | No module named or structured as Execution Manager. Execution is inline in `copilot_unified_router` / analyze paths (async functions, fail-open try/except). Cost protection paces calls but is not an Execution Manager. |
| **Evidências** | Grep absence of Execution Manager identifiers; `copilot_unified_router.py` `_run_analyze`, `_copilot_inner`; `ops/cost_protection.py` |
| **Impacto** | 🔴 |
| **Recomendação** | Substituir |
| **Solução Pública** | Introduce Core Execution Manager in future phase (design-only here). Public references for later eval: LangGraph node runners / interrupt patterns; workflow engines (Temporal — heavy); prefer Aurora-owned thin executor per philosophy (specializations never modify Core). |

---

### 3.12 Orchestration

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Crítica |
| **Problemas encontrados** | Orchestration = mega-router (`copilot_unified_router.py`) with feature-flag spaghetti. LangGraph POC is **shadow only**; production write path OFF. Pipeline ordering bugs historically caused sticky bleed (fixed behind flag). |
| **Evidências** | `copilot_unified_router.py` size/wiring; `langgraph_state_poc_001/REPORT.md` (flags OFF); `topic_boundary_002/REPORT.md` order fix; `conversation_pipeline.md` |
| **Impacto** | 🔴 |
| **Recomendação** | Substituir |
| **Solução Pública** | LangGraph as **host/orchestration graph only** (prior: reject as sport-logic SoT); SuperDialog-style flow locks (concepts, arch_003); custom Aurora Orchestrator Core. |

---

### 3.13 Learning

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Regular |
| **Problemas encontrados** | `learning_engine` is read-only historical context from SQLite; writes elsewhere. `belief_revision` is conversational MVP (not sports learning). Evolution engine exists. Not a closed-loop Core Learning pillar wired to all decisions. Frozen list includes Learning engine formulas. |
| **Evidências** | `core/learning_engine.py` (READ only docstring); `learning_db`; `belief_revision.py`; `evolution_engine.py`; `docs/FROZEN_MODULES.md` L18; roadmap ROI notes Learning ROI baixo–médio |
| **Impacto** | 🟡 |
| **Recomendação** | Congelar |
| **Solução Pública** | — |
| **Escopo Congelar** | Sports `learning_engine` formulas/contracts. Belief-revision conversational MVP remains separate (Manter/Melhorar product track — not Core freeze without more evidence). |

---

### 3.14 Observability

| Field | Assessment |
|-------|------------|
| **Estado** | Parcial |
| **Qualidade** | Boa |
| **Problemas encontrados** | Strong `[AUDIT]` logging and stamp helpers; frustration / LLM-judge observability; ops cost/throttle metrics; pipeline_trace. Not a unified Aurora Core Observability plane (schemas, metrics SoT, distributed tracing). Logs are authority #1 and are present for many turns. |
| **Evidências** | Router `[AUDIT]` / `pipeline=intelligence_engine` logs; `frustration_observability.py`; `llm_judge_observability.py`; `pipeline_trace.py`; `debug_audit.py`; `ops/*`; live run logs under `observations/*/run_log.txt` |
| **Impacto** | 🟡 |
| **Recomendação** | Melhorar |
| **Solução Pública** | — (optional later: OpenTelemetry concepts — not evidenced as requirement in repo docs) |

---

### 3.15 Pillar scoreboard (summary)

| # | Pillar | Estado | Qualidade | Impacto | Recomendação |
|---|--------|--------|-----------|---------|--------------|
| 1 | Understanding | Parcial | Regular | 🟠 | Melhorar |
| 2 | Context Manager | Parcial | Crítica | 🔴 | Substituir |
| 3 | Memory | Parcial | Regular | 🟠 | Melhorar |
| 4 | Knowledge | Implementado | Boa | 🟡 | Congelar |
| 5 | Search | Parcial | Regular | 🟡 | Melhorar |
| 6 | Planning | Parcial | Regular | 🟡 | Melhorar |
| 7 | Reasoning | Implementado | Boa | 🟡 | Congelar |
| 8 | Reflection | Implementado | Boa | 🟢 | Manter |
| 9 | Decision | Parcial | Regular | 🟠 | Melhorar |
| 10 | Tool Use | Parcial | Crítica | 🔴 | Substituir |
| 11 | Execution Manager | Ausente | Crítica | 🔴 | Substituir |
| 12 | Orchestration | Parcial | Crítica | 🔴 | Substituir |
| 13 | Learning | Parcial | Regular | 🟡 | Congelar |
| 14 | Observability | Parcial | Boa | 🟡 | Melhorar |

---

## 4. Frozen Candidates

Official map of modules/assets with **proven freeze policy and/or strategic SoT status**. These should remain Frozen during Core reconstruction unless a signed redesign brief supersedes them.

| # | Candidate | Evidence of freeze / keep | Core pillar affinity |
|---|-----------|---------------------------|----------------------|
| 1 | `methodology_engine` | Roadmap freeze checks; langgraph POC “not modified”; FROZEN_MODULES engines list | Reasoning |
| 2 | `market_engine` | Same | Reasoning / Decision |
| 3 | `confidence_engine` | Same; “formulas untouched” across P2.5 docs | Reasoning |
| 4 | `intelligence_engine` | Same; live narrative SoT | Reasoning |
| 5 | `learning_engine` | Same + FROZEN_MODULES | Learning |
| 6 | `decision_center` | `docs/FROZEN_MODULES.md` L18 | Decision |
| 7 | `knowledge_engine` | `docs/FROZEN_MODULES.md` L18 | Knowledge |
| 8 | `ownership_stability` | Code header `Status: FROZEN`; arch_003 KEEP | Context / Decision (lock) |
| 9 | `sport_continuity_guard` | Code header FROZEN; arch_003 KEEP | Context |
| 10 | `ambiguous_context_guard` | Code header FROZEN; arch_003 KEEP | Context |
| 11 | `fiction_context_jump_guard` | Code header FROZEN; arch_003 KEEP | Context |
| 12 | `sports_language` (SLL) | ARCH-001/003 KEEP; patch shipped + tests | Understanding |
| 13 | `entity_safety` | ARCH-003 KEEP | Understanding |
| 14 | `follow_up_engine` | `docs/FROZEN_MODULES.md` L19 | Decision / Understanding |
| 15 | Analyze / payload contracts + Integrity Guard | `docs/FROZEN_MODULES.md` L12–20 | Decision / Observability |
| 16 | Conversation Personalization (FE v3.6.x) | `docs/FROZEN_CONVERSATION_PERSONALIZATION.md` | *(specialization — must not modify Core)* |
| 17 | `response_selector` | Approved KEEP; reads subject, does not own fixture SoT (`topic_state_centralization_001`) | Decision (response) |
| 18 | `fixture_status` as `is_live` SoT | `AURORA_ARCHITECTURE.md` engines table | Reasoning / Execution input |

**Count Frozen Candidates: 18**

**Explicitly NOT frozen as Core Context SSOT (despite importance):** CSL, SRF, short_mem, conversation_state, multi-writer cascade — design says centralize/replace writers; modules remain operational.

---

## 5. Replacement Candidates

Modules/surfaces that should be **replaced or collapsed** in a future Substitution Phase (design-approved; not authorized to implement now).

| # | Candidate | Why (proven) | Target direction (prior art) |
|---|-----------|--------------|------------------------------|
| 1 | Multi-writer sport conversational state (14 owners) | Sticky bleed + SSOT design | Sole-writer Context Manager / STS (`topic_state_centralization_001`) |
| 2 | Parallel episode/transition detectors (≥4) | `topic_transition_arch_001` | Single custom `EpisodeTransition.decide` (KEEP CUSTOM; frameworks host only) |
| 3 | `message_intelligence.is_topic_switch` regex-only path | arch_003 REPLACE narrow | Episodic / Athena-style boundary concepts |
| 4 | Brittle date NLU in `natural_conversation` (when dateparser OFF) | arch_003; `calendar_time.py` exists flag-gated | `dateparser` (pt-BR) — module present, `ENABLE_DATEPARSER` default OFF |
| 5 | Duplicate nickname maps outside SLL | arch_003 REPLACE | SLL as sole nickname SoT |
| 6 | Ad-hoc Tool Use (direct web/API calls) | No Tool Use pillar | Core Tool Registry + schemas |
| 7 | Inline execution in mega-router | No Execution Manager | Core Execution Manager |
| 8 | `copilot_unified_router` as de-facto Orchestration | Monolith + flag coupling | Core Orchestrator (LangGraph host optional, shadow first) |
| 9 | Production dual-tree risk (`aurora/` vs `artifacts/aurora/`) | Missing TB-V2/LangGraph on mirror | Enforce single SoT path (process/architecture), not feature replace |

**Count Replacement Candidates: 9**

---

## 6. Public Technology Candidates

Only for Substituir recommendations / replacement surfaces. **No implementation. No adaptation.**

| Replacement surface | Public / mature options to evaluate later | Constraints from prior Aurora research |
|---------------------|-------------------------------------------|----------------------------------------|
| Context Manager / state host | LangGraph `TypedDict` + reducers + checkpointer; Rasa tracker/slots concepts | **Do not** adopt Rasa/LangGraph as sport-domain logic SoT (`arch_003`, `topic_transition_arch_001`) |
| Orchestration graph | LangGraph Graph API (host); SuperDialog flow locks (concepts) | Shadow-first; production write OFF until metrics |
| Topic boundary utility | Episodic topic segmentation; Athena Topic Manager concepts | Keep PT sport lexicon / Jaccard policy Aurora-owned |
| Calendar date extract | `dateparser` (pt/pt-BR); Duckling (ops-heavy optional) | puckling rejected for BR (`arch_003`) |
| Follow-up rewrite (utility) | Athena rule-coref; AWS sample contextualize pattern; CANARD/T5 Tier B | PT coverage / latency risks for neural |
| Tool Use schemas | OpenAI/Anthropic tool-calling; LangGraph tool nodes (concepts) | Prefer thin Aurora Core registry |
| Execution Manager | Workflow runners (LangGraph interrupts; Temporal — heavy) | Prefer Aurora-owned thin executor |
| Coref (pronoun) | Athena 1-turn rules | coreferee rejected (no PT) (`arch_003`) |

---

## 7. Risks

| # | Risk | Severity | Evidence |
|---|------|----------|----------|
| R1 | Multi-writer subject contamination / sticky bleed if TB-V2 OFF or incomplete | 🔴 | sticky_bleed_001; TB-002 flag default OFF |
| R2 | Starting Substitution Phase without Documento Mestre Etapa 1 in-repo | 🔴 | Search: **INSUFFICIENT EVIDENCE** for master doc path |
| R3 | Dual SoT if LangGraph write enabled without retiring writers | 🔴 | langgraph_state_poc_001 risks |
| R4 | Touching Frozen engines/guards for chat metrics → AEP regression | 🔴 | FROZEN headers; roadmap “do not retune” |
| R5 | `aurora/` mirror drift vs deploy SoT | 🟠 | File absence TB-V2/LangGraph on mirror |
| R6 | Cross-node session memory miss (Autoscale) | 🟠 | AURORA_ARCHITECTURE.md memory limitation |
| R7 | Engines starved → partial/empty analyses (trust) | 🟠 | next_product_bottleneck.md; logs `partial=True completeness=0.22` |
| R8 | Feature-flag matrix complexity → unknown production config | 🟠 | Multiple ENABLE_* defaults OFF/ON |
| R9 | Replacing transition with framework domain stories | 🟠 | Explicit prior rejection |
| R10 | Cache mistaken for truth in audits/ops | 🟡 | Mission authority rule; cost_protection prefers cache |

---

## 8. Roadmap Recommendation

Order respects: **nunca regredir**, Frozen policy, evidence-first, modularity, specializations never modify Core.

1. **Locate / ratify Documento Mestre Etapa 1** in-repo (blocker for Substitution Phase governance).  
2. **Freeze ratification ceremony** — publish Frozen Candidates (§4) as binding under Core governance (engines + AEP guards + SLL/entity_safety + FE personalization).  
3. **Context Manager SSOT (design → gated impl later)** — sole writer for sport subject; keep OS/SCG as lock modules via public APIs only (`topic_state_centralization_001`).  
4. **Centralize EpisodeTransition decision** (custom Aurora) before any LangGraph production write (`topic_transition_arch_001`).  
5. **Observability contract** for OLD vs NEW state (extend shadow metrics) before Orchestration cutover.  
6. **Introduce Core Tool Use + Execution Manager (design)** — wrappers around existing API-Football / web / analyze — without retuning engines.  
7. **Replace mega-router Orchestration** behind flags; LangGraph remains host candidate after shadow green.  
8. **Narrow utility replacements** already researched: dateparser ON with golden calendar; nickname SoT only via SLL; topic_switch regex retirement.  
9. **Understanding consolidation** — single Core Understanding façade feeding classifiers (SLL stays Frozen SoT for nicknames).  
10. **Defer** Learning formula changes; defer FE personalization edits; defer sports engine retunes.

**Do not** open Substitution Phase by swapping methodology/market/confidence/intelligence/learning first.

---

## 9. Final Verdict

### A Aurora está pronta para iniciar a Fase de Substituição?

# **NO**

### O que falta (exactly)

1. **Documento Mestre Etapa 1** versionado no repositório (**INSUFFICIENT EVIDENCE** hoje) — sem ele, Substitution Phase não tem autoridade de governança.  
2. **Context Manager SSOT** — multi-writer sport state ainda é o risco arquitetural dominante; TB-V2 fix não é default.  
3. **Core pillars Ausentes/Críticos** — Execution Manager ausente; Tool Use e Orchestration sem contrato Core (só monolito + tools ad-hoc).  
4. **Shadow → production gate** — LangGraph/STS write path must remain OFF until divergence metrics + sole-writer plan; Substitution without this reopens dual-SoT.  
5. **Frozen Candidates ratification** — engines/guards are de-facto frozen in docs/code, but Core-era Frozen Map (§4) needs formal sign-off against Documento Mestre.  
6. **Mirror/SoT discipline** — `aurora/` drift proves process risk before large replacements.

---

## 10. Validation Contract checklist

| # | Question | Answer | Notes |
|---|----------|--------|-------|
| 1 | Todas as conclusões possuem evidências? | **YES** for pillar estados and Frozen/Replacement maps cited above. Claims without files marked **INSUFFICIENT EVIDENCE**. | Cache never used as SoT. |
| 2 | Existem suposições? | **NO as evidence.** Residual unknowns explicitly labeled INSUFFICIENT EVIDENCE (Documento Mestre path; conversational reasoner replace-vs-improve). | |
| 3 | Alguma recomendação pode gerar regressão? | **YES — if mis-executed.** Hence Verdict NO; Substitution deferred. Recommendations prefer Congelar engines/guards; Substituir only utility/orchestration/context SSOT with prior flag/shadow discipline. | |
| 4 | Alguma recomendação viola o Documento Mestre? | **INSUFFICIENT EVIDENCE** — Documento Mestre Etapa 1 not found in repo; cannot certify compliance nor violation against that text. Recommendations aligned to Missão Oficial 001 pillars + prior ARCH reports. | |
| 5 | Existe conflito arquitetural? | **YES (documented).** Multi-writer vs SSOT design; TB-V2 OFF vs bleed fix; LangGraph host vs multi-writer; `aurora/` vs `artifacts/` drift; parallel Decision surfaces. | |
| 6 | O relatório está completo? | **YES** relative to OUTPUT CONTRACT §§1–11 and 14 pillars, with INSUFFICIENT EVIDENCE where required. | Remains **blocked for Substitution Phase** until §9 gaps close. |

**Validation gate for “ready to leave review”:** items 4–5 prevent declaring Substitution readiness; report itself is complete as audit deliverable.

---

## 11. Confidence

| Conclusion | Confidence | Justification | Evidences |
|------------|------------|---------------|-----------|
| Code SoT is `artifacts/aurora/` | **95%** | Explicit architecture SoT table | `AURORA_ARCHITECTURE.md` |
| Sports engines are Frozen Candidates | **92%** | Multiple independent freeze declarations | `docs/FROZEN_MODULES.md`; engine headers/roadmap; langgraph POC non-touch list |
| AEP guards FROZEN | **95%** | Code status headers | `ownership_stability.py`, `sport_continuity_guard.py`, `ambiguous_context_guard.py`, `fiction_context_jump_guard.py` |
| Context Manager is critical multi-writer | **93%** | Dedicated audit counted 14 writers + bleed RCA | `topic_state_centralization_001`, `sticky_bleed_001`, `topic_boundary_002` |
| Execution Manager absent | **90%** | Identifier/module grep empty; execution inline in router | Code grep + router structure |
| Tool Use not a Core pillar | **88%** | Tools exist but no registry/contract | `web_intelligence.py`, gateway, grep |
| LangGraph is shadow-only | **95%** | Flags + report | `sport_topic_state.py`, `langgraph_state_poc_001/REPORT.md` |
| Documento Mestre Etapa 1 missing from repo | **90%** | Targeted searches found no titled master doc | Grep/glob over observations, roadmap, docs, root |
| Ready for Substitution Phase = NO | **90%** | Compound of SSOT gap + missing Mestre + absent Core pillars | §§3–9 |
| Public tech shortlist correctness | **80%** | Drawn from ARCH-003 fetched research; maturity numbers may drift | `arch_003/ARCHITECTURE_RESEARCH.md` |
| Exact production flag values in live deploy | **INSUFFICIENT EVIDENCE** | Defaults documented in code; live env not audited this mission | Code defaults only |
| Quantitative live Success/HPS “today” | **INSUFFICIENT EVIDENCE** | Prior roadmap cites Discovery 90.9% (2026-07-20); not re-run here | `next_product_bottleneck.md` (historical) |

---

## Appendix A — Prior reports consulted

| Report | Path |
|--------|------|
| ARCH-001 | `artifacts/aurora/observations/arch_001/ARCHITECTURE_PROPOSAL.md` |
| ARCH-003 | `artifacts/aurora/observations/arch_003/ARCHITECTURE_RESEARCH.md` |
| CSL-001 | `artifacts/aurora/observations/csl_001/ARCHITECTURE.md` |
| Sticky bleed | `observations/sticky_bleed_001/REPORT.md` |
| Topic boundary 002 | `observations/topic_boundary_002/REPORT.md` |
| Topic transition | `observations/topic_transition_arch_001/REPORT.md` |
| Topic state centralization | `observations/topic_state_centralization_001/REPORT.md` |
| LangGraph POC | `observations/langgraph_state_poc_001/REPORT.md` |
| Sport intent hijack | `artifacts/aurora/observations/sport_intent_hijack_fix_001/REPORT.md` |
| Frozen modules | `docs/FROZEN_MODULES.md` |
| Architecture SoT | `AURORA_ARCHITECTURE.md` |
| Pipeline map | `artifacts/aurora/docs/conversation_pipeline.md` |
| Product bottleneck | `artifacts/aurora/roadmap/next_product_bottleneck.md` |

## Appendix B — Documento Mestre Etapa 1

**Status:** **INSUFFICIENT EVIDENCE**  
**Searched:** `observations/`, `artifacts/aurora/observations/`, `artifacts/aurora/roadmap/`, `docs/`, repo root patterns (`Documento*`, “Documento Mestre”, “Etapa 1”, “Aurora Core”, “Engenharia de Prompt”).  
**Found:** Mission prompt references Etapa 1 alignment in chat governance; **no canonical master document file** in the repository at audit time.

---

**END OF REPORT — AURORA CORE AUDIT 001**
