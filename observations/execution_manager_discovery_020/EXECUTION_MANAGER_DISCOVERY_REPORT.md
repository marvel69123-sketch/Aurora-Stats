# Mission 020 — Execution Manager MODULE_DISCOVERY

**MISSION ID:** `execution_manager_discovery_020`  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** MODULE_DISCOVERY / diagnostic (documentation only)  
**CODE SoT:** `artifacts/aurora/`  
**MIRROR (inventory only):** `aurora/` — drift noted; **not fixed**  
**STATUS:** COMPLETE (pending commit/push evidence below)

---

## Hard scope locks (this mission)

| Allowed | Forbidden |
|---------|-----------|
| Diagnose **current** execution / engine-orchestration surface | Product code changes |
| Answer PO Prompt Mestre questions + Dual Reporting | Spec / ADR / architecture redesign |
| File inventory, dependency graph, responsibility map | Comparative research mission |
| High-level ideal sequencing (not a Plan/Spec) | Starting Execution Manager rebuild |
| AEAP Level 1 → Level 2 if justified | Level 3 unless systemic re-audit required |

**Nenhuma alteração de código: SIM**

---

## AEAP budget

```text
AUDIT BUDGET
Nível escolhido: LEVEL 1 → expanded to LEVEL 2 (Module Audit)
Arquivos novos (produto): 0
Arquivos modificados (produto): 0
Dependências diretas inventariadas: D ≈ 25 (router helpers + engines + data/ops adjacent)
Arquivos reaproveitados / auditorias: Audit 001 §3.10–3.12; Master §4 pillar 11;
  conversation_pipeline.md; FROZEN_MODULES.md; Blueprint §9.4; Stage1 Closure 019
```

### Justification — why Level 2

Level 1 alone is insufficient because there is **no named `execution_manager` module**. The equivalent surface is **cross-cutting**: mega-router `_run_*` helpers, duplicate legacy `copilot_engine.dispatch`, analyze/live data fetch, cost/cache ops, and ad-hoc tool calls. Mapping **misplaced responsibilities** vs Context Manager / Tool Use / Orchestration (Blueprint / Master vocabulary) requires a **Module Audit (Level 2)** with a written adjacent budget — not a full hostile Level 3 reopen of Master/SSOT.

**Level 3 not used:** Master + Audit 001 already classify the pillar as Ausente/Substituir; systemic governance chain does not need re-litigation for discovery.

---

## Executive verdict (engineering)

**There is no Execution Manager module in the code SoT.**  
Master Architecture pillar #11 = **Ausente / Crítica / Substituir**.  
Runtime “execution” is **inline** inside Orchestration (primarily `copilot_unified_router.py`) plus a **legacy parallel path** (`copilot_engine` via `copilot_router`). Sports engines are invoked as a **hard-coded sequential pipeline** inside `_run_analyze`, not via a registry, skill runner, or Execution Manager API.

---

# Answers 1–12 (PO Prompt Mestre)

### 1. O que exatamente faz hoje o Execution Manager?

**Não existe como módulo nomeado.** O que a Aurora faz hoje no lugar do pilar é:

1. **Orquestrar o turno conversacional** no mega-router (`copilot` → `_copilot_inner`) — Master Intent, guards, NL/CUE/HCE, short-circuits, e depois **dispatch** por intent.  
2. **Executar pipelines de intent** via helpers `_run_analyze`, `_run_live`, `_run_bankroll`, `_run_learning`, `_run_knowledge`, etc.  
3. Em `_run_analyze`, **chamar em ordem fixa** motores Frozen (methodology → learning → confidence → market → methodology_v1 → decision_center → knowledge → intelligence) após `analyze_fixture` (I/O).  
4. Um caminho legado paralelo: `copilot_router` → `copilot_engine.dispatch` com a **mesma sequência de motores** duplicada.

Não há `ExecutionManager`, `ToolRegistry`, `run_tool`, `skill_runner`, ou `engine_runner` em `artifacts/aurora/src` (grep Mission 020; confirma Audit 001 §3.10–3.11).

### 2. Quais responsabilidades pertencem a ele?

Responsabilidades que **caem no papel esperado do pilar Execution Manager** (coordenar execução de motores/tools), **hoje exercidas pelo blob de execução**, não por um módulo isolado:

