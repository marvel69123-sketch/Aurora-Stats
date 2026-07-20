# Premium Readiness Report (post-P2b)

**Date:** 2026-07-20  
**Question:** Can Aurora enter Premium UX (P3) with sufficient ROI?  
**Verdict:** **CONDITIONAL GO — thin surface now; full Premium HOLD pending live SLOs**

---

## Scorecard

| Dimension | Ready? | Evidence |
|-----------|--------|----------|
| Conversational stability | ✅ | Discovery Real 97.7%, GA_LOOP 1, P0 smokes |
| Binding / honesty / explain | ✅ | P2.5 frozen & live |
| Data plane architecture | ✅ | P2b W1–W3 closed |
| Offline T3/T4 density | ✅ partial | Wave 3 corpus **62.5%** T3/T4; premium_analysis_rate **62.5%** |
| Live `% DRS≥60` | ❌ unknown | Not yet production-instrumented |
| Resolve rate (covered leagues) | ⚠️ unverified post-W3 | Charter target ≥85% |
| Odds / XI / injuries in real API | ⚠️ uneven | Offline means: odds 0.31, lineup 0.48, injury 0.13 |
| Premium UI chrome | ❌ | Out of P2b scope |
| Engine SoT integrity | ✅ | No formula edits |

---

## Answers (product)

### P3 UX já possui ROI suficiente?

| Escopo P3 | ROI? | Decisão |
|-----------|------|---------|
| **Thin Premium** (DRS tier, signals, narrative, odds/calendar cards) | **Sim** | **GO now** — low cost, uses existing `_data_plane` / NMB |
| **Full Premium UX program** (redesign, motion system, multi-surface) | **Ainda não** | **HOLD** until live density gates |

Thin UX amplifies the 62.5% offline premium rate into user perception.  
Full Premium UX amplifies empty shells if live density is still weak — negative ROI.

### A Aurora já parece um produto premium?

**Não de ponta a ponta. Sim em fatias T3/T4.**

| Momento | Sensação |
|---------|----------|
| Short FU / clarify / identity | Produto conversacional maduro (não “premium analyst”) |
| Análise com bundle rico | Pode parecer analista premium (xG, events, odds, XI, narrative) |
| Soft-miss / no fixture | Honestamente parcial — correto, mas não premium |
| UI atual | Funcional; sem hierarquia visual premium |

**Barra “parece premium”:** usuário recebe, na maioria dos confrontos cobertos, análise T3+ com sinais nomeados e odds/XI quando existirem — sem inventar. Hoje isso é **capaz**, não **consistente**.

---

## GO / NO-GO matrix

### GO (thin) — start immediately

- Surface `entities.data_richness.tier`  
- Honesty have/lack already present — tighten layout only  
- Narrative bullets when `signals.narrative` confirmed  
- Show 1X2 only if odds quality confirmed  
- Never decorate missing as present  

### HOLD (full P3) — until

1. Live `% DRS≥60` ≥ 50% on sport analyze turns (healthy API window)  
2. Resolve ≥ 85% on covered-league named pairs  
3. Real-user Discovery remains ≥ 97%  
4. ≥10 curated T3/T4 showcases with odds or XI  

### NO-GO triggers

- Invention uptick  
- DRS vanity inflate without confirmed signals  
- Unfreezing engines to “look richer”  

---

## Risk if we force full Premium now

```text
Beautiful shell × frequent DATA_PARTIAL  →  trust erosion
```

P2.5 honesty protects truth; Premium chrome without density sells a promise the feed cannot keep.

---

## Recommendation (one paragraph)

Ship **thin Premium surface** against the closed P2b plane (DRS, narrative, calendar, odds, lineups) while instrumenting **live density SLOs**. Treat full P3 as a gated program: ROI becomes high only after production proves that T3/T4 is the common case on covered fixtures, not the offline corpus exception.

---

## Linkage

- Closure: `p2b_closure_report.md`  
- Bottleneck: `post_p2b_bottleneck.md`  
- Sequence: `recommended_roadmap_v4.md`  
- Wave evidence: `p2b_wave1_report.md` · `p2b_wave2_report.md` · `p2b_wave3_report.md`
