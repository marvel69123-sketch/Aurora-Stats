# Mission 022 — Comparative Analysis (Execution Manager)

**MISSION ID:** `execution_manager_research_022`  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** ARCHITECTURE_RESEARCH (documentation only)  
**PREDECESSORS:** Mission 020 Discovery · Mission 021 Surface Map  
**COMPANION:** `EXECUTION_MANAGER_ARCHITECTURE_RESEARCH.md`  

**Nenhuma alteração de código: SIM**  
**NOT a Spec. NOT Master/SSOT edits. NOT authorization to implement.**

---

## Mandatory comparison table

| Framework | Papel equivalente | Responsabilidades | Compatibilidade Aurora |
|-----------|-------------------|-------------------|------------------------|
| **LangGraph** | Graph runtime / step orchestrator (nodes + edges + shared state) | Deterministic + conditional control flow; durable execution; streaming; optional memory/checkpointer | **Alta (padrões)** — nós determinísticos + edges condicionais espelham `_run_analyze`. **Baixa como host do EM** se reutilizar o grafo STS do CM (risco de contaminação CM↔EM). Preferir princípios; não fundir hosts. |
| **OpenAI Agents SDK** | `Runner` agent loop + handoffs + tool calls | Loop LLM→tools/handoff/final; sessions/history; guardrails | **Baixa para núcleo EM esportivo** — assume LLM-as-controller. Útil como referência de *separação Runner vs Agent vs Tools*, não como padrão de sequência Frozen. |
| **Semantic Kernel** | Process Framework (steps/events) + Agent Orchestration (multi-agent) | Process: passos versionáveis, event-driven, auditáveis. Agents: Concurrent/Sequential/Handoff/Group Chat | **Alta (Process / Sequential)** — melhor análogo conceitual a um *pipeline de passos* Frozen. Agent Orchestration multi-agente: **baixa** para analyze. |
| **CrewAI** | Flow (controle) + Crew Process (Sequential / Hierarchical) | Flow: estado + routing; Crew sequential: ordem fixa; Hierarchical: manager LLM delega | **Média (Sequential + Flow)** — sequential = bom princípio. Hierarchical manager LLM = **anti-padrão Aurora** para motores Frozen. |
| **AutoGen** | Team orchestrators (RoundRobin, Selector, Magentic-One) | RoundRobin: ordem fixa; Selector: LLM escolhe próximo; Magentic-One: planner + ledgers | **Média-Baixa** — RoundRobin ≈ sequential útil. Selector/Magentic-One = orquestração LLM-first, **não** cabe no núcleo EM Frozen. |
| **Haystack Agents** | `Agent` tool-calling loop (+ Pipeline/Component tools) | LLM→ToolInvoker loop; `state_schema`; PipelineTool envolve pipelines | **Baixa para EM core** (agent loop). **Alta para Tool Use adjacente** (ComponentTool / PipelineTool / registry). Pipeline determinístico Haystack (fora do Agent) ≈ step runner. |
| **Microsoft Agent Framework (sucessor SK)** | Enterprise multi-agent orchestration | Multi-agent, MCP/A2A, enterprise ops | **Baixa como adoção** agora; princípios de orchestration patterns (sequential vs concurrent) já cobertos via SK docs. Não é pré-requisito Aurora. |

### Compatibility legend (Aurora)

| Score | Meaning |
|-------|---------|
| Alta | Principles reusable for future EM without violating CM FROZEN / Frozen engines / Tool Use split |
| Média | Partial: take sequential/process ideas; discard LLM-manager / shared-context ownership |
| Baixa | Wrong abstraction for Aurora EM core (still informative as anti-pattern or for other pillars) |

---

## Framework-by-framework notes

### 1. LangGraph

**Sources:** [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview), [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), GitHub README.

**EM-equivalent?** Partial. LangGraph is a **low-level orchestration runtime**, not a product “Execution Manager” brand. Closest mapping: **compiled graph that runs deterministic nodes** with optional conditional edges.

**What it teaches**

- Separate **State schema**, **Nodes** (compute), **Edges** (control).
- Mix deterministic steps with agentic steps in one graph — Aurora should use **deterministic-first** for sports engines.
- Durable execution / resume / streaming / HITL as *runtime capabilities*, not domain logic.

**Aurora caution**

- Master + Research 003 already assign LangGraph to **Context Manager STS host**.
- Reusing the **same** STS graph as EM would collapse pillars (Mission 020/021 contamination risk).
- Principle OK: “typed step graph.” Host reuse for EM: **not recommended** without a hard boundary (separate graph / no STS writes).

---

### 2. OpenAI Agents SDK

