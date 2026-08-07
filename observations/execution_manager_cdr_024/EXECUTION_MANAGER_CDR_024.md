# AURORA — CRITICAL DESIGN REVIEW — Execution Manager CDR-001

**MISSION ID:** `execution_manager_cdr_024`  
**DOCUMENT:** `EXECUTION_MANAGER_CDR_024.md`  
**VERSION:** 1.0  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** CRITICAL_DESIGN_REVIEW (documentation only)  
**PRIMARY TARGET:** `observations/execution_manager_spec_023/SPEC_EXECUTION_MANAGER_v1.0.md`  
**CODE SoT (reference only):** `artifacts/aurora/`  
**STATUS:** COMPLETE (await Product Owner)  
**SPEC MUTATION / AAR / IMPLEMENTATION:** **DO NOT START** — await PO  

**Nenhuma alteração de código: SIM**

---

## Hard scope locks

| Allowed | Forbidden |
|---------|-----------|
| Hostile CDR of Spec EM v1.0 only | Product code |
| Dual Reporting (REGRA 29) on this CDR artifact | Spec / ADR / Master / Blueprint / SSOT edits |
| AEAP Level 1 on CDR deliverable only | AAR, Implementation Plan, rebuild |
| Citations to 020 / 021 / 022 / Blueprint / Master (read-only) | Pretend Critical findings |

---

## Review stance

Hostile Architecture Review Board: **assume Spec is wrong** until it survives cross-examination against Discovery 020, Surface 021, Research 022, Blueprint, and Master pillar #11 (read-only).

**Locked family under test (Mission 022 — not reopened):**

```text
Deterministic Sequential Pipeline
+ Step Runner
+ Shadow-first
+ Context Manager write-free
+ Tool Use separado
```

This CDR does **not** invent a new pattern family. It asks whether Spec v1.0 is **complete and decidable enough** to implement without violating 020/021 must-stay behaviour or CM/Tool Use boundaries.

---

## Binding exhibits (read-only)

| Exhibit | Role |
|---------|------|
| Spec v1.0 (`SPEC_EXECUTION_MANAGER_v1.0.md`) | Defendant |
| Discovery 020 | Absence of EM; mega-router blob; dual legacy; CM/Tool Use risks |
| Surface Map + Report 021 | Destino Futuro; `_run_*`; integrity dual-path; `_save_analysis_context`; soft-analyze |
| Research 022 + Comparative | Pattern family; anti-patterns |
| Blueprint §5 / §9.4 | Shadow, PGR, Zero User Impact |
| Master §4 pillar #11 | Ausente / Substituir (read-only) |
| Spec Report 023 | Spec self-claims (cross-check only) |

---

## AEAP (Level 1 — CDR artifacts only)

```text
AUDIT BUDGET
Nível escolhido: LEVEL 1 (Audit only artifacts produced this mission)
Arquivos novos (produto): 0
Arquivos modificados (produto): 0
Arquivos novos (observations): 1
  - EXECUTION_MANAGER_CDR_024.md
Dependências diretas inventariadas (docs): Spec 023 + Missions 020/021/022 + Blueprint §5 + Master #11 (RO) + Dual Reporting REGRA 29
Elevação L2/L3: NÃO — CDR docs-only; no product delta; no Master reopen
```

---

# REPORT 1 — ENGINEERING REPORT (full CDR)

## 1. Identity

| Field | Value |
|-------|-------|
| Mission | 024 CRITICAL_DESIGN_REVIEW — EM CDR-001 |
| Branch | `feat/aurora-response-selector-001` |
| Commit message | `docs(review): add Execution Manager CDR-001` |
| Commit hash | `492a6f64cdf3a9ca1668ae074f74dab503fac559` (CDR body); stamp `7e0c628eb342a0545285d4d158e8a7d400b04c49` |
| Push | **YES** — `origin/feat/aurora-response-selector-001` (`a01a563..7e0c628`) |
| Product code | **Nenhuma alteração de código: SIM** |
| Spec edited | **NO** |
| AAR started | **NO** |

## 2. Verdict (normative)

```text
STATUS
IMPLEMENTABLE
NÃO
```

**Blockers:** **2 High** (no Critical). Spec family lock and CM/Tool Use separation **survive**. Spec is **not** yet decidable for soft-analyze / caller integrity / CM-commit eligibility as evidenced by Mission 021 surface.

| Severity | Count | Blockers |
|----------|------:|----------|
| Critical | 0 | — |
| High | 2 | **2 blockers** |
| Medium | 7 | improvements |
| Low | 4 | improvements |

## 3. What survived cross-examination (credit)

