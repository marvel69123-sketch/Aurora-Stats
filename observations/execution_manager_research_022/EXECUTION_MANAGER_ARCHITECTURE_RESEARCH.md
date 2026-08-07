# Mission 022 — Execution Manager Architecture Research

**MISSION ID:** `execution_manager_research_022`  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** ARCHITECTURE_RESEARCH / comparative (documentation only)  
**CODE SoT:** `artifacts/aurora/` (read-only context via Missions 020/021)  
**PREDECESSORS:**  
- Mission 020 — `observations/execution_manager_discovery_020/`  
- Mission 021 — `observations/execution_surface_021/`  
**BLUEPRINT:** `docs/architecture/governance/AURORA_MODULE_BLUEPRINT.md` (process law — not Spec)  
**MASTER:** `docs/architecture/master-architecture.md` — **READ ONLY** (CM FROZEN; EM absent; Frozen engines; Tool Use / Orchestration boundaries)  

**STATUS:** COMPLETE (docs only)  
**Nenhuma alteração de código: SIM**

---

## Hard scope locks

| Allowed | Forbidden |
|---------|-----------|
| Comparative research of modern AI “Execution Manager” equivalents | Product code |
| Principles recommendation (pattern family) | Definitive architecture Spec / ADR / Master / SSOT edits |
| Citation of public framework docs + Aurora 020/021 | Starting Spec mission / EM rebuild |
| AEAP Level 1 on **this mission’s deliverables only** | Global repo audit; Level 3 |

**This package answers “How should it work?” as principles — not “build this Spec.”**

---

## AEAP budget (Level 1 — deliverables only)

```text
AUDIT BUDGET
Nível escolhido: LEVEL 1 (Audit only artifacts produced this mission)
Arquivos novos (produto): 0
Arquivos modificados (produto): 0
Arquivos novos (observations): 2
  - EXECUTION_MANAGER_ARCHITECTURE_RESEARCH.md
  - COMPARATIVE_ANALYSIS.md
Dependências diretas inventariadas (docs): D ≈ Missions 020/021 + Blueprint §9.4 + Master §4–6 (read-only)
Auditorias reaproveitadas: Mission 020 Discovery; Mission 021 Surface; Research 003 (CM host boundary)
Elevação L2/L3: NÃO — research paper; no product delta; no Master contradiction requiring reopen
```

### Level 1 checklist (deliverables)

| Check | Result |
|-------|--------|
| Deliverables under `observations/execution_manager_research_022/` | YES |
| No product code mutated | YES |
| No Master / Spec / Blueprint / SSOT edits | YES |
| Sources cited for frameworks | YES |
| Comparison table present | YES (`COMPARATIVE_ANALYSIS.md` + summarized below) |
| Recommendation = pattern family only (not Spec) | YES |
| Dual Reporting (REGRA 29) | YES (end of this file) |
| Spec mission started | **NO** |

---

## Aurora constraints (binding context — read-only)

From Master + Missions 020/021 + Blueprint:

1. **Context Manager Sole-Writer FROZEN** — EM must **not** own STS / subject write / `_save_analysis_context` semantics.  
2. **Frozen sports engines** — consume `run`/`consult`/`generate` contracts; do not retune formulas inside EM.  
3. **Tool Use separate** — API/cache/web/gateway are adjacent; EM invokes adapters, does not become the registry.  
4. **Orchestration separate** — Master Intent / guards / conversational layers decide *whether* to run; EM runs *how* once asked.  
5. **AEL / Shadow / Gated Activation** — future implementation (when authorized) defaults OFF, shadow dual-run, PGR ladder.  
6. **Reality of extraction** — EM-equivalent today lives as `_run_analyze` / `_run_live` / thin `_run_*` inside mega-router (~5260 LOC) + legacy `copilot_engine` duplication.

---

# Answers 1–12 (PO research prompt)

### 1. Which responsibilities belong **in** a future Execution Manager?

*(Principles — not Spec inventory.)*

