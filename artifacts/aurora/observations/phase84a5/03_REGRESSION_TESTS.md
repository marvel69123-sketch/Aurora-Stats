# Phase 8.4-A.5 — Regression tests

Command: `scripts/phase84a5_ownership_smoke.py`

| Case | Result |
|------|--------|
| Opinion Fluminense ontem | **OK** — `match_opinion`, no overwrite, no leitura rápida/Momento |
| Calendar `tem jogo do fluminense hoje?` | **OK** — not stolen as `match_opinion` |
| Team summary `me fale sobre o flamengo` | **OK** — `team_summary`, overwrite=None |
| Small talk `oi` | **OK** — `small_talk` |
| Repair `não foi isso` | **OK** — repair reply, not Entendi/panorama |

```text
PASS — 8.4-A.5 ownership patch
```
