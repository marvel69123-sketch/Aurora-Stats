# TOPIC-BOUNDARY-002 — Transcripts before / after

Evidence sources:

- **Before:** `observations/sticky_bleed_001/REPORT.md` + `observations/parallel_human_audit_001` (V2 ON, bleed)  
- **After:** `tests/test_topic_boundary_v2_002.py` pipeline mirror (boundary → CSL → sport intent)

---

## BEFORE (sticky bleed — V2 ON, pre-002)

### Turn 1

```text
User: Flamengo x Palmeiras
Aurora: [analyze / partial on Flamengo x Palmeiras]
ctx: episode_id=6af4d299…  csl=Flamengo x Palmeiras  SRF=Flamengo x Palmeiras
```

### Turn 2 — bug

```text
User: Liverpool x Chelsea

Pipeline (old order):
  SLL → CSL keeps Flamengo/Palmeiras → Sport Intent rewrites to
       "analisar Flamengo x Palmeiras (comparativo de forca)"
  → TopicBoundaryV2 NEW_EPISODE (episode_id rotates)
  → analyze Flamengo → honesty "Mantendo foco Flamengo x Palmeiras…"
  → note_csl writes Flamengo again

Aurora (observed): Mantendo foco Flamengo x Palmeiras… + Flamengo analysis
ctx end: episode_id rotated, but csl_fixture / entities still Flamengo vs Palmeiras
Liverpool/Chelsea mentioned: false
```

---

## AFTER (TOPIC-BOUNDARY-002 — V2 ON)

### Scenario 1 — soft FU (no reset)

```text
User: Flamengo x Palmeiras
User: Quem está melhor?

Pipeline:
  SLL → Boundary keep (soft_followup_same_episode) → CSL FU inject
       → Sport Intent (compare on Flamengo/Palmeiras)

Expected / tested:
  episode_boundary = false
  csl.teams = [Flamengo, Palmeiras]
  message retains Flamengo/Palmeiras context
```

### Scenario 2 — hard switch (subject rotates)

```text
User: Flamengo x Palmeiras
User: Liverpool x Chelsea

Pipeline (new order):
  SLL → TopicBoundaryV2 NEW_EPISODE (new_fixture)
       clears SRF / entity_v2_last_bind / short sport memory
       replaces csl.teams/fixture/topic → Liverpool x Chelsea
       sets csl_subject_guard
  → CSL resolve respects guard + message sides
  → Sport Intent rewrite uses Liverpool/Chelsea (not Flamengo)

Expected / tested:
  boundary_detected = true
  boundary_reason = new_fixture
  subject_replaced = true
  srf_cleared / entity_bind_cleared = true
  rewritten message contains no Flamengo/Palmeiras
  csl.fixture ≈ Liverpool x Chelsea
```

### Scenario 2b — note_csl poison blocked

```text
(same T2, if analyze payload still returns Flamengo home/away)

note_csl_after_response → note_csl_blocked = true
csl.teams remain Liverpool/Chelsea
```

### Scenario 3 — FU after switch

```text
User: Flamengo x Palmeiras
User: Liverpool x Chelsea
User: Quem está melhor?

Expected / tested:
  episode_boundary = false on T3
  FU / CSL subject = Liverpool/Chelsea
  no Flamengo in message or csl.teams
```

### Scenario 4 — partial boundary

```text
User: Flamengo x Palmeiras
User: Inter joga hoje?

Expected / tested:
  boundary_reason = low_entity_overlap
  csl.teams include Inter; exclude Flamengo
```

---

## Diff summary

| Signal | Before | After |
|--------|--------|-------|
| Episode id on T2 switch | Rotates | Rotates |
| Router message on T2 | Flamengo compare | Liverpool compare |
| SRF on T2 | Flamengo sticky | Cleared |
| `entity_v2_last_bind` | Flamengo sticky | Cleared |
| End CSL fixture | Flamengo (note_csl) | Liverpool (guard) |
| Honesty “Mantendo foco Flamengo” | Yes | Blocked at source (no SRF/bind) |
