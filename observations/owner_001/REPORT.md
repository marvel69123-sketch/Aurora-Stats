# AURORA-OWNER-001 — Why skill outputs never reach the user

**Type:** Investigation only (no code changes)  
**Date:** 2026-07-21  
**Scope:** INTENT-001 sport skills → final `CopilotResponse.executive_summary`

---

## Verdict

Specialized skills never lose a finished answer to ownership — **they never produce one**. Skills only rewrite the inbound `message` and stamp metadata. An earlier SPORT claimer then authors `executive_summary`; late honesty prefixes **Mantendo foco…** + **No-bet…**. `finalize` / `CopilotResponse` serialize that payload; they do not invent skill prose.

---

## Answers (task questions)

| # | Question | Answer |
|---|----------|--------|
| 1 | Does `ownership_stability` overwrite skill outputs? | **No skill response text exists to overwrite.** OS (and force-claim after GA block) **early-claims** the turn and becomes (or stamps) the reply author. Soft hold: “Continuando sobre…”. `_stamp_stability` may replace GA-loop crumbs with “Mantendo o contexto…”. |
| 2 | Does `finalize_response` replace responses? | **No.** Forensics stamp entities; `CopilotResponse` copies `payload["executive_summary"]`. No skill content is introduced at finalize. |
| 3 | Are no-bet shells injected after skills? | **Yes.** `partial_inference_honesty.apply_honesty_to_payload` (~router L5022) prefixes posture including `No-bet: sinais insuficientes para stake.` when `bankroll_recommendation.no_bet` (default true on holds / soft sections). |
| 4 | Which component becomes final owner? | **`turn_owner=SPORT`**. `response_owner` is typically **`ownership_stability`** (soft hold / force) or a continuity resolver (`conversation_continuity` / pronoun / advanced) when those claim first. Skills are never `response_owner`. |

---

## Call chain (relevant slice)

```
User message
  → SLL (sports_language)
  → CSL (conversation_state_layer)          # may inject fixture into FU text
  → Sport Intent / skills (INTENT-001)      # MESSAGE REWRITE ONLY + ctx stamp
      skill_* → str | None                  # never builds executive_summary
  → Entity v2 resolve_referent              # ASSUME stamps "Mantendo foco…" on ctx
                                            # (CLARIFY-only early claim)
  → Continuity / Pronoun / Advanced         # may early-claim short FUs
  → Sport Continuity Guard                  # may early-claim
  → Ownership Stability try_*_claim         # may early-claim
  → MasterIntent / GA
      if owner lock + sport anchor:
        should_block_ga → force_owner_claim_after_ga_block
          → soft hold payload (SPORT)       # ★ PRIMARY CLAIM FOR SKILL-SHAPED FUs
  → … (analyze / Natural / skill sinks skipped when payload set)
  → P2.5 stamp_bind + apply_honesty         # ★ NO-BET + assumption PREFIX
  → restore_continuity_draft (if wiped to "?")
  → CopilotResponse(executive_summary=…)    # serialize only
```

**Key modules**

| Stage | File | Role |
|-------|------|------|
| Skill | `sport_intent_layer.py` | `apply_sport_intent_resolve` → rewritten string; `note_sport_intent_on_payload` stamps intent/skill only |
| Early claim | `copilot_unified_router.py` ~1976–2168, ~2210–2268 | Continuity / OS / SCG / force after GA block |
| Soft hold | `ownership_stability.py` `_build_hold_payload` | Continuity shell + `response_owner=ownership_stability` |
| Honesty | `partial_inference_honesty.py` | Prefix assumption + No-bet onto sportish payloads |
| Finalize | router ~4986–5171 | Forensics + `CopilotResponse` construction |

---

## Ownership transitions (observed FU)

**Seed:** `Flamengo x Palmeiras` → GA / analyze, then `OwnerLock: ACTIVE owner=SPORT`, sport anchor created.

**Follow-up:** `Quem está melhor?`

| Step | Owner / state | What happens to text |
|------|---------------|----------------------|
| CSL | — | Often contextualizes to “Entre Flamengo e Palmeiras, quem está melhor?” |
| Skill `skill_recent_form` | — | Rewrites **message** → e.g. `forma recente de Flamengo e Palmeiras`; stamps `sport_intent=recent_form`, `sport_skill=skill_recent_form` |
| Entity v2 | ASSUME (no claim) | `bind_assumptions=["Mantendo foco Flamengo x Palmeiras (…)"]` on ctx |
| Short-FU resolvers | often miss | Skill-shaped text is **not** `placar`/`mercados`/… kind → continuity / SCG often return `None` |
| GA block + force | **SPORT** claim | Soft hold / stamped continuity shell becomes payload; `skipped_nl`; later “ContinuityFollowUp: skipped … already claimed” |
| Presence / early finalize | `turn_owner=SPORT`, `rewrite_locked=True` | Locks reply; late rewrite/review skipped |
| Honesty | same owner | Prefix: Mantendo foco + No-bet |
| CopilotResponse | **final** | User sees honesty shell (± hold body), **not** form comparison |

Live trace markers (OWNER-001 probe):

- `[SPORT_INTENT] intent=recent_form skill=skill_recent_form … rewritten=True`
- `[AUDIT] ContinuityFollowUp: skipped repair/GA/HCE — already claimed`
- `[FINAL_SOURCE] owner=SPORT … intent=follow_up`
- Final summary prefix: `Mantendo foco …` + `No-bet: sinais insuficientes…`
- Entities: `sport_intent` / `sport_skill` present; `honesty_modes=['BINDING_ASSUMED','NO_BET_HARD']`; `continuity_followup` / ownership flags as claimed