| Responsabilidade observada | Onde vive hoje |
|----------------------------|----------------|
| Coordenar sequência analyze (motores) | `_run_analyze` em `copilot_unified_router.py` |
| Coordenar live opportunities | `_run_live` → `live_intelligence_engine` + `routers/live` |
| Dispatch por intent após classificação | `_copilot_inner` + helpers `_run_*`; legado `copilot_engine.dispatch` |
| Montar payload estruturado pós-motores | Continuação de `_run_analyze` (markets, confidence labels, match card) |
| Fail-open / try-except em volta de etapas | Espalhado no router e em camadas conversacionais |

O Master **não** atribui Context Manager, Tool registry, ou Orchestration de conversa a este pilar — ver Mapa § abaixo.

### 3. Quais partes são legadas?

| Superfície | Por que legada / paralela |
|------------|---------------------------|
| `src/core/copilot_engine.py` (`detect_intent` + `dispatch` + `_handle_analyze`) | Segundo executor analyze; ainda montado via `copilot_router` |
| `src/routers/copilot_router.py` | Endpoint chat legado ao lado do unified |
| Regex intent stack em `copilot_engine` | Coexiste com Master Intent / NL / CUE no unified |
| Compat wrappers em `analyze.py` / `copilot_engine` para EntityResolver | Ponte legado → SoT de aliases |
| Mirror `aurora/` | Árvore secundária; router ~5120 linhas vs SoT ~5260 — **drift OPEN** (não corrigido) |

### 4. Quais dependências ele possui?

O blob de execução **consome** (direto):

**Data / I/O**

- `routers/analyze.analyze_fixture` → `api_football_get` / client  
- `ops/cost_protection` (budget, analyze cache key/get/set, force_refresh)  
- `data/gateway.DataGateway` (cache/throttle/circuit — data plane adjacente)  
- `conversation/web_intelligence` (enrichment web ad-hoc — Tool Use adjacent)

**Frozen / Congelar sports engines (não devem ser reescritos como EM)**

- `methodology_engine`, `methodology_v1`, `learning_engine`, `confidence_engine`, `market_engine`  
- `decision_center`, `knowledge_engine`, `intelligence_engine`, `live_intelligence_engine`  
- Integrity / partial / fixture_status / entity resolver paths

**Brain / memory / learning DB**

- `brain` config / methodology config / brain_meta  
- `memory_db.recall_context`, `learning_db.get_learning_stats`

**Conversation / Orchestration (callers & peers — not EM internals)**

- Master Intent, fiction/sport continuity guards, natural conversation, response layers  
- Context Manager surfaces (STS / sole-writer / `minimal_commit_orchestrator`) — **context commit**, not engine execution

### 5. Quais módulos o utilizam? (dependents)

| Dependent | Relação |
|-----------|---------|
| `main.py` | Monta `copilot_unified_router` e `copilot_router` |
| Frontend Copilot / clients HTTP | Consomem `POST /aurora/copilot` (unified) e legado chat |
| Camadas conversacionais no mesmo router | Decidem *se* o pipeline sport/analyze roda; depois chamam `_run_*` |
| `tests/*` | Exercitam engines, integrity, router behaviours; poucos testes tratam “EM” como unidade (inexistente) |
| Mirror `aurora/` | Cópia parcial do mesmo padrão (inventário only) |

Nenhum módulo importa `execution_manager` — **dependents dependem do router/helpers**, não de uma API de EM.

### 6. Onde estão os maiores problemas?

1. **Ausência do pilar** — execução misturada com Orchestration conversacional no mesmo arquivo (~5260 linhas).  
2. **Dupla via de execução** — unified `_run_analyze` vs `copilot_engine._handle_analyze` (risco de drift de comportamento).  
3. **Sem contrato de Tool Use** — APIs/web/gateway chamados ad-hoc (Audit 001 §3.10); EM futuro não pode absorver isso sem confundir pilares.  
4. **Ordem de motores hard-coded** — correta operacionalmente hoje, mas sem registry/versão/observabilidade de “step” como produto do EM.  
5. **Responsabilidades de contexto no mesmo blob** — `_save_analysis_context` e flags `sport_pipeline_blocked` convivem com execução de motores (fronteira CM).  
6. **Mirror drift** — Activation/deploy risk herdado (Stage1 / Blueprint), não específico de EM mas afeta qualquer rebuild.

