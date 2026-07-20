# P2.5-S — Sports Understanding MVP

**Objective:** Route real sports questions into the sports pipeline; eliminate `UNKNOWN` / `SMALL_TALK` on sport asks.

**Validation:** **PASS** (`sports_understanding_validation.json` — 5/5 sport cases `dialog_mode=SPORT`)

## Problem (from destroy analysis)

Real-team turns almost never hit `analyze_match` / sport ownership. They landed in `clarification` + `UNKNOWN`/`SMALL_TALK` soft-assume echoes (“Entendi que o pedido era…”) instead of team/fixture answers.

## Policy

1. Detect real sport signals (known clubs, fixtures, form asks) — exclude pure fiction.
2. Force `dialog_mode=SPORT` when master intent is `SPORT_QUERY`/`LIVE_MATCH` or real sport signal present.
3. Never demote forced SPORT into SMALL_TALK via clarify-expire / unknown-loop.
4. Expand NC `team_opinion` for `tá bem` / `ta bem` / `como tá`.
5. Stamp `dialog_mode=SPORT` on sport-owned payloads (form + fixture/follow_up).
6. Credibility SOCIAL mode must not rewrite sport-owned intent to `small_talk`.

## Files

| File | Change |
|------|--------|
| `src/conversation/sport_understanding.py` | **New** — recall / force / enrich helpers |
| `src/conversation/dialog_mode.py` | Force SPORT; block assume demotion |
| `src/conversation/natural_conversation.py` | Form-ask patterns + SPORT entity stamp |
| `src/conversation/master_intent_router.py` | Sport regex includes `tá bem` |
| `src/conversation/reflection_credibility.py` | Do not demote sport-owned → small_talk |
| `src/routers/copilot_unified_router.py` | Post-NL recall + final SPORT stamp |

## Validation (live TestClient)

| Case | dialog_mode | Notes |
|------|-------------|-------|
| `o Bahia tá bem?` | **SPORT** | `team_opinion` / conversation_assist |
| `Corinthians tá bem? agora` | **SPORT** | same |
| `Botafogo tá bem?` | **SPORT** | same |
| `Flamengo x Palmeiras` | **SPORT** | sport follow_up / owner SPORT |
| `analisar Santos x Bahia` | **SPORT** | same |
| `oi` | (non-sport) | unchanged small_talk |
| `Goku vs Naruto` | **FICTION** | gate preserved |
| `Batman vs Superman` | **FICTION** | gate preserved |

`target_met: true` — **0** sport cases with UNKNOWN/SMALL_TALK/null dialog_mode.

## Not in scope

- Sports engine / invented odds or live stats (API key may be absent; honest degrade OK)
- Full destroy re-run (optional follow-up)
- Pronoun FU without prior sport frame (`e o meio-campo?` still needs anchor)

## Artifacts

- `sports_understanding_patch.md` (this file)
- `sports_understanding_validation.json`
