# RESOLUTION MATRIX — CDR 005 → Spec 004 Governance Gate

**Mission:** ARCHITECTURE_GOVERNANCE / DESIGN_REVIEW_RESOLUTION (006)  
**Role:** Chief Software Architect + Architecture Review Board + Technical Governance Lead  
**Date:** 2026-08-06  
**Primary defendant:** `observations/aurora_context_manager_spec_004/SPEC.md` (read-only; **not modified**)  
**Findings source:** `observations/aurora_context_manager_cdr_005/CDR.md` (27 findings)  
**Cross-exhibits:** Audit 001, research_003 (as needed)

**Binding path for ACCEPT:** Finding → ACCEPT → **Spec 004 v1.1** (future revision) → new CDR → new AAR → only then Implementation Plan.  
**No code. No Spec 004 edit in this mission. No migration.**

---

## Summary Counts

| Decision | Count |
|----------|------:|
| **ACCEPT** | **24** |
| **REJECT** | **1** |
| **DEFER** | **2** |
| **Total** | **27** |

| Severity bucket (CDR composite) | ACCEPT | REJECT | DEFER |
|---------------------------------|-------:|-------:|------:|
| 🔴 BLOCKER (10) | 10 | 0 | 0 |
| 🟠 ALTO (13) | 12 | 1 | 0 |
| 🟡 MÉDIO (4) | 2 | 0 | 2 |

---

## FINDING-001

### ID
FINDING-001

### Descrição
P3 exige sole-writer via `STS.commit` com `ENABLE_LANGGRAPH_STATE` OFF, enquanto C7 / §5.1 exigem sole `_commit` apenas no caminho graph — Spec não define host de commit de produção não-graph para P3.

### Severidade
🔴 BLOCKER (Crítico × Alta)

### Evidências
SPEC §17 P3; §7 C7; §5.1; research_003 §8 P3 vs §7.1; CDR X1.

### Decisão: ACCEPT

### Justificativa Técnica
Contradição normativa load-bearing: a fase que deveria provar sole-writer não possui host legal. Implementadores seriam forçados a inventar segundo orquestrador → dual orchestration permanente. Não é nit; bloqueia P3→P4 coerente.

### Impacto
- **Arquitetural:** Dois hosts de commit (funnel vs graph) sem contrato único.
- **Governança:** Gate P3 não é falsificável.
- **Operacional:** Migração inventa path sob pressão.
- **Escalabilidade:** Dual host multiplica race surfaces.

### Ação Recomendada (Spec 004 v1.1)
Normativamente escolher **uma** arquitetura P3: (A) orquestrador mínimo não-LangGraph com **mesma** semântica de edges/commit/projeções que o host P4; ou (B) exigir host LangGraph (shadow/order) antes do funnel write, reescrevendo P3 gate. Proibir segundo commit path ad hoc. Atualizar C7 / §5.1 / §17 para um único “commit host” por fase.

### Spec v1.1 Work Item ID
SPEC-v1.1-001

---

## FINDING-002

### ID
FINDING-002

### Descrição
Canal proven de sticky-bleed — rewrite de `message` / intent sobre times CSL sticky **antes** do boundary — permanece fora do contrato do Context Manager.

### Severidade
🔴 BLOCKER (Crítico × Alta)

### Evidências
sticky_bleed_001 Verdict + call chain; TB-002 root cause #1; SPEC §5.5 / §9.1 / §9.3 (golden sem regra de message-authority); CDR X6.

### Decisão: ACCEPT

### Justificativa Técnica
STS correto + message reescrito sobre subject OLD ainda produz “Mantendo foco” / analyze no fixture errado. Sole-writer de keys não fecha a classe de falha de percepção. Spec afirma golden scenario sem autoridade de message.

### Impacto
- **Arquitetural:** Subject SoT incompleto se message é canal equivalente.
- **Operacional / Percepção:** Bleed user-visible com testes de keys verdes.
- **Governança:** T4/V6 podem passar falso-positivos.

### Ação Recomendada (Spec 004 v1.1)
Regra normativa: após cutover, intent/compare rewrite consome **snapshot STS** (ou teams message-side pós-SLL), nunca CSL sticky pré-STS. Adicionar critério T* de divergência `message-derived teams ≠ STS.teams` → fail. Estender §5.5 / §9.3 / §10.

### Spec v1.1 Work Item ID
SPEC-v1.1-002

---

## FINDING-003

### ID
FINDING-003

