# Sport Understanding Failure Analysis

**Mode:** ANALYSIS ONLY (no implementation)
**Generated:** 2026-07-20T22:52:08.991871+00:00
**Corpus:** post–P3-D.4 destroy — `human_stress_sessions_full.json` + `conversation_failures.json`

---

## Verdict

**Root cause:** real sport questions are almost never routed to `analyze_match`.

On **1285** turns that mention a real team, only **23 (1.8%)** get `intent=analyze_match`.
The rest go to `clarification` (641), `conversation_assist` (385), `conversation_repair` (125), etc.
Dialog modes are mostly `UNKNOWN` / `SMALL_TALK`.

Aurora *talks around* the question (soft-assume echo, anchors, hollow recovery) instead of answering it.
Perception MVPs reduced sticky banks; they did **not** fix sport referent + intent binding.

Destroy loop taxonomy still **context_confusion ≈ 79.6%** — an understanding/binding class.

## Why perception improvements were not enough

| Layer fixed by P3-C/D | What still breaks sport understanding |
|----------------------|----------------------------------------|
| Belief abandon / anti-reactivation | Does not choose `analyze_match` |
| Commitment recovery | Turns short sport/repair into hollow uncommitted |
| Response diversification | Replaces answers with anchors/short generics |
| Jaccard / fingerprint cooldown | Stops repeats; does not bind fixture/team |

## Evidence (destroy dumps)

### Real-team intent routing

| Intent | Count | Share |
|--------|------:|------:|
| clarification | 641 | 49.9% |
| conversation_assist | 385 | 30.0% |
| conversation_repair | 125 | 9.7% |
| follow_up | 64 | 5.0% |
| small_talk | 36 | 2.8% |
| **analyze_match** | **23** | **1.8%** |

### Real-team dialog modes

| Mode | Count |
|------|------:|
| UNKNOWN | 505 |
| SMALL_TALK | 360 |
| ? | 253 |
| REPAIR | 96 |
| FICTION | 70 |
| CLARIFICATION | 1 |

### Broad sport-turn failure tags (supporting)

| Tag | Count | Role |
|-----|------:|------|
| soft_assume_template | 454 | Meta echo instead of sport answer |
| fiction_false_positive* | 427 | Inflated by chaos (Pikachu/Batman); clean FP smaller |
| hollow_uncommitted_instead_of_sport | 386 | Recovery after repair kills sport thread |
| anchor_without_sport_answer | 346 | Diversify anchor on follow-ups |
| over_ask_instead_of_bind | 238 | Re-ask instead of bind |

\*Narrowed samples: fiction replies mostly on mixed fiction+team chaos, not clean `Flamengo x Palmeiras`.

## Concrete dump examples

**Soft-assume on a real team ask (no sport answer):**
- User: `Aurora, o Bahia tá bem?!!!`
- Aurora: `Vou assumir o fio… Entendi que o pedido era: "Aurora, o Bahia tá bem?!!!". Vou responder em cima disso…`
- intent=`clarification`, dialog=`UNKNOWN`

**Follow-up part ask → anchor, not binding:**
- User: `e o meio-campo?`
- Aurora: `Ancorando no que você trouxe ("e o meio-campo?")… Quer aprofundar ou mudar o recorte?`
- No fixture/team referent resolution

**Repair → hollow (sport thread lost):**
- User: `já falei` / `para de repetir`
- Aurora: `Mudando o formato: sem status de compromisso…` / `Modo aberto…`

## Causal stack

1. **intent_router** — real team asks → clarification/assist (not analyze_match) → no sport-answer path
2. **dialog_mode** — UNKNOWN/SMALL_TALK dominate → wrong reply family
3. **answer_fit** — soft-assume echoes text without form/market/live content
4. **followup_binding** — `e o meio-campo?` gets anchors, not referent bind
5. **repair_side_effect** — frustration → hollow uncommitted, sport abandoned
6. **loop_taxonomy** — context_confusion confirms binding class

## What next work should target (not implementing now)

1. Sport intent recall when real teams/fixtures present
2. Question-shape routing (form / live / odds / pronoun / part-of-team)
3. Follow-up referent bind before diversification anchors
4. Keep fiction gate for pure fiction; do not eclipse the real-team part in mixed lines

## Artifacts

- `sport_understanding_failure_analysis.md` (this file)
- `sport_understanding_failure_analysis.json`
- Script: `roadmap/scripts/analyze_sport_understanding_failures.py`