**Sources:** [Running agents](https://openai.github.io/openai-agents-python/running_agents/), [Agents overview](https://developers.openai.com/api/docs/guides/agents), Runner reference.

**EM-equivalent?** Partial — the **`Runner`** is the execution engine of an **LLM agent loop**, not a Frozen sports pipeline.

**Loop (documented):** call model → final output **or** handoff **or** tool calls → repeat (`max_turns`).

**What it teaches**

- Clear **Runner vs Agent vs Tools vs Session** split.
- Handoff input filters = controlled context projection into the next specialist.
- Tools are first-class; history/session is orthogonal to the loop.

**Aurora caution**

- Analyze order must **not** be LLM-decided.
- Useful analogy for future conversational Tool Use / specialists — **not** for methodology→…→intelligence sequencing.

---

### 3. Semantic Kernel

**Sources:** [Process Framework](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/process/process-framework), [Agent Orchestration](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/), [Agent architecture](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-architecture).

**EM-equivalent?**

- **Process Framework:** Yes — strongest named analogue (Process / Step / Pattern).
- **Agent Orchestration:** Multi-agent collaboration — closer to Orchestration/Tool Use than Frozen EM.

**What it teaches**

- **Process = ordered steps with I/O contracts**, event-driven transitions, auditability (OpenTelemetry called out).
- Orchestration patterns table: Concurrent, Sequential, Handoff, Group Chat — pick pattern by job, don’t default to multi-agent.
- Note: Process Framework marked **experimental** in docs — adopt **principles**, not a hard SK dependency mandate.

**Aurora fit:** Sequential Process / Step Runner family is the primary recommendation anchor.

---

### 4. CrewAI

**Sources:** [Introduction](https://docs.crewai.com/en/introduction), [Processes](https://docs.crewai.com/en/concepts/processes), [Production architecture](https://docs.crewai.com/en/concepts/production-architecture).

**EM-equivalent?** Partial.

- **Flow:** application control plane (state, routers, persistence) ≈ Orchestration + app shell.
- **Crew Process.sequential:** ordered task execution ≈ EM pipeline.
- **Process.hierarchical:** manager LLM assigns tasks ≈ **anti-pattern** for Frozen engines.

**What it teaches**

- Explicit split: **Flow (when/how app proceeds)** vs **Crew (unit of work)**.
- Structured outputs between tasks; guardrails on task outputs.
- Production guidance: wrap work in Flow for state + control.

**Aurora fit:** Sequential process + structured step I/O. Reject hierarchical LLM manager for sports EM.

---

### 5. AutoGen

**Sources:** [SelectorGroupChat](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/selector-group-chat.html), [Magentic-One](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/magentic-one.html), teams reference.

**EM-equivalent?**

- **RoundRobinGroupChat:** weak EM analogue (fixed speaker order) — principle of fixed sequence.
- **SelectorGroupChat:** LLM picks next speaker — **not** EM for Frozen pipeline.
- **Magentic-One Orchestrator:** planner + Task/Progress ledgers — powerful generalist, **wrong job** for Aurora sports EM core.

**What it teaches**

- Multiple orchestration *families* exist; choose by determinism needs.
- Custom `selector_func` can override LLM selection — proves control can be deterministic even in agent frameworks.

**Aurora fit:** Prefer deterministic selection (fixed order / rule-based) over Magentic-One for analyze.

---

### 6. Haystack Agents

**Sources:** [Agents](https://docs.haystack.deepset.ai/docs/agents), [Agent component](https://docs.haystack.deepset.ai/docs/agent), Function calling docs.

**EM-equivalent?** Mostly **no** for sports EM. Haystack `Agent` = tool-calling loop until exit condition.

**What it teaches**

- Strong **Tool** abstraction: Tool / ComponentTool / PipelineTool / MCPToolset.
- Agent state_schema shares data across tool calls — do **not** confuse with Aurora CM sole-writer STS.
- Multi-agent via wrapping Agent as ComponentTool (coordinator/specialist).

**Aurora fit:** Patterns belong primarily to future **Tool Use** pillar; EM should *invoke* tools via adapters, not own the agent loop.

---

### 7. Other relevant (brief)

| System | Note for Aurora EM research |
|--------|------------------------------|
| **Microsoft Agent Framework** | SK successor; enterprise multi-agent — monitor, don’t mandate. |
| **Temporal / durable workflows** | Durable step execution — overkill for current EM extraction (also deferred in CM Research 003). Principle of durable step IDs may matter later. |
| **Plain Python Step Runner** | Not a branded framework — often the best *implementation shape* for Frozen pipelines under AEL (shadow dual-run, defaults OFF). |

---

## Cross-cutting pattern families (synthesis)

| Pattern family | Frameworks exemplifying it | Aurora EM? |
|----------------|----------------------------|------------|
| **Deterministic Sequential Pipeline / Step Runner** | SK Process, CrewAI Sequential, LangGraph deterministic nodes, AutoGen RoundRobin (weak), Haystack Pipeline | **PRIMARY** |
| **Conditional / event-driven process** | SK Process events, CrewAI Flow routers, LangGraph conditional edges | **SECONDARY** (integrity INVALID abort, live vs analyze branch) |
| **LLM agent tool loop** | OpenAI Runner, Haystack Agent | **OUT of EM core** → Tool Use / conversational agents |
| **LLM multi-agent orchestrator** | AutoGen Magentic-One / Selector, CrewAI Hierarchical, SK Group Chat | **ANTI-PATTERN for Frozen EM** |
| **Shared graph state as SSOT** | LangGraph state+checkpointer | **CM domain** (already); EM must not own STS sole-write |

---

## Evidence reuse (Aurora-local)

| Artifact | Use |
|----------|-----|
| Mission 020 | EM absent; blob in mega-router; CM/Tool Use boundaries |
| Mission 021 | `_run_*` Destino Futuro; extract analyze/live/thin reports |
| Master §4 #11 | Execution Manager Ausente / Substituir |
| Blueprint §9.4 | Next-module attention: defaults OFF, Frozen engines, no CM reopen |
| Research 003 | LangGraph = CM host — do not casually reuse as EM SoT |

---

**Await PO.** Spec not started.