### Descrição
Checkpoint após `_commit` e projection refresh depois cria janela crash/restart com STS NEW + projeções OLD (dual-SoT de leitura).

### Severidade
🔴 BLOCKER (Crítico × Alta)

### Evidências
SPEC §9.1 steps 5.4–6, §13.2, §14, §15.1 projection-failure; centralization_001 §2.2 readers; CDR X3.

### Decisão: ACCEPT

### Justificativa Técnica
Postcondition §10.1 (“subject fields consistent across STS + projections”) é falsa em qualquer crash entre checkpoint e projection. Deep call graph ainda lê projeções — recreia sticky triad exatamente quando durability “funciona”.

### Impacto
- **Arquitetural / Persistência:** Dual-SoT de leitura pós-crash.
- **Operacional:** Soft FU / Autoscale peer em envelope stale.
- **Escalabilidade:** Pior sob multi-node sem shared envelope.

### Ação Recomendada (Spec 004 v1.1)
Definir **uma** durability boundary: checkpoint inclui projection plan + `subject_generation`/epoch **e** consumidores recusam generation mismatch; **ou** projection refresh está na mesma unidade de commit que o checkpoint (falha = fail-closed). Remover postcondition absoluta sem janela definida.

### Spec v1.1 Work Item ID
SPEC-v1.1-003

---

## FINDING-004

### ID
FINDING-004

### Descrição
“Atomicidade” de commit / projection atravessa quatro stores sem protocolo transacional (checkpointer, conversation_manager, OS lock, SCG).

### Severidade
🔴 BLOCKER (Crítico × Alta)

### Evidências
SPEC §5.5, §7 C7, §12, §15.1 OS/SCG best-effort; Audit 001 Memory Autoscale; CDR §1 FINDING-004.

### Decisão: ACCEPT

### Justificativa Técnica
Linguagem “atomic” sem unidade de trabalho real autoriza corrupção estrutural papelada com AUDIT. Não é pedantismo: sem stages + winner-on-divergence, recovery é indefinida.

### Impacto
- **Arquitetural:** Claims de consistência não implementáveis.
- **Persistência / Operacional:** Divergence permitida por design.
- **Governança:** Testes “atomic” não falsificáveis.

### Ação Recomendada (Spec 004 v1.1)
Substituir “atomic” por **commit stages** numerados, crash semantics por stage, e regra de qual store vence em divergence. Proibir palavra “atomic” salvo UoW definida (incl. fsync/order expectations). Alinhar §7 C7, §10.3, §15.1.

### Spec v1.1 Work Item ID
SPEC-v1.1-004

---

## FINDING-005

### ID
FINDING-005

### Descrição
P4 exige “rollback proven” sem definir unidade de rollback, safety in-flight, nem repair pós dual-SoT.

### Severidade
🔴 BLOCKER (Crítico × Alta)

### Evidências
SPEC §17 P4; research_003 §8 P4; centralization_001 §8 Rollback column; TB-002 `ENABLE_TOPIC_BOUNDARY_V2=0` precedent.

### Decisão: ACCEPT

### Justificativa Técnica
Gate operacional sem procedimento = enable P4 sem reverse seguro. centralization_001 tinha rollback por fase; Spec dropou. “Proven” não é critério testável.

### Impacto
- **Operacional:** Ops inventa rollback sob incidente.
- **Governança:** Exit gate P4 slogan.
- **Arquitetural:** Partial writer re-enable recreia dual-SoT.

### Ação Recomendada (Spec 004 v1.1)
Matriz normativa de rollback por fase (P1–P5): trigger, steps, accepted data loss, verification, in-flight turn policy. Tornar “rollback proven” = drill + checklist observável antes de P4 exit.

### Spec v1.1 Work Item ID
SPEC-v1.1-005

---

## FINDING-006

### ID
FINDING-006

### Descrição
Documento Mestre Etapa 1 = INSUFFICIENT EVIDENCE; Spec faz P0 exit = “Missão 005 accepts SPEC” — auto-ratificação circular da Substitution sem autoridade master.

### Severidade
🔴 BLOCKER (Crítico × Alta) — **governance / P0**

### Evidências
SPEC §16.4, §17 P0, Validation Contract Q4; Audit 001 §9 NO + items 1/5 + Appendix B; research_003 R2.

### Decisão: ACCEPT