### 7. O que deve permanecer?

*(Descoberta descritiva — não é Spec. “Permanecer” = comportamento/valor que um rebuild não deve destruir.)*

- Sequência Frozen de motores analyze (methodology → … → intelligence) e contratos de payload Analyze.  
- Integrity / PARTIAL / Resolver gates antes de inventar mercados.  
- Fail-open culture nas camadas conversacionais; cost_protection budget defaults.  
- Separação já conquistada: **Context Manager FROZEN** (STS sole-writer / shadow / gates) — EM **não** reabre writers.  
- Engines listados em `docs/FROZEN_MODULES.md` — consumir, não retunar.

### 8. O que deve ser descartado?

*(Como responsabilidade do futuro EM / como superfície legada — não como ordem de apagar código agora.)*

- Ideia de que o mega-router **é** o Execution Manager.  
- Duplicação sustentável `copilot_engine.dispatch` vs unified `_run_*` (legado a aposentar sob missão governada).  
- Misturar **controle de contexto conversacional** e **ordem de motores** no mesmo owner futuro.  
- Tratar `minimal_commit_orchestrator` / LangGraph STS host como Execution Manager (são host de **context commit**, Audit/Master).  
- Inventar Tool Registry *dentro* do EM sem missões Tool Use / Orchestration alinhadas.

### 9. Quais riscos existem na reconstrução?

| Risco | Por quê |
|-------|---------|
| Regressão de analyze/live UX | Toda a percepção de “Aurora pensou o jogo” passa por `_run_analyze` / `_run_live` |
| Quebra de Frozen engines | EM mal delimitado tenta “melhorar” methodology/market/confidence |
| Dual-SoT temporário | Novo EM + legado `_run_*` + `copilot_engine` = três caminhos |
| Contaminação de Context Manager | Reabrir writers / misturar commit de STS com execução de motores |
| Confusão Tool Use ↔ EM | Gateway/web/API sem registry; puxar I/O para EM sem contrato |
| Mirror / Activation | Drift `aurora/` vs `artifacts/aurora/` em cut-over |
| Big-bang | Substituir mega-router de uma vez viola Blueprint ladder / Zero User Impact |

### 10. Quais responsabilidades não deveriam estar nele?

| Responsabilidade | Owner correto (Master/Blueprint vocabulary) |
|------------------|-----------------------------------------------|
| Sole-write de subject esportivo / STS / episode | **Context Manager** (FROZEN cycle) |
| Classificar intent conversacional / Master Intent / CUE | **Understanding / Orchestration** de turno |
| Registry/schema/permission de tools | **Tool Use** (ainda ad-hoc) |
| Ordem de camadas conversacionais (HPL → Reasoner → CRL…) | **Orchestration** (`conversation_pipeline.md`) |
| Formulas Frozen de methodology/market/confidence/learning/knowledge/decision | **Engines Frozen** (consumidas, não “geridas” como lógica do EM) |
| Personalização FE | Frozen FE — fora de EM |

### 11. Quais responsabilidades estão espalhadas pelo projeto?

| Responsabilidade | Espalhamento observado |
|------------------|------------------------|
| Invocar pipeline analyze | `copilot_unified_router._run_analyze` **e** `copilot_engine._handle_analyze` |
| Fetch fixture / API | `routers/analyze`, client, gateway, cost_protection cache |
| Budget / cache hit-miss | `ops/cost_protection` (+ analyze inner) |
| Web enrichment | `web_intelligence` (fora do `_run_analyze` principal) |
| Live path | `_run_live` + `routers/live` + `live_intelligence_engine` |
| “Orchestrate” nome | `minimal_commit_orchestrator` = context commit; **não** engine execution |
| Dispatch intent | Unified inner + legado `copilot_engine.dispatch` + NL routers |

### 12. Qual seria a ordem ideal da futura implementação?

*(Sequenciamento alto nível apenas — **não** é Spec, Plan 014, nem autorização de código.)*