---

## Response diffs (intent vs final)

| Stage | Content |
|-------|---------|
| User | `Quem está melhor?` |
| After CSL (typical) | `Entre Flamengo e Palmeiras, quem está melhor?` |
| After skill (routed message) | `forma recente de Flamengo e Palmeiras` |
| **Skill “ideal” reply (does not exist)** | Would be form/strength prose for both clubs |
| Early-claimed payload | Continuity / soft-hold shell (`Continuando sobre…` / contextual FU prose / short crumb) |
| After honesty (user-visible) | `Mantendo foco Flamengo x Palmeiras (…)` + `No-bet: sinais insuficientes para stake.` (± residual hold body) |

**Diff takeaway:** Skill changes the **router input string**, not the **response**. Final text is authored by ownership/continuity + honesty.

---

## Exact overwrite / claim points

There is no “skill `executive_summary` overwritten at line X.” There are two decisive points:

### 1. Claim point (skill never becomes author) — **exact**

When SPORT owner-lock is active and GA is blocked, router force path:

`copilot_unified_router.py` ~2232–2268 → `force_owner_claim_after_ga_block` / `try_sport_continuity_claim`

or earlier early-claim:

`try_ownership_stability_claim` ~2146–2168  
`try_contextual_short_followup` ~2028–2050  

→ sets `payload`, `skipped_nl=True` → analyze / Natural / any hypothetical skill sink **never run as response authors**.

### 2. Shell injection point (user-visible No-bet / Mantendo foco) — **exact**

`copilot_unified_router.py` ~5022–5035:

1. `stamp_bind_on_payload` merges Entity v2 ASSUME assumptions  
2. `apply_honesty_to_payload` → `render_honesty_prefix` prepends:
   - assumption line from `Mantendo foco {fixture}` (`entity_resolver_v2.py` ~605–607)
   - posture `No-bet: sinais insuficientes para stake.` when `NO_BET_HARD` / `no_bet=True`

### 3. Finalize — **not** an overwrite of skills

`CopilotResponse(..., executive_summary=payload["executive_summary"], ...)` ~5128–5156 — passthrough.

---

## Why INTENT-001 feels “dead” on follow-ups

1. **Architecture:** skills = reshape + metadata, by design (no payload emission).  
2. **Ownership wins early:** locked SPORT session + force/ soft hold owns FU turns.  
3. **Irony:** skill rewrite can make the message **less** like a registered short FU (`_is_short_followup` / `_CONTINUITY_FU`), so specialized continuity prose does not fire → generic hold.  
4. **Honesty** then paints the hold with Mantendo foco + No-bet — matches human-audit thin replies.

---

## Minimal patch proposal (design only — do not implement here)

Prefer **additive** claim before OS soft hold; avoid editing FROZEN `ownership_stability` core if policy forbids.

### Option A (recommended): Skill response sink (pre-OS)

After sport intent classification, if `conf ≥ threshold` and entities/anchor available:

- Build a real payload (`executive_summary` = skill answer, `response_owner=sport_intent_skill`, `turn_owner=SPORT`, `rewrite_locked=True`, `no_bet` as appropriate).
- Claim **before** OS soft hold / force path (same pattern as `advanced_football_continuity`).
- Stamp existing `sport_intent` / `sport_skill`.

### Option B: Branch soft-hold / continuity templates on `ctx["sport_intents"]`

If OS must stay frozen: wrap or post-filter only the soft-hold text when `sport_intent` is set — emit skill-shaped prose instead of “Continuando sobre…”. Weaker than A (still no real form analysis unless skill builds it).

### Option C: Skip GA-block force soft hold when high-conf sport intent needs analyze

If `sport_intent in {recent_form, compare_strength, …}` and anchor exists → do **not** force soft hold; allow analyze / a dedicated skill engine. Risk: GA steal regressions — gate tightly.

### Honesty interaction

Whatever authors the skill reply should either:

- set `bankroll_recommendation.no_bet` intentionally and accept No-bet posture, or  
- mark entities so honesty does not replace the whole answer with assumption-only shells (e.g. skip assumption prefix when `response_owner=sport_intent_skill`).

### Do not

- Expect `finalize` / forensics to emit skill text.  
- Treat Entity v2 ASSUME as a response author (it only feeds honesty).

---

## Frozen-surface note

`ownership_stability`, `sport_continuity_guard`, and related continuity guards are FROZEN for many patches. OWNER follow-up work should prefer **Option A** (new pre-claim skill sink) over editing OS claim internals.

---

## Evidence references

- `artifacts/aurora/src/conversation/sport_intent_layer.py` — skills return `str`, not payloads  
- `artifacts/aurora/src/routers/copilot_unified_router.py` — early claim ~2146; force ~2232; honesty ~5022; `CopilotResponse` ~5128  
- `artifacts/aurora/src/conversation/ownership_stability.py` — claim chain, `_build_hold_payload`, `_stamp_stability`  
- `artifacts/aurora/src/conversation/partial_inference_honesty.py` — prefix + No-bet  
- `artifacts/aurora/src/core/entity_resolver_v2.py` — soft maintain `Mantendo foco…`  
- Probe: session FU after fixture opener (OWNER-001 live copilot) — skill stamp yes; final text honesty shell; `owner_final=SPORT`