| In EM | Why (cross-framework + Aurora) |
|-------|--------------------------------|
| **Coordinate declared execution pipelines** (analyze, live, thin report runs) | Every mature system separates a *runner/process* from chat UI and from domain formulas |
| **Enforce step order / contracts** for Frozen engine sequence | Sequential Process / deterministic graph nodes (SK Process, CrewAI Sequential, LangGraph deterministic nodes) |
| **Gate early aborts that are execution-local** (e.g. integrity INVALID before engines) | Conditional edges / process events — still *execution control*, not Understanding |
| **Assemble structured execution results** for Orchestration/FE contracts | Step outputs → typed payload (CrewAI structured outputs; SK step I/O) |
| **Per-step observability / fail-open policy** around engine invocations | Auditability theme (SK Process + OpenTelemetry; LangGraph streaming) |
| **Respect budget/ops decisions** (“may this step run?”) without owning cache module | Runner integrates policies; ops remains Tool Use / ops plane (Mission 021) |
| **Shadow-comparable step API** | Enables AEL dual-run vs current `_run_analyze` without mega-router edits forever |

### 2. Which responsibilities belong **out** of EM?

| Out of EM | Correct Aurora owner |
|-----------|----------------------|
| Sole-write STS / episode / subject persistence | **Context Manager** (FROZEN) |
| Intent classification, sport_pipeline_blocked, conversational layer order | **Understanding / Orchestration** |
| Tool registry, permissions, raw API clients, analyze cache implementation | **Tool Use** / data / ops |
| Frozen methodology/market/confidence formulas | **Engines Frozen** |
| Greeting/help/identity/capabilities static payloads | **Router / Orchestration** (Mission 021) |
| LLM “manager” choosing which Frozen engine runs next | **Nowhere in Aurora EM core** (anti-pattern) |
| LangGraph STS checkpointer host role | **CM** (Research 003) — not EM |

### 3. What recurring patterns appear across modern systems?

1. **Runner ≠ Domain logic** — OpenAI `Runner`, LangGraph runtime, SK Process, CrewAI Flow vs Crew.  
2. **Sequential pipeline vs agentic loop** — two families; frameworks support both; products must choose.  
3. **Tools as first-class, separate from control** — Agents SDK tools, Haystack Tool/PipelineTool, SK plugins.  
4. **Typed intermediate state between steps** — LangGraph State, CrewAI Flow state, Haystack state_schema (caution: not Aurora CM SSOT).  
5. **Conditional routing as edges/events**, not buried `if` soup in HTTP handlers.  
6. **Multi-agent LLM orchestration** as an *optional* pattern for open-ended tasks — not universal default.  
7. **Observability of steps** (traces, ledgers, OTel) treated as product requirement of the executor.

### 4. How should **flow control** work (principle)?

**Prefer deterministic control for Frozen pipelines; reserve agentic loops for Tool Use / open conversational work.**

| Mode | When | Aurora mapping |
|------|------|----------------|
| Fixed sequence | Known pipeline (analyze engines) | Default EM mode |
| Conditional branch | Integrity fail, live vs analyze, soft-404 recovery | Thin rule edges |
| Agentic tool loop | Unknown tool sequence, web research | Tool Use / future agents — **not** EM core |
| LLM multi-agent debate | Open-ended collaboration | **Out of scope** for sports EM |

Framework evidence: SK Sequential + Process; CrewAI Sequential; LangGraph deterministic nodes; AutoGen RoundRobin (weak). Counter-evidence (do not copy for EM core): Magentic-One, SelectorGroupChat, CrewAI Hierarchical, OpenAI/Haystack agent loops.

### 5. How should **module coordination** work (principle)?

Treat EM as a **thin coordinator of named capabilities**, not a god-object:

```text
Orchestration (decide: run analyze?)
    → Execution Manager (run pipeline P with inputs I)
        → Tool Use adapters (fetch fixture / live feed)   [invoke, don't own]
        → Frozen engines (methodology … intelligence)    [consume]
        → structured Result R
    → Orchestration / FE (present)
    → Context Manager (commit subject)                 [separate call path]
```

Principles from frameworks:

- CrewAI: Flow delegates work units; does not merge memory ownership into every Crew.  
- OpenAI: Runner coordinates Agents/Tools; Sessions are orthogonal.  
- SK: Process steps call Kernel Functions; Process is not the Kernel.  
- Aurora lessons (020/021): do **not** put `_save_analysis_context` inside the executor owner.