### Justificativa Técnica
Audit 001 verdict explícito: **NOT ready for Substitution Phase** sem Documento Mestre. Usar CDR técnico como proxy de autorização de Substitution é gap de governança, não nit de processo. Spec v1.1 deve separar (a) aceite técnico do contrato vs (b) autorização de Substitution.

### Impacto
- **Governança:** Kill político — “approved Spec” sem autoridade Substitution.
- **Arquitetural:** Implementação pode avançar sem master compliance / waiver.

### Ação Recomendada (Spec 004 v1.1)
Reescrever P0 exit: aceite técnico CDR/AAR **≠** Substitution authorization. Exigir Documento Mestre in-repo **ou** waiver humano escrito (owner, scope, expiry, time-box) como precondition de qualquer missão de implementação. Manter label INSUFFICIENT EVIDENCE até master/waiver.

### Spec v1.1 Work Item ID
SPEC-v1.1-006

---

## FINDING-007

### ID
FINDING-007

### Descrição
Turns concorrentes same-`session_id` indefinidos (last-writer-wins); sem mutex/lease/serial queue.

### Severidade
🔴 BLOCKER (Crítico × Média)

### Evidências
SPEC §8.1, §11–§14 silêncio; §12 Autoscale sem serialização; Audit R6; CDR Race matrix.

### Decisão: ACCEPT

### Justificativa Técnica
Produção com retry/double-submit é cenário real. Interleave init_load→commit→checkpoint→projection corrompe prior de soft FU. Spec single-threaded fantasy não é implementável com credibilidade.

### Impacto
- **Arquitetural / Escalabilidade:** Race first-class.
- **Operacional:** Duplicate client → double boundary / wrong prior.
- **Performance:** Contenção precisa de política (queue vs 429).

### Ação Recomendada (Spec 004 v1.1)
Mandatar execução serial por `thread_id` (lock/lease) antes de production write ON; definir conflito (429 / queue / refuse merge). Incluir na Race matrix normativa e em T* concurrency.

### Spec v1.1 Work Item ID
SPEC-v1.1-007

---

## FINDING-008

### ID
FINDING-008

### Descrição
Autoscale split-brain: checkpointer compartilhado + session envelope/projeções locais (Memory miss conhecido).

### Severidade
🟠 ALTO (Alto × Alta)

### Evidências
SPEC §12; Audit 001 Memory + R6; CONTAMINATION_NOTES `before_langgraph`.

### Decisão: ACCEPT

### Justificativa Técnica
Spec admite Postgres checkpointer mas deixa envelope local — Node B serve projeções stale/empty após commit em A. Sticky sessions sozinhas não fecham autoridade de projeção. Gap de escala = gap de subject credibility.

### Impacto
- **Escalabilidade:** Horizontal scale reintroduz bleed.
- **Arquitetural:** STS checkpoint ≠ projection authority cross-node.
- **Operacional:** Contaminação tipo legacy lag em multi-instance.

### Ação Recomendada (Spec 004 v1.1)
Norma multi-node: shared session envelope SoT **ou** todos consumidores de subject leem apenas checkpoint/STS (projeção local sem autoridade). Sticky sessions, se usadas, são complemento — não substituto. Gate P4 multi-instance explicit.

### Spec v1.1 Work Item ID
SPEC-v1.1-008

---

## FINDING-009

### ID
FINDING-009

### Descrição
Matriz de flags independentes pode habilitar dual-SoT por construção; precedência §8.8 é prosa, não enforceável.

### Severidade
🔴 BLOCKER (Crítico × Alta)

### Evidências
SPEC §8.8, §17; Audit 001 R8; topic_transition_arch_001 dual detectors; centralization_001 residual materializers.

### Decisão: ACCEPT

### Justificativa Técnica
Proibição dual-SoT sem illegal combinations machine-checkable falha no boot. Flag spaghetti já auditado (R8). Interface incompleta = dual-SoT “legal” por config.

### Impacto
- **Interface / Governança:** Policy text ≠ enforceable contract.
- **Arquitetural:** Combinações ilegais = dual materializers.
- **Operacional:** Config drift produção.

### Ação Recomendada (Spec 004 v1.1)
Publicar **illegal flag matrix** + fail-closed boot/assert; preferir enum único de migration stage consolidando LangGraph/STS/V2 gates. Atualizar C12 e T9.

### Spec v1.1 Work Item ID
SPEC-v1.1-009

---

## FINDING-010

### ID
FINDING-010

### Descrição
Fail-closed classify bifurcado: “safe boundary **or** no subject invent” — políticas incompatíveis; control-flow não decidível.