| Claim | Result |
|-------|--------|
| Locked 022 family restated without reopen | **PASS** — Spec header lock + O2/R1–R10 |
| Mega-router is **not** EM; EM extracts `_run_analyze` / `_run_live` / thin reports | **PASS** — aligns 020/021 extract candidates |
| Greeting/help/identity/capabilities/fallback stay Router | **PASS** — §5.1 / G10 / NR3 |
| CM write-free; `_save_analysis_context` **not** EM | **PASS** — NR1 / G1 / §6.1 / §4.6 |
| Tool Use via ports only; no registry in EM | **PASS** — R4 / NR4 / G3 / §4.5 |
| Frozen engine order A3–A10 locked to 021 L543–584 | **PASS** — §5.2 |
| Shadow defaults OFF; fail-open; ZUI | **PASS** — §11 / §12 / G5 |
| Progressive Activation Blueprint ladder | **PASS** — §12 |
| Legacy `copilot_engine` retirement pre-declared (not silent forever) | **PASS** — O7 / F10 / §6.6 |
| No LLM step selection | **PASS** — NR7 / G2 / §5.6 |
| LangGraph STS host ≠ EM | **PASS** — NR8 / G9 |
| Testability includes boundary “no `_save_analysis_context`” | **PASS** — §15 |
| Master #11 not edited; Spec under observations | **PASS** — governance hygiene |

**Bottom line:** Architecture **shape** is implementable in principle. Spec **edge contracts** around integrity/soft-analyze/caller CM eligibility are **not**.

---

## 4. Findings catalog

### CDR-H-001 — A2 “INVALID → abort” oversimplifies soft-analyze must-stay
- **Severidade:** High (**BLOCKER**)
- **Categoria:** Pipeline / Architecture contradiction
- **Evidência:**
  - Spec §5.2 A2: “INVALID → abort pipeline”; PARTIAL continues.
  - Spec R3 claims “PARTIAL / soft-analyze fail-open culture” as Step Runner edges.
  - Surface 021 “Must stay”: Soft analyze + integrity INVALID/PARTIAL behaviour (`EXECUTION_SURFACE_MAP.md` §10; Report §13).
  - SoT `copilot_unified_router.py`: inside `_run_analyze` ~L502–527 early abort exists **with** alias-missing soft skip (“skipped INVALID early abort”); caller ~L3851–3873 **tries soft analyze when precheck INVALID**, sets `prefer_live` from integrity, then post-applies integrity.
- **Impacto:** Naive Spec-faithful implementer hard-aborts all INVALID → regresses soft-analyze UX Discovery/Surface marked must-stay. Internal Spec tension: A2 absolute vs R3 “current culture”.
- **Recomendação:** Before Spec acceptance for Plan: make A2 **decidable** — enumerate INVALID subtypes / soft-skip exceptions **or** normative “A2 semantics ≡ Mission 021 surface + SoT `_run_analyze` integrity block (including soft skip)” with explicit golden cases. Do not leave absolute abort language unreconciled with soft-analyze.

### CDR-H-002 — Caller soft-analyze + post-integrity + conditional CM save absent from Orchestration contract
- **Severidade:** High (**BLOCKER**)
- **Categoria:** Separation / Dependencies / Governance (CM boundary)
- **Evidência:**
  - Surface 021 §9 / Map §231: “integrity post-check + `_save_analysis_context` sit *outside* `_run_analyze` but are part of after execute (Router/CM).”
  - Map row integrity: `_run_analyze` L502–527 **+ caller** L3851–3873 — Destino **Avaliar**.
  - Spec §4.6 Caller contract: build request → `run` → present payload → CM commit “after success acceptance” — **no** normative table for: precheck soft-try, `prefer_live` derivation, post-EM `_apply_integrity`, when `_save_analysis_context` / CM sole-write may run, live ctx seed exclusion (NR1).
  - Spec Flow §7 jumps EM → presentation → CM separate; omits Orchestration integrity wrap that 021 proves exists.
  - Spec correctly forbids EM owning `_save_analysis_context` (NR1) but does not specify Orchestration **acceptance predicates** that today gate the write (~L3906–3908 pattern).
- **Impacto:** Extraction can (a) absorb CM write into EM adapter “for convenience”, or (b) drop soft-analyze wrap, or (c) invent a third integrity authority — recreating mega-router coupling / CM contamination Discovery 020 warned about.
- **Recomendação:** Add normative **Orchestration post/pre-EM contract** (still not EM responsibilities): inputs to soft-try, flags emitted (`prefer_live`, soft hints), reading of `ExecutionResult.abort_reason` / `fixture_quality`, **CM commit eligibility matrix**, and explicit “live ctx seed remains CM residual / out of EM”. Resolve Avaliar integrity **sequencing** ownership without moving formula ownership out of `fixture_integrity`.