1. **Fechar Discovery** (esta missão) + PO gate.  
2. **Research/Spec do EM** com fronteiras explícitas vs Tool Use + Orchestration + CM FROZEN (sem reabrir CM).  
3. **CDR/AAR** nos forks críticos (o que é EM vs Tool vs Orchestrator).  
4. **Implementation Plan + PO + Readiness** (Blueprint).  
5. **Prep/Infra** — contrato fino de “run engine steps / run analyze pipeline” defaults OFF.  
6. **Shadow** do novo executor ao lado de `_run_analyze` (comparar payloads).  
7. **Sole path / gated cut-over** do unified helper; legado `copilot_engine` em missão de retirement.  
8. **Não** acoplar Activation full-env nem Tool Use registry completo na mesma escada sem gates próprios.

---

# Mapa de Responsabilidades (obrigatório)

| Responsabilidade | Está no lugar certo? | Observação |
|------------------|----------------------|------------|
| Coordenar execução dos motores analyze | **Não** (módulo EM ausente) | Vive inline em `_run_analyze` / duplicado em `copilot_engine` — papel de EM, dono errado (Orchestration blob) |
| Decidir ordem dos motores Frozen | **Parcialmente** | Ordem atual é estável e valiosa; deveria permanecer como contrato consumido pelo futuro EM, **não** reinventada ad hoc no router |
| Chamar APIs (API-Football / fixture fetch) | **Não (para EM)** | Correto em data/analyze/client/gateway — adjacente a **Tool Use** / data plane, não Core EM |
| Cache de analyze / prefer stale | **Não (para EM)** | `cost_protection` + gateway — ops/data; EM pode *respeitar* budget, não *ser* o cache |
| Controlar contexto / subject esportivo | **Não** | Context Manager FROZEN / STS / sole-writer; `_save_analysis_context` no router é residual de Orchestration+CM |
| Classificar intent / bloquear sport pipeline | **Não** | Understanding + Orchestration (Master Intent, guards) |
| Registry de tools / web fetch | **Não** | Tool Use ausente/parcial (Audit §3.10); `web_intelligence` solto |
| Orquestrar camadas conversacionais (CUE→…→UI) | **Não** | Orchestration / pipeline map — distinto de EM |
| Commit STS / minimal commit orchestrator | **Não** | Context commit host — **não** Execution Manager |
| Montar payload UI / match card pós-engines | **Parcial** | Hoje no router após motores; pode ficar adapter de Orchestration/FE contract, não fórmula de motor |
| Budget / cost protection em volta de calls | **Parcial** | Ops correto; EM futuro deve integrar *decision* de “pode executar?”, sem absorver o módulo ops |
| Duplicar dispatch legado (`copilot_engine`) | **Não** | Legado; risco de drift |

---

# File inventory (SoT + mirror awareness)

## Primary execution surface (artifacts/aurora — Code SoT)

| Path | Role in “EM equivalent” |
|------|-------------------------|
| `src/routers/copilot_unified_router.py` (~5260 LOC) | **Primary** orchestration + `_run_*` execution blob |
| `src/core/copilot_engine.py` (~841 LOC) | **Legacy** intent+dispatch+engine sequence |
| `src/routers/copilot_router.py` | Legacy HTTP chat → `copilot_engine` |
| `src/routers/analyze.py` | Fixture fetch / analyze data assembly + cost cache hooks |
| `src/routers/live.py` | Live fixtures feed for `_run_live` |
| `src/core/methodology_engine.py` | Frozen engine step |
| `src/core/methodology_v1.py` | Frozen engine step |
| `src/core/learning_engine.py` | Frozen engine step |
| `src/core/confidence_engine.py` | Frozen engine step |
| `src/core/market_engine.py` | Frozen engine step |
| `src/core/decision_center.py` | Frozen engine step |
| `src/core/knowledge_engine.py` | Frozen engine step |
| `src/core/intelligence_engine.py` | Report assembly step |
| `src/core/live_intelligence_engine.py` | Live path |
| `src/ops/cost_protection.py` | Budget + analyze cache |
| `src/data/gateway.py` | Data gateway cache/throttle |
| `src/conversation/web_intelligence.py` | Ad-hoc web tool path |
| `src/main.py` | Mounts both copilot routers |
| `docs/conversation_pipeline.md` | Documents conversational order (Orchestration), engines as pass-through step 10 |

## Explicitly **not** Execution Manager (boundary)