### Severidade
🟠 ALTO (Alto × Alta)

### Evidências
SPEC §15.1; Validation Contract ambiguity #3; CDR X4.

### Decisão: ACCEPT

### Justificativa Técnica
Não é ambiguidade de copy i18n: são duas máquinas de estado. Produção não pode ser implementada sem coin-flip arquitetural. Spec deve escolher **uma**.

### Impacto
- **Arquitetural / Estado:** Branch de degrade indefinido.
- **Operacional:** Drop context vs keep sticky contested.
- **Governança:** Ambiguity #3 mal classificada como “UX copy”.

### Ação Recomendada (Spec 004 v1.1)
Uma degrade state machine normativa (inputs → mutação STS exata + response class). Copy i18n separada. Fechar ambiguity #3 como control-flow, não copy.

### Spec v1.1 Work Item ID
SPEC-v1.1-010

---

## FINDING-011

### ID
FINDING-011

### Descrição
STS como god-component (schema + apply + commit + projections + OS/SCG orchestration).

### Severidade
🟠 ALTO (Alto × Média)

### Evidências
SPEC §7 C2/C6/C7/C13/C14; §10.3; Validation Contract Q2.

### Decisão: REJECT

### Justificativa Técnica
Falso positivo relativo ao contrato Spec **como escrito**. §6–§7 já separa C2 (schema/events), C7 (Commit Gate), C8 (Projection Layer), C13/C14 (OS/SCG adapters). “Trigger projection / side-effect via adapters” ≠ ownership monolítica dos módulos KEEP. O risco de blob é de implementação futura, não ausência de split normativo. Elegância de Commit Gate vs Projection Coordinator pode ser refinement pós-contratos de durability/sole-writer — não defeito que impede decidibilidade do Spec atual além dos findings ACEITOS (003/004/016). Validation Contract Q2 permanece errado por **outros** gaps (001/002/005/…) — tratados em FINDING-027.

### Impacto
- **Arquitetural:** Overstated; componentes já particionados no Spec.
- **Governança:** Aceitar forçaria refactor cosmético antes de fechar blockers reais.

### Ação Recomendada (if ACCEPT)
N/A — REJECT.

### Spec v1.1 Work Item ID
N/A

---

## FINDING-012

### ID
FINDING-012

### Descrição
`EpisodeTransitionDecision.current_entities` / `prior_subject` especificados como `...` — sem schema/equality/canonicalization.

### Severidade
🟠 ALTO (Alto × Alta)

### Evidências
SPEC §8.4; topic_transition_arch_001 §1.2 prior collection.

### Decisão: ACCEPT

### Justificativa Técnica
Sem DTO tipado, P1 “centralize decide” forka silenciosamente; golden vs TB-V2 impossível. Ellipsis não é placeholder aceitável em interface normativa.

### Impacto
- **Interface / Arquitetural:** Single decision não golden-testável.
- **Governança:** P1 exit gate vazio.

### Ação Recomendada (Spec 004 v1.1)
DTO normativo alinhado a inputs/outputs TB-V2 detect (prior source rules, entity equality, fixture-label canonicalization) **antes** de P1 exit. Substituir `...` em §8.4.

### Spec v1.1 Work Item ID
SPEC-v1.1-012

---

## FINDING-013

### ID
FINDING-013

### Descrição
Enum KEEP_EPISODE | NEW_FIXTURE | NEW_EPISODE não mapeia bijectivamente aos três apply nodes (soft FU → keep_followup vs seed → apply_subject).

### Severidade
🟠 ALTO (Alto × Média)

### Evidências
SPEC §8.4, §9.1 route, §7 C6; POC ARCHITECTURE route table.

### Decisão: ACCEPT

### Justificativa Técnica
Ambiguidade de keep pode pular followup window ou rotacionar episódio via nó errado. Função pura decision→node é requisito de fluxo, não nit.

### Impacto
- **Arquitetural / Fluxo:** Soft-FU stamp incorreto / false rotate.
- **Operacional:** Percepção regressível.

### Ação Recomendada (Spec 004 v1.1)
Appendix normativo: tabela pura `(outcome × reason) → apply node` com cobertura de seed/same-fixture/soft_FU/new_*.

### Spec v1.1 Work Item ID
SPEC-v1.1-013

---

## FINDING-014

### ID
FINDING-014

### Descrição
Shadow path §9.2 preserva lag pré-LangGraph por design; P2 pode green-wash locus-1.

