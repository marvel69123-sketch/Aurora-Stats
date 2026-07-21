# Root Cause — Deploy health 2026-07-20

## 1) Deploy Autoscale unhealthy (primary)

**Symptom:** `GET /aurora/healthz` on production host fails (TLS/connection closed locally; edge **500** without FastAPI JSON error body). Alternate hosts return **404** “isn't live yet”.

**Why this is ops, not P2.5-S:**
- Health handler is dependency-light and never imports sport understanding.
- Local `TestClient` `/aurora/healthz` → **200** with `backend_commit=b984c48`.
- Bare edge 500 / TLS EOF matches prior phase 8.4-A.3 conclusion: Autoscale edge without a healthy uvicorn worker (crash-loop or unpublished instance).

**Publish lag:**
- SoT `origin/main` = `b984c48` (P2.5-S).
- Last git marker `Published your App` = `b30ec32` (before P2.5-S).
- Even if edge recovers on an old build, published commit may lag `main` until Republish.

**Required ops action:** Replit Shell → `git pull origin main` → `pnpm run deploy` → **Republish** → hard refresh → confirm healthz 200 + `backend_commit`.

---

## 2) SoT runtime regression — `Query.strip` (fixed locally)

**Symptom (pre-fix):** Every `/aurora/chat` path that hits `analyze_match` → `analyze_fixture(home, away)` as a plain coroutine raised:

```text
AttributeError: 'Query' object has no attribute 'strip'
```

**Mechanism:**
1. `analyze_fixture` is both a FastAPI route and an internal async function.
2. Defaults use `user_id: str | None = Query(None)` (and other `Query(...)`).
3. Internal callers omit those kwargs → parameters receive **Query Param objects**, not `None`/`False`.
4. `bool(user_id)` is truthy for a Query object → enters `begin_request(user_id)`.
5. `(user_id or "anonymous").strip()` → AttributeError.

**Relation to P2.5-S:** P2.5-S increases traffic into sport/`analyze_match`, which **surfaces** the bug more often. It does not create the Query leak. Healthz remains unaffected.

**Minimal fix (applied in working tree):**
- Unwrap non-`str`/`bool`/`int` Query leaks at start of `analyze_fixture`.
- Harden `cost_protection._coerce_user_id` so `.strip()` never runs on Param objects.

**Post-fix:** Query error gone; without `API_FOOTBALL_KEY`, fixture path degrades to 404/fail-open (expected).

---

## 3) P2.5-S secondary risks (not deploy-fatal)

- Force `analyze_match` without populating `home`/`away` → fixture miss / Inference V2 fallback.
- Exception swallowing (`except Exception: pass`) on sport short-FU import/stamp → silent fail-open.
- Audit WARNING loops (`OWNER_AFTER SPORT` ×N) — observability noise, not crash.

These are product degradation risks after Autoscale is healthy; they are **not** the cause of healthz 500.
