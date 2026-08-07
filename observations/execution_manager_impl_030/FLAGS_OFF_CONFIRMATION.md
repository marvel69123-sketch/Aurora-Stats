# Mission 030 — Feature flags OFF confirmation (Phase 1 Prep)

**Plan §8 names (final).** Production-affecting defaults must remain **OFF / 0%**.

| Flag | Required default | Product code getter (Phase 1) | Env observed |
|------|------------------|------------------------------|--------------|
| `ENABLE_EXECUTION_MANAGER_SHADOW` | OFF | **ABSENT** (not wired) | unset → treat OFF |
| `ENABLE_EXECUTION_MANAGER` | OFF | **ABSENT** | unset → treat OFF |
| `ENABLE_EM_PIPELINE_BANKROLL` | OFF | **ABSENT** | unset → treat OFF |
| `ENABLE_EM_PIPELINE_LEARNING` | OFF | **ABSENT** | unset → treat OFF |
| `ENABLE_EM_PIPELINE_KNOWLEDGE` | OFF | **ABSENT** | unset → treat OFF |
| `ENABLE_EM_PIPELINE_LIVE` | OFF | **ABSENT** | unset → treat OFF |
| `ENABLE_EM_PIPELINE_ANALYZE` | OFF | **ABSENT** | unset → treat OFF |
| `ENABLE_EM_PIPELINE_LIVE_TEAM` | OFF | **ABSENT** | unset → treat OFF |
| `ENABLE_EM_PGR_01` … `ENABLE_EM_PGR_06` | OFF | **ABSENT** | unset → treat OFF |
| `EM_ACTIVATION_PCT` | **0** | **ABSENT** | unset → treat 0 |

**Phase 1 policy:** Plan Prep confirms flags **absent or OFF**. Flag **controller** + illegal matrix I1–I8 land in **Phase 2 Infrastructure** (not this mission).

**Repo search (Prep):** Plan document mentions names; **no** product wiring under `artifacts/aurora/src/` for EM flags.

```text
FLAGS PRODUCT WIRING: ABSENT
EFFECTIVE POSTURE: ALL OFF / 0%
SHADOW ARMED: NO
SOLE-PATH ARMED: NO
PGR ARMED: NO
```