| Path | Actual role |
|------|-------------|
| `src/conversation/minimal_commit_orchestrator.py` | Context commit host (CM) |
| `src/conversation/langgraph_state_graph.py` | STS/LangGraph host candidate (CM) — shadow defaults OFF |
| `src/conversation/sole_writer_funnel.py` | CM sole-writer funnel |
| Conversation guards / Master Intent / CUE / HCE / CRL | Understanding / Orchestration / CM projections |

## Mirror `aurora/` (inventory only)

- Present: `aurora/src/...` including routers/core/conversation.  
- `copilot_unified_router.py` ~5120 lines vs SoT ~5260 — **non-parity**.  
- No `execution_manager` identifiers found in mirror core/routers grep sample.  
- **Do not fix drift in this mission.**

## Governance / prior evidence cited

| Artifact | Use |
|----------|-----|
| `docs/architecture/master-architecture.md` §4 #11 | Pillar Ausente / Substituir |
| `observations/aurora_core_audit_001/REPORT.md` §3.10–3.12 | Tool Use / EM / Orchestration audit |
| `docs/architecture/governance/AURORA_MODULE_BLUEPRINT.md` | Process law for next module |
| `docs/FROZEN_MODULES.md` | Engines untouchable internals |
| `observations/aurora_stage1_closure_019/...` | Etapa 1 closed; await PO for Etapa 2 |

---

# Dependency graph (textual)

```text
[HTTP clients / FE]
        │
        ├─► copilot_unified_router.copilot / _copilot_inner     ◄── PRIMARY Orchestration
        │         │
        │         ├─► Understanding / guards / CM projections (not EM)
        │         │
        │         └─► _run_analyze / _run_live / _run_*         ◄── EM-EQUIVALENT BLOB
        │                   │
        │                   ├─► analyze_fixture / live router     (I/O / Tool-adjacent)
        │                   │         ├─► api client
        │                   │         ├─► cost_protection cache
        │                   │         └─► data gateway
        │                   │
        │                   └─► Frozen engines sequence
        │                             methodology → learning → confidence
        │                             → market → methodology_v1 → decision_center
        │                             → knowledge → intelligence
        │
        └─► copilot_router.chat → copilot_engine.dispatch      ◄── LEGACY PARALLEL

[minimal_commit_orchestrator / LangGraph STS]
        └── Context Manager path (orthogonal; must not be folded into EM)
```

---

# Duplications, bottlenecks, risks

### Duplications

- Analyze engine sequence: unified `_run_analyze` **≈** `copilot_engine._handle_analyze`.  
- Intent routing: Master/NL/CUE vs legacy regex in `copilot_engine`.  
- Dual HTTP surfaces mounted in `main.py`.

### Bottlenecks

- Single mega-file owns conversation Orchestration **and** engine execution.  
- Any EM change today requires editing the highest-risk file in the product.  
- No step-level Execution API → hard to shadow/compare safely.

### Risks

- See Q9. Highest product risk: silent analyze regression. Highest architecture risk: EM that reopens CM or swallows Tool Use.

---

# Impact of a future rebuild (descriptive — not Spec)

Replacing the inline blob with a real Execution Manager would:

- **Touch** the hot path of every analyze/live copilot turn.  
- **Require** dual-run/shadow against current `_run_analyze` payloads before cut-over.  
- **Force** an explicit retirement plan for `copilot_engine` / `copilot_router`.  
- **Must not** move STS writes, Master Intent, or Frozen engine formulas into the new module.  
- **Should** leave API/cache/gateway behind clear Tool Use / data-plane boundaries (even if initially thin adapters).  
- **Remain** defaults-OFF / PGR-ladder compatible per Blueprint (when authorized).

---

# Ideal future implementation order (high-level only)

See **Q12**. Reminder: **await PO** before Research 021 / Spec / architecture / code.

---

# REPORT 1 — ENGINEERING REPORT

## Identity

| Field | Value |
|-------|-------|
| Mission | 020 MODULE_DISCOVERY — Execution Manager |
| Branch | `feat/aurora-response-selector-001` |
| Commit message | `docs(research): add Execution Manager Discovery Report (Mission 020)` |
| Commit hash | `caed099cc1f01ddc1a6310cb3820f29ba221719b` (discovery body); evidence stamp in follow-up commit |
| Push | **YES** — `origin/feat/aurora-response-selector-001` (`63f7475..caed099`, plus evidence follow-up) |
| Product code | **Nenhuma alteração de código: SIM** |