### Severidade
🟠 ALTO (Alto × Alta)

### Evidências
SPEC §9.2, §17 P2; CONTAMINATION_NOTES; langgraph_state_poc_001 ARCHITECTURE Phase 2; CDR X8.

### Decisão: ACCEPT

### Justificativa Técnica
Medir compare pós-intent/CSL valida o path errado para readiness de cutover. “Locus 1 understood as legacy lag” como exit permanente é falsa confiança → P4 com ingress contamination intacta. Liga FINDING-002.

### Impacto
- **Arquitetural / Fluxo:** Gate P2 não prova ordem de ingress.
- **Governança:** Métricas verdes enganosas.
- **Operacional:** Bleed permanece até produção.

### Ação Recomendada (Spec 004 v1.1)
P2 deve incluir experimento de ingress-order (shadow compare post-SLL pre-CSL) com critérios de sucesso **separados**. Não tratar locus-1 dominance como aceitável forever. Atualizar §9.2 / §17 P2 / V4.

### Spec v1.1 Work Item ID
SPEC-v1.1-014

---

## FINDING-015

### ID
FINDING-015

### Descrição
Enforcement de illegal-write é test-time theater; P4 habilita write antes de runtime sole-writer guard (P5).

### Severidade
🔴 BLOCKER (Crítico × Alta)

### Evidências
SPEC §10.6, §17 P4 vs P5; centralization_001 residual cascade; Audit R3; CDR X2.

### Decisão: ACCEPT

### Justificativa Técnica
Viola a própria proibição dual-SoT do Spec. 14 writers vivos + production write = Audit R3 no dia 1. Guard runtime é precondition de P4, não nicety de P5.

### Impacto
- **Arquitetural:** Dual-SoT por schedule.
- **Governança / Acoplamento:** T1/T11 sem dentes em prod.
- **Operacional:** Bleed com “new architecture” badge.

### Ação Recomendada (Spec 004 v1.1)
Runtime sole-writer guard = **hard P4 precondition**. P5 apenas aposenta código morto após guard provar zero hits. Reordenar §17 e fortalecer §10.6 com mecanismo normativo (fail-closed production).

### Spec v1.1 Work Item ID
SPEC-v1.1-015

---

## FINDING-016

### ID
FINDING-016

### Descrição
OS/SCG side-effects após checkpoint; restart pode deixar locks/anchors OLD com STS NEW.

### Severidade
🟠 ALTO (Alto × Média)

### Evidências
SPEC §9.1 steps 5–7, §10.3, §15.1 best-effort; sticky_bleed_001 Owner TTL.

### Decisão: ACCEPT

### Justificativa Técnica
Postcondition de boundary exige OS release + SCG expire, mas ordering + best-effort torna KEEP modules amplificadores de contaminação pós-commit “sucesso”. Parte da durability unit (liga 003/004).

### Impacto
- **Arquitetural / Fluxo:** Side-effects fora da UoW.
- **Operacional:** Soft FU / RS hold OLD fixture.
- **Persistência:** Checkpoint mente sobre completeness.

### Ação Recomendada (Spec 004 v1.1)
Incluir OS/SCG required side-effects no boundary commit stage com compensation explícita; **ou** incomplete side-effects = fail-closed para production write. Remover “best-effort” sem estado de incomplete visível aos consumidores.

### Spec v1.1 Work Item ID
SPEC-v1.1-016

---

## FINDING-017

### ID
FINDING-017

### Descrição
Ordem de aquisição de locks entre session envelope e checkpointer não especificada — risco de deadlock.

### Severidade
🟡 MÉDIO (Alto × Baixa)

### Evidências
SPEC §12–§15 silêncio; C10/C11/C15 interaction; CDR Race matrix.

### Decisão: DEFER

### Justificativa Técnica
Risco real sob retry/load, mas probabilidade Baixa e não bloqueia decidibilidade dos contratos de subject/sole-writer/durability unit. Adequado a política operacional / Spec revision posterior (v1.2+) **após** fechar UoW (003/004) e serial lease (007), que reduzem a superfície. Não é false positive — adiado conscientemente.

### Impacto
- **Operacional / Performance:** Stuck sessions sob load (latente).
- **Arquitetural:** Lock hierarchy TBD.

### Ação Recomendada (if ACCEPT)
N/A — DEFER. Tracking: documentar lock hierarchy + timeouts + projection retry budget em revisão futura ou runbook ops pós-v1.1 dos blockers.