### CDR-M-001 — match_card dual signal (Router Destino vs EM optional adapter)
- **Severidade:** Medium
- **Categoria:** Separation / Ambiguity
- **Evidência:** Surface Map: match_card attach → **Router** / FE. Spec NR6: match_card coerce → Router. Spec A13/L4: “Optional adapter”; “EM may emit fields Router needs”.
- **Impacto:** Implementers may call `attach_match_card` inside EM, preserving `_run_analyze` coupling 021 flagged.
- **Recomendação:** Normative: EM **never** calls `attach_match_card`; may only emit raw fields; Router owns attach/coerce. Remove “optional adapter” wording or mark **Forbidden**.

### CDR-M-002 — `cancel(run_id)` optional in §4.1 but normative in §9
- **Severidade:** Medium
- **Categoria:** Interfaces / Ambiguity
- **Evidência:** §4.1 lists `cancel` as “Optional future (post-Infra)”. §9 Cancelamento treats `cancel(run_id)` as policy now.
- **Impacto:** Interrupted/cancel tests and Infra scope unclear.
- **Recomendação:** Either promote cancel to v1.0 required API or demote §9 cancel to “future; timeout is the v1.0 interrupt path”.

### CDR-M-003 — Retry state vs Result status / run_id policy underspecified
- **Severidade:** Medium
- **Categoria:** Pipeline / Observability
- **Evidência:** §8 Retry → Running “new or same run_id per policy”. §4.3 status list uses ellipsis; Retry is state not Result status.
- **Impacto:** Shadow correlation and metrics can fork silently.
- **Recomendação:** Fix status enum (no ellipsis); declare run_id immutability (retry = new `run_id`) as default.

### CDR-M-004 — Shadow compare allowlist deferred without interim parity criteria
- **Severidade:** Medium
- **Categoria:** Testability / Progressive Activation
- **Evidência:** §11 “tolerate non-semantic noise via declared allowlist (Plan/Infra later)”. Prep baselines claimed in §12 without field-level compare contract.
- **Impacto:** Green Shadow can mean “noise drowned signal”.
- **Recomendação:** Spec appendix: minimum mandatory compare keys (markets, fixture_quality, abort_reason, engine step order) vs explicitly deferred noise (timestamps, DRS stamp churn).

### CDR-M-005 — Budget dual layer (Router `begin_request` vs EM A0) not bridged
- **Severidade:** Medium
- **Categoria:** Dependencies / Separation
- **Evidência:** Surface: `cost_protection.begin/end_request` wraps HTTP turn (Router+ops). Spec A0 `budget_check` + opaque `budget_token`. R8: honor without absorbing cache.
- **Impacto:** Double-gate or token never plumbed from turn scope.
- **Recomendação:** Normative: who mints `budget_token` (Orchestration/ops adapter); A0 only consults port; EM never calls `begin_request`.

### CDR-M-006 — G6 “one official executor” vs Phase 4 “legacy `_run_*` may remain”
- **Severidade:** Medium
- **Categoria:** Progressive Activation / Dual-SoT honesty
- **Evidência:** G6 vs §12 Phase 4; Discovery Q9 three-path risk (EM + `_run_*` + `copilot_engine`).
- **Impacto:** Temporary dual-SoT during climb is inevitable; Spec softens but can be read as immediate single SoT.
- **Recomendação:** Explicit dual-SoT **window** language: sole-path ON ⇒ one *official* unified executor; `_run_*` shim allowed until retirement mission; `copilot_engine` never counts as Shadow substitute (already §13 — strengthen G6 footnote).

### CDR-M-007 — Thin `Db.port` vs Tool Use separation purity
- **Severidade:** Medium
- **Categoria:** Separation
- **Evidência:** §4.5 `Db.port(learning_stats|knowledge_search|memory_recall)`; Research 022 prefers Tool Use ports for I/O; Surface allows thin EM DB→payload.
- **Impacto:** Mild pillar blur for knowledge/memory recall inside analyze A9 vs thin pipelines.
- **Recomendação:** Keep thin report DB ports as EM-local **read adapters** labeled non-registry; clarify A9 `memory_db.recall_context` remains Frozen-sequence consume (not CM write).

### CDR-L-001 — `pipeline_id` naming (`live_team_analyze` vs intent `live_team_analysis`)
- **Severidade:** Low
- **Categoria:** Interfaces
- **Evidência:** §4.2 enum vs Surface intent name.
- **Impacto:** Mapping bugs in Orchestration adapter.
- **Recomendação:** Alias table in Spec.