### 6. How should **decision routing** work (principle)?

Split **decision layers** explicitly:

| Decision | Owner |
|----------|--------|
| What did the user mean? / May sport pipeline run? | Understanding + Orchestration |
| Which pipeline (analyze vs live vs bankroll)? | Orchestration dispatch (today `_copilot_inner` branches) |
| Which next **engine step** inside analyze? | **EM contract** (fixed order / declared graph) — **not** LLM |
| Which external tool / cache / API? | Tool Use policy (+ ops budget) |
| What is the sport subject after success? | Context Manager |

Anti-conflation: AutoGen Selector / Magentic-One fold “who speaks next” into the executor via LLM — attractive for general agents, **hostile** to Frozen sports determinism and Shadow parity.

### 7. How should **external tools** be handled (principle)?

- **EM invokes; Tool Use owns.**  
- Haystack’s ComponentTool / PipelineTool and OpenAI’s tool loop show tools as a **distinct abstraction** with schemas and invokers.  
- Mission 021 already classifies `analyze_fixture`, live feed, `web_intelligence`, cost_protection as Tool Use / ops.  
- Future EM should depend on **narrow ports** (`FetchFixture`, `FetchLiveFeed`) rather than importing API clients into the coordinator.  
- Do **not** invent a full Tool Registry *inside* EM (Mission 020 discard list).

### 8. How does **context** reach the executor (principle)?

**Push a run request; do not let EM own conversational memory.**

Recommended principle family:

1. Orchestration builds an **ExecutionRequest** (session id, entities, flags, prefer_live, budget tokens, *read projections* of subject).  
2. EM receives **immutable-enough inputs** for the run (+ step-local scratch).  
3. EM returns **ExecutionResult** (structured payload + step traces).  
4. CM sole-writer commits subject **after** Orchestration accepts success — not as a side effect buried in engine loop.

Framework analogues:

- OpenAI handoff `input_filter` — controlled projection into next unit.  
- CrewAI task `context` — explicit prior outputs, not global ambient memory.  
- LangGraph state — powerful but **dangerous** if EM writes STS fields (CM contamination).

Aurora rule: **read projections in; no sole-write out** from EM.

### 9. How should **memory** relate to the executor (principle)?

| Memory class | Relation to EM |
|--------------|----------------|
| Sport conversational subject (STS) | **CM only** — EM must not write |
| Step scratch / intermediate engine outputs | EM-local (ephemeral run state) |
| Long-term learning / knowledge DB reads | Engines / DBs consumed as steps; EM sequences calls |
| Chat transcript / sessions | Orchestration / product session — not EM SSOT |
| Framework “agent memory” (CrewAI/AutoGen/OpenAI Sessions) | Do **not** adopt as Aurora sport-subject SSOT |

Modern systems often blur memory into the orchestrator. Aurora’s CM FROZEN cycle exists precisely because that blur failed. EM research must keep the separation.

### 10. What **anti-patterns** should Aurora avoid?

| Anti-pattern | Seen in / analogous to | Why it hurts Aurora |
|--------------|------------------------|---------------------|
| Mega-router **is** the EM | Current state (020/021) | Couples conversation + engines + CM writes |
| LLM chooses Frozen engine order | Magentic-One, Selector, Hierarchical Crew | Non-deterministic analyze; Shadow impossible |
| EM owns context writes | LangGraph-as-SSOT misuse; agent shared state | Reopens CM FROZEN |
| EM owns Tool Registry | Haystack Agent / Agents SDK loop absorbed wholesale | Collapses Tool Use pillar |
| Dual parallel executors forever | unified `_run_*` + `copilot_engine` | Drift (already present) |
| Big-bang replace mega-router | — | Violates Blueprint AEL / Zero User Impact |
| Reuse CM STS graph as EM host without boundary | LangGraph already in CM | Pillar contamination |
| Treat `minimal_commit_orchestrator` as EM | Name confusion (020) | Wrong owner |

### 11. Which principles **fit** Aurora?