### Spec v1.1 Work Item ID
N/A (tracked as DEFER-017 for later revision)

---

## FINDING-018

### ID
FINDING-018

### Descrição
Projection write-through fanout ilimitado sem latency budget / dirty-set.

### Severidade
🟡 MÉDIO (Médio × Média)

### Evidências
SPEC §8.5, §9.1 step 6, §21 R6; centralization_001 triad map; research_003 R6 (checkpoint bloat mitigated; projection amp ignored).

### Decisão: DEFER

### Justificativa Técnica
Preocupação legítima de p99/write amplification, mas não é defeito de contrato que impede sole-writer correctness ou fecha dual-SoT. Pode esperar após epoch/consistency model (021) e UoW (003/004). Não bloquear Spec v1.1 dos blockers de credibilidade.

### Impacto
- **Performance:** p99 / DB amplification.
- **Escalabilidade:** Hot path cost.

### Ação Recomendada (if ACCEPT)
N/A — DEFER. Futuro: budget N key updates / dirty-set; async só se consistency model permitir (geralmente não para betting subject).

### Spec v1.1 Work Item ID
N/A (tracked as DEFER-018 for later revision)

---

## FINDING-019

### ID
FINDING-019

### Descrição
T10 subestima regressão comportamental de Frozen (OS/SCG/RS) via ordem/argumentos de call-site.

### Severidade
🟠 ALTO (Alto × Média)

### Evidências
SPEC §18 T10, §20 F2; sticky_bleed_001; TB-002 order change; Audit R4.

### Decisão: ACCEPT

### Justificativa Técnica
Percepção muda com ordering/identity de argumentos mesmo sem editar internals Frozen. “Untouched internals” ≠ “no behavioral contract change”. Gate P4 sem golden OS/SCG/RS é falsa confiança Frozen.

### Impacto
- **Governança / Regressão:** Frozen policy hollow.
- **Arquitetural:** Call-site é parte do contrato de colaboração.

### Ação Recomendada (Spec 004 v1.1)
Substituir/expandir T10: golden perception suites binding OS/SCG/RS observáveis sob boundary/soft-FU/analyze como gates P4. Esclarecer F2: call-site ordering é behavioral surface.

### Spec v1.1 Work Item ID
SPEC-v1.1-019

---

## FINDING-020

### ID
FINDING-020

### Descrição
ADR-001 overclaims POC shadow como prova de produção (sole-writer, multi-node, projection atomicity, message-path).

### Severidade
🟠 ALTO (Alto × Alta)

### Evidências
ADR-001; CONTAMINATION_NOTES (shadow never writes); research_003 shortlist #2.

### Decisão: ACCEPT

### Justificativa Técnica
Shadow NEW_STATE sob lag prova classify-under-isolation, não cutover. Contingency (STS sem LangGraph) é mais forte para P3 mas demotada sem kill criteria. ADR fraco trava tax de dependência em evidência incompleta.

### Impacto
- **Governança / ADR:** Dependency lock injustificado.
- **Arquitetural:** Host choice provisional sem flip triggers.

### Ação Recomendada (Spec 004 v1.1)
Relabel ADR-001 como **provisional** pending P2/P3 kill criteria; definir triggers explícitos para flip à contingency (custom STS sem LangGraph). Cruzar com SPEC-v1.1-001 (P3 host).

### Spec v1.1 Work Item ID
SPEC-v1.1-020

---

## FINDING-021

### ID
FINDING-021

### Descrição
ADR-007 ban dual-SoT vs write-through multi-key sem generation/epoch — sleight of hand logical vs physical.

### Severidade
🟠 ALTO (Alto × Alta)

### Evidências
ADR-007, ADR-010; SPEC §5.4, §8.5; centralization_001 §4.

### Decisão: ACCEPT

### Justificativa Técnica
Sole writer lógico ≠ single physical store. Sem `subject_generation`/epoch, readers preferem cópia stale e bleed retorna. ADR-010 (projections) exige mecanismo de freshness.

### Impacto
- **Arquitetural:** Projeções re-bleed via reader preference.
- **Persistência:** Multi-key sem authority bits.
- **Governança:** “Sole-SoT” claim falso.

### Ação Recomendada (Spec 004 v1.1)
Mandatar `subject_generation` (epoch) em STS e todas projeções; readers descartam mismatch. Atualizar ADR-007/010 e §8.5 / read consumer contract. Alinhar SPEC-v1.1-003.