### CDR-L-002 — Result `status` ellipsis (“… terminal”)
- **Severidade:** Low
- **Categoria:** Interfaces
- **Evidência:** §4.3.
- **Impacto:** Contract tests cannot close.
- **Recomendação:** Closed enum aligned to §8 terminals.

### CDR-L-003 — Feature flag names fully deferred
- **Severidade:** Low
- **Categoria:** Progressive Activation
- **Evidência:** §12 “flag names deferred to Implementation Plan”; Phase 2 mentions illegal matrix.
- **Impacto:** Acceptable for Spec if Plan owns names; illegal combinations should be sketched.
- **Recomendação:** Sketch illegal matrix principles (shadow+sole conflicting, EM write flags nonexistent, etc.) without final env names.

### CDR-L-004 — Fail-open per step “by current culture” without step matrix
- **Severidade:** Low
- **Categoria:** Testability
- **Evidência:** §5.6 / §9; points at `_run_analyze` culture.
- **Impacto:** Plan must reverse-engineer; Spec incomplete as sole SoT.
- **Recomendação:** Appendix step×fail-open table in Spec revision (can cite 021 line ranges).

---

## 5. PO section validation matrix

| PO section | Verdict | Notes |
|------------|---------|-------|
| Architecture | **FAIL (High)** | Family OK; A2 vs soft-analyze + Avaliar integrity unresolved |
| Separation Router/CM/Tool/EM | **FAIL (High)** | CM write forbidden OK; caller CM eligibility + soft wrap missing; match_card Medium |
| Pipeline deterministic? | **CONDITIONAL** | Frozen order yes; soft-analyze/prefer_live edges underspecified |
| Dependencies | **PASS w/ Medium** | No circular; budget dual-layer Medium; Db.port Medium |
| Progressive Activation | **PASS w/ Medium** | Ladder/Shadow/Rollback OK; G6 wording Medium |
| Testability | **PASS w/ Medium** | Strong §15; Shadow allowlist + fail-open matrix gaps |
| Observability | **PASS** | Events + step_traces adequate for Spec stage |
| Governance SSOT/AEL/AEAP/Rules 19–29 | **PASS** | Docs-only; F13; REGRA 23–28 mirrored; Dual Reporting this file |

## 6. Evidence cross-walk (Spec claims vs 020/021/022)

| Topic | Spec claim | Evidence | CDR call |
|-------|------------|----------|----------|
| Mega-router coupling | Extract EM from `_run_*` | 020 blob; 021 extract map | Survives |
| `_save_analysis_context` | NR1 CM not EM | 021 CM contamination | Survives (ownership) / **fails** (caller eligibility — H-002) |
| Dual legacy paths | Parallel until retirement | 020/021 `copilot_engine` | Survives with M-006 |
| Tool Use ports | FetchFixture / FetchLiveFeed | 022 Q7; 021 Tool Use adj | Survives |
| Integrity | A2 abort INVALID | 021 Avaliar dual-path + soft | **H-001 / H-002** |
| Soft-404 | Orchestration flags | 021 L4182 caller | Partial pass; soft-analyze ≠ soft-404 |
| match_card | Prefer Router | 021 Router Destino | M-001 |
| Shadow-first | §11 | 022 + Blueprint | Survives |

## 7. Architecture / governance notes

- **No ADR created** (forbidden this mission).
- **No Spec edit** (forbidden this mission) — blockers imply **Spec revision mission** if PO agrees, then re-CDR or delta CDR.
- **Master / Blueprint / SSOT:** untouched.
- **AAR:** not started.
- **Implementation authorization:** remains **NOT AUTHORIZED**.

## 8. Safety

- Docs-only under `observations/execution_manager_cdr_024/`.
- Rollback = revert this docs commit.
- Zero User Impact: no flags, no runtime change.

## 9. Validations

| Check | Result |
|-------|--------|
| Reviewed Spec §§1–16 | YES |
| Compared to 020/021/022 | YES |
| Hostile stance | YES |
| Critical findings invented | NO (0 Critical) |
| Code changed | NO |
| Spec changed | NO |
| AAR started | NO |
| Dual Reporting | YES |

## 10. Residual / next (await PO)

1. PO accepts CDR verdict **NÃO**.  
2. Spec revision mission to clear **CDR-H-001** and **CDR-H-002** (and preferably Medium pack).  
3. Re-CDR or delta CDR on revised Spec.  
4. Only then Implementation Plan / Readiness.  
5. Do **not** start AAR or product code from this mission.

