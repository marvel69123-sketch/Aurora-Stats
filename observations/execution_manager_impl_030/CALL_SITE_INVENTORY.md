# Mission 030 — Call-site inventory (Phase 1 Prep)

**SoT:** `artifacts/aurora/`  
**Source map:** `observations/execution_surface_021/EXECUTION_SURFACE_MAP.md`  
**Captured:** 2026-08-07  
**Class:** inventory only — no extraction

---

## 1. Unified mega-router `_run_*` (EM extraction candidates)

| Function | Approx lines | Destino Futuro | Primary callee |
|----------|--------------|----------------|----------------|
| `_run_analyze` | 437–974 | **EM** (E3) | `_copilot_inner` analyze / live_team / soft-404 |
| `_run_live` | 977–1017 | **EM** (E2) | `_copilot_inner` live_opportunities |
| `_run_bankroll` | 1020–1102 | **EM** thin (E1) | `_copilot_inner` |
| `_run_learning` | 1105–1182 | **EM** thin (E1) | `_copilot_inner` |
| `_run_knowledge` | 1185–1236 | **EM** thin (E1) | `_copilot_inner` |

**Encapsulation:** all `_run_*` are private to `copilot_unified_router.py`. No other SoT module imports them by name.

---

## 2. Stays on Router (NOT EM)

| Surface | Approx | Policy |
|---------|--------|--------|
| `_run_greeting` / `_run_help` / `_run_identity` / `_run_capabilities` / `_run_fallback` | 1239+ | Router conversational |
| `attach_match_card` inside analyze/live success | 962–973 / 987–1010 | Router presentation |
| `begin_request` / `end_request` | copilot HTTP wrap | Router / ops |
| Soft-try / post-assess / CM eligibility | `_copilot_inner` | Orchestration (§4.6–§4.7) |

---

## 3. CM write sites (never EM)

| Site | Approx | Notes |
|------|--------|-------|
| `_save_analysis_context` | def ~1563; calls ~3908, ~3999 | Subject `last_*` |
| Live `last_*` seed | ~4076–4089 | Out of EM (NR1) |
| LangGraph STS adapter | `_copilot_inner` | Orthogonal CM |

---

## 4. live_team_analyze composite (E4)

| Stage | Today | Destino |
|-------|-------|---------|
| T0 `search_live_for_team` | `_copilot_inner` ~L3949–4064 | **EM** Step Runner + Tool Use live-list port (Plan §3.3 CLOSED) |
| T1 analyze | `_run_analyze(..., prefer_live=True)` | **EM** analyze |
| CM seed on success | `_save_analysis_context` | **CM** — out of EM |

---

## 5. HARD-ABORT / integrity helpers

| Helper | Path | Role |
|--------|------|------|
| `assess_named_fixture` | `fixture_integrity.py` | Gate formula |
| `blocked_integrity_payload` | `fixture_integrity.py` | INVALID / HARD-ABORT HTTP shape (M-001) |
| Early abort in `_run_analyze` | ~L502–527 | Soft-skip if `VALID_LOCATED` rescue |

---

## 6. Frozen engines (consume-only)

Order in `_run_analyze` (~L543–584):  
`methodology` → `learning` → `confidence` → `market` → `methodology_v1` → `decision_center` → `knowledge` → `intelligence`  
Live: `live_intelligence_engine.build_live_payload`

**REGRA 19:** order change = ARCHITECTURAL DECISION REQUIRED.

---

## 7. Legacy parallel (not Shadow peer)

| Asset | Path | Policy |
|-------|------|--------|
| `copilot_engine` | `artifacts/aurora/src/core/copilot_engine.py` | Legado; retirement = later mission |
| `POST /aurora/chat` | `copilot_router.py` | Legado HTTP |

Shadow peer for unified clients = unified `_run_*` only (Plan I5).