### Spec v1.1 Work Item ID
SPEC-v1.1-021

---

## FINDING-022

### ID
FINDING-022

### Descrição
ADR-011 `thread_id` = “deterministic function of session_id” sem algoritmo, namespace, collision domain, empty/anon handling.

### Severidade
🟡 MÉDIO (Médio × Média)

### Evidências
ADR-011; SPEC §8.1, §13.1, §10.1.

### Decisão: ACCEPT

### Justificativa Técnica
Claims de isolation/restart são unfalsifiable sem mapping. Médio, mas contrato de identidade é precondition de checkpoint/recovery — não deferível se Spec afirma isolation.

### Impacto
- **Arquitetural:** Cross-talk / recovery miss risk.
- **Governança:** Testes negativos impossíveis.

### Ação Recomendada (Spec 004 v1.1)
Especificar algoritmo, length, namespace, negative tests (collision/isolation), handling de IDs vazios/anônimos além de precondition non-empty.

### Spec v1.1 Work Item ID
SPEC-v1.1-022

---

## FINDING-023

### ID
FINDING-023

### Descrição
Corrupt checkpoint: “open new episode **or** refuse” sem detector nem branch normativa única.

### Severidade
🟡 MÉDIO (Alto × Baixa) — CDR composite MÉDIO; impacto de credibilidade Alto se ocorrer

### Evidências
SPEC §14; Validation Contract omite este fork.

### Decisão: ACCEPT

### Justificativa Técnica
Duas políticas sem procedure = não implementável (CDR X7). Mesmo raro, betting-credibility landmine. Spec deve uma branch + checksum/schema version.

### Impacto
- **Persistência / Estado:** Silent reset vs stuck refuse.
- **Governança:** Ambiguity under-listed.

### Ação Recomendada (Spec 004 v1.1)
Uma recovery branch normativa + AUDIT + UX clarify; checksum/schema version no checkpoint; detector corruption vs unexpected shape.

### Spec v1.1 Work Item ID
SPEC-v1.1-023

---

## FINDING-024

### ID
FINDING-024

### Descrição
Mirror `aurora/` vs `artifacts/aurora/` drift — kill criteria soft; timeline aberto.

### Severidade
🟠 ALTO (Alto × Média)

### Evidências
SPEC §16.1; Validation ambiguity #5; Audit 001 R5.

### Decisão: ACCEPT

### Justificativa Técnica
Deploy no tree errado = flags ON + modules missing → dual-tree outage / silent legacy. Requirement “resolve before P4” sem hard release assert é soft kill.

### Impacto
- **Operacional / Regressão:** Production write no tree errado.
- **Governança:** Ambiguity #5 timeline aberto.

### Ação Recomendada (Spec 004 v1.1)
Hard release gate: deploy path assertion fail-closed se módulos LangGraph/STS ausentes. Mirror drift open = P4 NO-GO explícito (não só timeline process).

### Spec v1.1 Work Item ID
SPEC-v1.1-024

---

## FINDING-025

### ID
FINDING-025

### Descrição
Missing `langgraph` package: fail-closed incompleto (HTTP/UX/session mutate / legacy writers ainda vivos).

### Severidade
🟠 ALTO (Alto × Média)

### Evidências
SPEC §14, §15.1, §18 T12; C1 sequential fallback shadow-only; CDR X5.

### Decisão: ACCEPT

### Justificativa Técnica
Fail-closed subject + legacy writers vivos = dual-SoT no failure mode que Spec alega prevenir. Outcome de turn não definido.

### Impacto
- **Estado / Operacional:** Dependency incident → credibility incident.
- **Arquitetural:** Degrade process-global incompleto.

### Ação Recomendada (Spec 004 v1.1)
Process-global degrade: se write flag ON e host unavailable → recusar mutação subject **e** bloquear legacy subject writers no processo; definir HTTP/status/session mutate/UX class. Expandir T12.

### Spec v1.1 Work Item ID
SPEC-v1.1-025

---

## FINDING-026

### ID
FINDING-026

### Descrição
note_* cascade residual permanece kill vector até P5 enquanto P4 já habilita production write.

### Severidade
🔴 BLOCKER (Crítico × Alta)

### Evidências
centralization_001 §6; SPEC §9.1 step 12, §17 P4/P5; sticky_bleed note_csl point F; CDR X2.

### Decisão: ACCEPT

### Justificativa Técnica
Vetor residual **conhecido** sobrevive ao schedule de production write. Funnel+guard de note_* subject fields é precondition de P4 (com 015), não cleanup P5.