## 11. Engineering brief

EM Spec v1.0 locks the right pattern family and hard boundaries (CM write-free, Tool Use ports, Router conversational purity, Frozen order, Shadow/PGR). It **fails IMPLEMENTABLE** because integrity/soft-analyze semantics and the Orchestration↔CM caller contract are not decidable against Mission 021 surface evidence—two High blockers, zero Critical. Fix Spec; do not implement yet.

---

# REPORT 2 — PRODUCT OWNER REPORT

📋 PRODUCT OWNER REPORT

✅ O que fizemos hoje

Fizemos a **revisão crítica de design (CDR)** da especificação do Execution Manager v1.0 — só documentos, sem mudar o Spec e sem começar a construção. O time técnico tentou **quebrar** a especificação de propósito (como um auditor hostil), comparando-a com as descobertas das missões 020, 021 e 022.

🧠 O que isso significa

A ideia geral da cozinha industrial (linha de produção fixa, sem misturar com a memória da conversa nem com um robô improvisando etapas) **está boa e alinhada** com o que já tinha sido aprovado.  
Porém a especificação ainda **não está pronta para construir**: em dois pontos importantes ela fica vaga ou contraditória em relação ao comportamento real que hoje não pode ser perdido (análise “suave” quando os nomes dos times estão incompletos / duvidosos, e a regra de **quando** gravar o contexto depois da análise). Sem fechar isso, um implementador bem-intencionado pode quebrar a experiência do usuário ou reabrir o Context Manager.

👤 O usuário percebe diferença?

**Não.** Esta missão só produziu o relatório de revisão. O produto em produção não mudou.

⚠️ Existe algum risco?

- **Risco desta missão:** baixo (só documentação).  
- **Risco se ignorarmos o veredito e construirmos agora:** alto — dá para “seguir o Spec” e ainda assim estragar a análise suave ou misturar gravação de contexto com o executor.  
- Por isso o veredito técnico é **não implementável ainda** (falta revisar o Spec), não “arquitetura errada”.

🎯 O que ainda falta?

- Sua leitura deste CDR.  
- Se concordar: uma **missão de revisão do Spec** só para corrigir os dois bloqueios (e, de preferência, os ajustes médios).  
- Depois: novo CDR (ou CDR delta) → só então plano de implementação.  
- **Não** começar AAR nem código agora.

📊 Quanto falta?

Para **esta** Missão 024 (CDR): concluída após commit/push.

```text
████████████████████  100%
```

Para o **Execution Manager poder ser construído com segurança**: ainda não — Spec precisa de correção. Estimativa honesta do programa EM após este CDR:

```text
████░░░░░░░░░░░░░░░░  20%
```

(Descoberta + mapa + pesquisa + Spec rascunho feitos; CDR reprovou implementabilidade; construção em **0%**.)

🏗️ Analogia simples

É como revisar a **planta da cozinha** antes de comprar os fogões: o modelo de linha de produção está certo, mas duas portas importantes (quando abortar um pedido “inválido” e quando o livro de pedidos — o Context Manager — pode ser atualizado) ainda estão mal desenhadas na planta. *Shadow Mode* continua sendo o aluno que observa o professor; *Rollback* continua sendo voltar ao estado anterior — nada disso foi ligado no produto hoje.

📝 Resumo em uma frase

O CDR conclui **IMPLEMENTABLE = NÃO**: a arquitetura escolhida sobrevive, mas o Spec v1.0 tem **dois bloqueios altos** (análise suave / integridade e contrato de gravação de contexto) que precisam de revisão documental antes de qualquer construção — produto intacto, aguardando o Product Owner.

---

## Final result (exact)

```text
STATUS
IMPLEMENTABLE
NÃO
```

### Blockers (if NÃO)

| ID | Severidade | One-line |
|----|------------|----------|
| CDR-H-001 | High | A2 INVALID abort absolute vs soft-analyze must-stay (021) |
| CDR-H-002 | High | Orchestration soft-analyze + post-integrity + CM commit eligibility missing from §4.6 |

### Improvements only (non-blockers)

CDR-M-001 … CDR-M-007; CDR-L-001 … CDR-L-004 (see Findings catalog).

---

## Handoff

| Item | Status |
|------|--------|
| CDR-001 | Delivered |
| Dual Reporting | This file |
| Product code | Unchanged |
| Spec | Unchanged |
| AAR | **NOT STARTED** — await PO |
| Next | PO decision → Spec revision (recommended) |

---

*End of EXECUTION_MANAGER_CDR_024.md*