1. **Deterministic Sequential Pipeline / Step Runner** for Frozen sports execution.  
2. **Explicit ExecutionRequest / ExecutionResult contracts** (structured I/O).  
3. **Separation of Orchestration (when) vs EM (how) vs Tool Use (I/O) vs CM (subject).**  
4. **Conditional edges for gates**, not LLM routing, on integrity/partial paths.  
5. **Shadow dual-run / step observability** before cut-over (AEL).  
6. **Defaults OFF + gated activation** (Blueprint §9.4).  
7. **Consume Frozen engines; never rewrite them as agents.**  
8. **Legacy retirement path** for `copilot_engine` (pre-declare — Blueprint lesson).  
9. **Thin coordinator** extractable from `_run_analyze` / `_run_live` without rewriting formulas.  
10. **Fail-open per step with recorded skip/error**, matching current culture.

### 12. Which principles **do not** fit Aurora?

1. **LLM-as-Execution-Manager** for sports analyze pipeline.  
2. **Multi-agent debate / Magentic ledgers** as core analyze path.  
3. **Shared mutable graph state as sport-subject SSOT inside EM.**  
4. **Hierarchical manager agent assigning engines.**  
5. **Absorbing Tool Use agent loop into EM.**  
6. **Framework-as-domain-SoT** (engines/transitions invented by framework).  
7. **Session memory frameworks replacing CM sole-writer.**  
8. **Black-box agent max_turns loop** without step contracts (breaks Shadow parity).  
9. **One LangGraph host for CM + EM without hard write isolation.**  
10. **Copying any framework wholesale** as Aurora Core Substitution without AAR (Master Substitution discipline).

---

## Mandatory comparison table (summary)

Full notes: `COMPARATIVE_ANALYSIS.md`.

| Framework | Papel equivalente | Responsabilidades | Compatibilidade Aurora |
|-----------|-------------------|-------------------|------------------------|
| LangGraph | Graph runtime (nodes/edges/state) | Control flow, durable exec, optional memory | Alta (padrões determinísticos); baixa se host = STS CM |
| OpenAI Agents SDK | Runner + handoffs + tools | LLM loop, tools, sessions | Baixa no núcleo EM Frozen; útil na separação Runner/Tools |
| Semantic Kernel | Process Framework + Agent Orchestration | Steps/events vs multi-agent patterns | Alta (Process/Sequential); baixa (multi-agent core) |
| CrewAI | Flow + Sequential/Hierarchical Process | App control + task order / LLM manager | Média (Sequential/Flow); Hierarchical = anti-padrão |
| AutoGen | RoundRobin / Selector / Magentic-One | Fixed order vs LLM orchestration | Média-Baixa; só RoundRobin/princípio sequencial ajuda |
| Haystack Agents | Agent tool loop (+ Pipeline tools) | LLM↔tools; tool wrapping | Baixa no EM core; Alta para Tool Use |
| MS Agent Framework | Enterprise multi-agent successor | Fleet orchestration | Baixa adoção imediata; padrões já cobertos |

---

## RECOMMENDATION (mandatory — pattern family only)

```text
Qual arquitetura recomenda para o futuro Execution Manager do Aurora?
Por quê?
```

### Recommended pattern family

**Deterministic Sequential Pipeline / Step Runner (Process Framework family)**  
— with **thin conditional edges** for integrity/live branches, **explicit ports to Tool Use**, **no context sole-write**, and **AEL shadow/gated cut-over**.

### Why (grounded in Aurora constraints)

1. Aurora’s real EM job (Mission 020/021) is **running a known Frozen engine sequence** and assembling a structured payload — not open-ended multi-agent planning.  
2. CM Sole-Writer is **FROZEN**: any pattern that makes the executor the memory SSOT (shared agent state / STS writes) is disqualified.  
3. Tool Use must remain a **separate pillar**: agent-tool loops (OpenAI, Haystack Agent) are the wrong *core* abstraction; EM should call adapters.  
4. Shadow/Gated Activation requires **deterministic, step-comparable outputs** — LLM-selected next steps destroy parity.  
5. Mega-router extraction reality: the extractable unit is already a **pipeline body** (`_run_analyze` / `_run_live`), matching Sequential Process / deterministic graph nodes — not Magentic-One.  
6. LangGraph remains valuable as **CM host** (Research 003); EM should adopt **principles** of deterministic graphs **without** conflating hosts or reclaiming STS write.