### Impacto
- **Arquitetural / Concorrência:** Re-materialize divergent subject pós-boundary.
- **Governança:** Schedule viola dual-SoT ban.

### Ação Recomendada (Spec 004 v1.1)
Funnel+runtime guard de todos note_* subject fields **antes** de P4 exit. P5 só deleta dead code. Alinhar §17 com SPEC-v1.1-015.

### Spec v1.1 Work Item ID
SPEC-v1.1-026

---

## FINDING-027

### ID
FINDING-027

### Descrição
Validation Contract Q2 afirma “No undefined responsibilities” enquanto CDR prova gaps (message rewrite, P3 host, rollback, lock order, corrupt branch, Autoscale envelope).

### Severidade
🟠 ALTO (Alto × Alta)

### Evidências
SPEC Validation Contract Q1–Q2 vs FINDING-001/002/005/007/008/010/023.

### Decisão: ACCEPT

### Justificativa Técnica
Self-grade do Spec é unreliable e hazard de processo: humanos podem confiar no Q2. Contrato de validação deve ser retractado/corrigido até findings ACEITOS fechados; checklist externo (CDR/AAR) é autoridade.

### Impacto
- **Governança:** Process hazard.
- **Arquitetural:** False closure de responsibilities.

### Ação Recomendada (Spec 004 v1.1)
Marcar Validation Contract como non-authoritative até closure dos ACEITOS; corrigir Q2 → YES com lista explícita; exigir checklist externo CDR-derived. Não usar self-grade como gate de implementação.

### Spec v1.1 Work Item ID
SPEC-v1.1-027

---

## Work Item Index (ACCEPT → Spec 004 v1.1)

| Work Item | Finding | Theme |
|-----------|---------|-------|
| SPEC-v1.1-001 | 001 | P3 commit host vs graph-only |
| SPEC-v1.1-002 | 002 | Message rewrite authority |
| SPEC-v1.1-003 | 003 | Checkpoint↔projection durability boundary |
| SPEC-v1.1-004 | 004 | Commit stages / ban fake atomicity |
| SPEC-v1.1-005 | 005 | Rollback matrix per phase |
| SPEC-v1.1-006 | 006 | P0: Mestre/waiver ≠ CDR self-ratify |
| SPEC-v1.1-007 | 007 | Per-thread_id serial lease |
| SPEC-v1.1-008 | 008 | Shared envelope or STS-only readers |
| SPEC-v1.1-009 | 009 | Illegal flag matrix / stage enum |
| SPEC-v1.1-010 | 010 | Single fail-closed classify branch |
| SPEC-v1.1-012 | 012 | Typed EpisodeTransitionDecision DTO |
| SPEC-v1.1-013 | 013 | decision×reason → node table |
| SPEC-v1.1-014 | 014 | P2 ingress-order experiment |
| SPEC-v1.1-015 | 015 | Runtime sole-writer guard before P4 |
| SPEC-v1.1-016 | 016 | OS/SCG in commit stage / fail-closed |
| SPEC-v1.1-019 | 019 | Frozen call-site golden gates |
| SPEC-v1.1-020 | 020 | ADR-001 provisional + flip triggers |
| SPEC-v1.1-021 | 021 | subject_generation epoch |
| SPEC-v1.1-022 | 022 | thread_id mapping algorithm |
| SPEC-v1.1-023 | 023 | Single corrupt-checkpoint branch |
| SPEC-v1.1-024 | 024 | Deploy SoT hard assert |
| SPEC-v1.1-025 | 025 | Missing-langgraph process degrade |
| SPEC-v1.1-026 | 026 | note_* funnel+guard before P4 |
| SPEC-v1.1-027 | 027 | Validation Contract retract/correct |

**Deferred track (not Spec v1.1 blockers):** DEFER-017 (lock hierarchy), DEFER-018 (projection fanout budget).

---

## Explicit Non-Actions (this mission)

- Spec 004 (`observations/aurora_context_manager_spec_004/SPEC.md`) **not modified**.
- No product / Aurora code modified.
- No migration executed.
- No git commit created.

```
FACT:
RESOLUTION_MATRIX for CDR 005 complete. ACCEPT 24 / REJECT 1 / DEFER 2.
All 10 BLOCKER findings ACCEPTED → Spec 004 v1.1 work items required.
Implementation remains blocked pending Spec revision + new CDR + new AAR.
```