## Scope

| In | Out |
|----|-----|
| Diagnostic report under `observations/execution_manager_discovery_020/` | Spec, ADR, comparative research |
| Answers 1–12 + responsibility map + Dual Reporting | EM rebuild / product mutation |
| AEAP L1→L2 | Level 3; Master edits; mirror drift fix |

## Evidence method

- Grep SoT: no `execution_manager` / `ExecutionManager` / `ToolRegistry` / `run_tool`.  
- Read: Master pillar 11; Audit 001 §3.10–3.12; `conversation_pipeline.md`; `_run_analyze` engine sequence; `copilot_engine.dispatch`; `main.py` router mounts; cost_protection; gateway; Blueprint §3/§9.4.  
- Size: unified router ~5260 LOC; legacy engine ~841 LOC; mirror router ~5120 LOC.

## Architecture / governance

- Master / Spec / ADRs / Blueprint content: **not modified**.  
- Context Manager: **FROZEN** — not reopened.  
- REGRA 29 Dual Reporting: this file.  
- Next: **await PO** — do not start Research 021 / Spec / rebuild.

## Safety

- Docs-only; no flags flipped; no runtime behaviour change.  
- Rollback of this mission = revert docs commit.

## Validations

| Check | Result |
|-------|--------|
| AEAP Level recorded + justified | YES (L2 Module Audit) |
| 12 PO questions answered | YES |
| Mapa de Responsabilidades | YES |
| Dual Reporting Eng + PO | YES |
| Code unchanged | YES |
| Spec / rebuild started | **NO** |

## Residual / next

- PO review of Discovery.  
- Optional later: Research/Spec EM (only if PO authorizes).  
- Mirror drift remains OPEN (Activation residual — not this mission).

---

# REPORT 2 — PRODUCT OWNER REPORT

📋 PRODUCT OWNER REPORT

✅ O que fizemos hoje

Abrimos a Etapa 2 com uma **missão só de entendimento**: mapear o que hoje faz o papel de “Execution Manager” na Aurora. Não escrevemos código de produto, não desenhamos a solução nova e não começamos a reconstrução.

🧠 O que isso significa

Descobrimos que esse “cérebro de execução” **ainda não existe como peça separada**. Hoje a Aurora **executa os motores esportivos dentro do grande roteador da conversa** (e ainda tem um caminho antigo paralelo). Antes de reconstruir, agora sabemos onde está a bagunça e o que **não** deve ser misturado com o Context Manager que acabamos de congelar.

👤 O usuário percebe diferença?

**Não.** Esta missão só produziu um relatório de diagnóstico. O produto em produção não mudou.

⚠️ Existe algum risco?

Risco desta missão: **baixo** (só documentos).  
Risco que o relatório deixa claro para o futuro: se reconstruirmos sem cuidado, podemos quebrar a análise de jogos, reabrir o Context Manager, ou misturar “chamar APIs” com “coordenar motores”. Por isso a próxima etapa precisa da sua autorização explícita.

🎯 O que ainda falta?

- Sua leitura e aprovação deste Discovery.  
- Só depois: pesquisa/especificação do Execution Manager (missões futuras — **ainda não iniciadas**).  
- Continuar respeitando o Context Manager congelado e os motores esportivos protegidos.

📊 Quanto falta?

Para **esta** Missão 020 (entender o módulo atual): praticamente concluída após commit/push.

```text
████████████████████  100%
```

(Missão 020 Discovery concluída e publicada no Git. A reconstrução do Execution Manager permanece em **0%** — deliberadamente não começou.)

🏗️ Analogia simples

É como querer reformar a **cozinha industrial** (onde os pratos são de fato preparados) e descobrir que hoje os fogões estão no meio da **sala de atendimento**. O Context Manager já organizou o “quem é o assunto da conversa”; agora vimos que ainda falta uma cozinha com dono claro — mas **não começamos a obra**.

📝 Resumo em uma frase

O Execution Manager atual **não existe como módulo**; a execução está embutida no roteador — e a Missão 020 só documentou isso, sem mudar o produto, aguardando o Product Owner.