### Explicitly not recommended as EM core

- Magentic-One / SelectorGroupChat / CrewAI Hierarchical / OpenAI-or-Haystack agent loops as the sports analyze controller.  
- “LangGraph STS graph becomes EM.”  
- Spec-level module design in this mission — **await PO** before Spec.

### One-sentence family label (for return banner)

**Deterministic Sequential Pipeline / Step Runner (Process Framework family), Tool-Use-ported, CM-write-free, shadow-first.**

---

## Sources

### Aurora (local)

- `observations/execution_manager_discovery_020/EXECUTION_MANAGER_DISCOVERY_REPORT.md`  
- `observations/execution_surface_021/EXECUTION_SURFACE_MAP.md`  
- `observations/execution_surface_021/EXECUTION_SURFACE_REPORT.md`  
- `docs/architecture/governance/AURORA_MODULE_BLUEPRINT.md`  
- `docs/architecture/master-architecture.md` (read-only)  
- `observations/aurora_context_manager_research_003/REPORT.md` (LangGraph = CM host boundary)

### Public frameworks (fetched/searched 2026-08-07)

- LangGraph Overview — https://docs.langchain.com/oss/python/langgraph/overview  
- LangGraph Graph API — https://docs.langchain.com/oss/python/langgraph/graph-api  
- OpenAI Agents SDK — Running agents — https://openai.github.io/openai-agents-python/running_agents/  
- OpenAI Agents guide — https://developers.openai.com/api/docs/guides/agents  
- Semantic Kernel Process Framework — https://learn.microsoft.com/en-us/semantic-kernel/frameworks/process/process-framework  
- Semantic Kernel Agent Orchestration — https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/  
- CrewAI Introduction — https://docs.crewai.com/en/introduction  
- CrewAI Processes — https://docs.crewai.com/en/concepts/processes  
- CrewAI Production architecture — https://docs.crewai.com/en/concepts/production-architecture  
- AutoGen Magentic-One — https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/magentic-one.html  
- AutoGen SelectorGroupChat — https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/selector-group-chat.html  
- Haystack Agents — https://docs.haystack.deepset.ai/docs/agents  
- Haystack Agent component — https://docs.haystack.deepset.ai/docs/agent  

---

## Handoff

| Item | Status |
|------|--------|
| Research package | This folder |
| Spec | **NOT STARTED** — await PO |
| Product code | Unchanged |
| Recommended family | Deterministic Sequential Pipeline / Step Runner |

**Await Product Owner.** Do not start Spec.

---

# Dual Reporting (REGRA 29)

---

# REPORT 1 — ENGINEERING REPORT

## Identity

| Field | Value |
|-------|-------|
| Mission | 022 ARCHITECTURE_RESEARCH — Future Execution Manager |
| Branch | `feat/aurora-response-selector-001` |
| Commit message | `docs(research): add Execution Manager architecture research` |
| Commit hash | `eaa64379f7e60e78a6c9b3decf04617c0d0b39fa` (body); stamp `1902134cf3ce43431b616afcc97475e43095a3f2` |
| Push | **YES** — `origin/feat/aurora-response-selector-001` (`bb967e4..eaa6437`, stamp `eaa6437..1902134`) |
| Product code | **Nenhuma alteração de código: SIM** |
| Deliverables | `EXECUTION_MANAGER_ARCHITECTURE_RESEARCH.md`, `COMPARATIVE_ANALYSIS.md` |

## Scope

| In | Out |
|----|-----|
| Comparative framework research + Q&A 1–12 | Spec / ADR / Master / Blueprint / SSOT edits |
| Principles recommendation (pattern family) | Definitive architecture; EM rebuild |
| AEAP L1 on mission deliverables | Global audit; Level 3 |
| Dual Reporting | Starting Spec mission |

## Evidence method

- Read Missions 020/021 + Blueprint §9.4 + Master pillar boundaries (read-only).  
- WebSearch/WebFetch current docs for LangGraph, OpenAI Agents SDK, Semantic Kernel, CrewAI, AutoGen, Haystack Agents (+ MS Agent Framework note).  
- Mapped each framework’s EM-equivalent (or explicit absence) to Aurora constraints.  
- Produced comparison table + pattern-family recommendation without Spec.

