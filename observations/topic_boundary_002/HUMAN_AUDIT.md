# TOPIC-BOUNDARY-002 — Human audit checklist

**Auditor:** agent + unit pipeline mirror  
**Flag under test:** `ENABLE_TOPIC_BOUNDARY_V2=1`  
**Default prod flag:** `0` (safe)

---

## Scenarios

### S1 — Soft FU, no reset

| Turn | User | Expected |
|------|------|----------|
| T1 | Flamengo x Palmeiras | Episode A |
| T2 | Quem está melhor? | Same episode; subject Flamengo/Palmeiras |

**Result (automated):** Pass — `episode_boundary` false; CSL teams stay Flamengo/Palmeiras.

**Human check:** Reply may contextualize FU with Flamengo/Palmeiras; must not invent a new fixture.

---

### S2 — Hard switch

| Turn | User | Expected |
|------|------|----------|
| T1 | Flamengo x Palmeiras | Episode A |
| T2 | Liverpool x Chelsea | New episode; CSL = Liverpool/Chelsea; **zero** Flamengo refs in rewritten message / CSL |

**Result (automated):** Pass — `boundary_reason=new_fixture`; SRF/bind cleared; sport-intent message has no Flamengo.

**Human check (live router):** User-visible text must not say `Mantendo foco Flamengo…`. Analyze entities home/away must be Liverpool/Chelsea (or honest unavailable — never Flamengo).

---

### S3 — FU after switch

| Turn | User | Expected |
|------|------|----------|
| T1 | Flamengo x Palmeiras | Episode A |
| T2 | Liverpool x Chelsea | Episode B |
| T3 | Quem está melhor? | Answer about Liverpool x Chelsea only |

**Result (automated):** Pass — FU pipeline keeps Liverpool/Chelsea; no Flamengo in message/CSL.

**Human check:** No honesty prefix tying back to Flamengo.

---

### S4 — Partial boundary

| Turn | User | Expected |
|------|------|----------|
| T1 | Flamengo x Palmeiras | Episode A |
| T2 | Inter joga hoje? | Boundary (`low_entity_overlap`); CSL subject → Inter |

**Result (automated):** Pass — detect + apply with Inter seeded; Flamengo teams gone.

**Human check:** Calendar/schedule path for Inter; no Flamengo fixture reuse.

---

## Regression gates

| Gate | Pass? |
|------|-------|
| Flag OFF → noop (legacy sticky behavior unchanged) | Yes |
| TB001 suite still green | Yes (16/16 with TB002) |
| No engine / selector / OS / SCG / SLL edits | Yes |
| No invented odds/fixtures in boundary path | Yes (seed from user message entities only) |

---

## Go / no-go

| Decision | Condition |
|----------|-----------|
| **Ship code** (flag default 0) | Yes — additive + tested |
| **Default ON** | No until live S2/S3 human pass on full router |
| **Commit** | Only when product owner asks |

---

## Residual risks

1. If analyze still resolves wrong clubs from knowledge/graph **independent of CSL**, honesty may still mention wrong teams — out of scope for boundary order/cleanup.  
2. Single-team ask regex is Portuguese-leaning (`joga` / `enfrenta`); English “Inter play today?” may not trigger partial boundary until SLL supplies clubs.