## Architecture / governance

- Master / Spec / ADRs / Blueprint / SSOT: **not modified**.  
- Context Manager: **FROZEN** — recommendation forbids EM context sole-write.  
- Frozen engines: **untouched** (consume-only principle).  
- REGRA 29 Dual Reporting: this section.  
- Next: **await PO** — do **not** start Spec.

## Safety

- Docs-only under `observations/execution_manager_research_022/`.  
- Rollback = revert docs commit.  
- No flags / runtime change.

## Validations

| Check | Result |
|-------|--------|
| Q&A 1–12 | YES |
| Comparison table | YES |
| Recommendation pattern family | YES |
| Sources cited | YES |
| AEAP L1 on deliverables | YES |
| Code unchanged | YES |
| Spec started | **NO** |

## Residual / next

- PO review of research + recommendation family.  
- Only if PO authorizes: Spec EM with explicit CM / Tool Use / Orchestration forks (CDR/AAR later).  
- Mirror drift remains OPEN (Activation residual — not this mission).

## Top engineering takeaways

1. **Primary family:** Deterministic Sequential Pipeline / Step Runner (SK Process / CrewAI Sequential / deterministic graph principles).  
2. **Disqualified for EM core:** LLM multi-agent orchestrators and agent-tool loops as sports pipeline controllers.  
3. **Hard boundary:** EM must not own CM writes; must not absorb Tool Registry; must not reuse STS graph as write host.  
4. **Extraction reality:** Mission 021 `_run_analyze` / `_run_live` already look like the Step Runner body to extract later under AEL.

---

# REPORT 2 — PRODUCT OWNER REPORT

📋 PRODUCT OWNER REPORT

✅ O que fizemos hoje

Pesquisamos **como sistemas modernos de IA resolvem o papel de “Execution Manager”** (LangGraph, OpenAI Agents SDK, Semantic Kernel, CrewAI, AutoGen, Haystack e adjacentes). Comparamos com o que a Aurora já descobriu nas missões 020/021 e recomendamos uma **família de padrão** — **sem Spec, sem código de produto, sem reconstrução**.

🧠 O que isso significa

Não copiamos um framework. Respondemos **“como deveria funcionar”** em princípios: o futuro Execution Manager da Aurora deve ser um **coordenador de pipeline determinístico** (passos na ordem dos motores Frozen), com ferramentas e contexto **fora** dele — respeitando o Context Manager congelado, os motores Frozen e a ativação sombra/gradual do Blueprint.

👤 O usuário percebe diferença?

**Não.** Só documentos de pesquisa em `observations/`. O produto não mudou.

⚠️ Existe algum risco?

Risco desta missão: **baixo** (somente documentação).  
Risco que a pesquisa evita no futuro: escolher um “orquestrador LLM multiagente” para a análise esportiva — isso quebraria previsibilidade, sombra/comparação e o Context Manager.

🎯 O que ainda falta?

- Sua leitura e aprovação desta pesquisa / recomendação de família.  
- **Só depois** (se você autorizar): missão de **Spec** do Execution Manager.  
- Continuar **sem** iniciar Spec ou código até o seu OK explícito.

📊 Quanto falta?

Para **esta** Missão 022 (pesquisa comparativa): concluída após commit/push.

```text
████████████████████  100%
```

(Reconstrução do Execution Manager permanece em **0%**. Spec **não** iniciada.)

🏗️ Analogia simples

Descobrimos a cozinha no meio da sala (020) e inventariamos cada fogão (021). Agora comparamos **como restaurantes modernos organizam a cozinha industrial**: a recomendação não é “contratar um chef-robô que improvisa o cardápio a cada pedido” (multiagente LLM), e sim uma **linha de produção com etapas fixas e portas claras para a geladeira (dados) e para o livro de pedidos (contexto)** — ainda **sem construir a obra**.

📝 Resumo em uma frase

Recomendamos o futuro Execution Manager como **pipeline sequencial determinístico (Step Runner / Process Framework)** — pesquisa só, produto intacto, aguardando o Product Owner antes de qualquer Spec.
