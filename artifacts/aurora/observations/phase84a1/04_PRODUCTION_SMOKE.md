# Phase 8.4-A.1 — Production smoke

## Question

`"o que você achou do jogo do fluminense ontem?"`

## Expected

| Check | Expected |
|-------|----------|
| `response_type` | `match_opinion` |
| `opinion_time` | `True` |
| `match_opinion_renderer` | `True` |
| Text contains | match reading / opinion tone |
| Must NOT contain | `panorama`, `Fase atual`, `Agenda à frente`, `team_summary` path |

## Code-on-main validation (post-push)

Run against tree = `origin/main` @ `93a9abc`:

```bash
cd artifacts/aurora
.venv/Scripts/python.exe scripts/phase83a_opinion_renderer_smoke.py
```

Result (local, same SHA as remote):

```text
[OK] 'o que você achou do jogo do fluminense ontem?'
     type=match_opinion opinion_time=True recent=True
     text='Sobre a partida do Fluminense: …'
PASS — 8.3-A opinion renderer
```

Full log: `smoke_local_stdout.txt`

## Live Autoscale HTTP

Not executed from this environment (no production base URL in repo; Republish is manual).

**After Replit Republish**, validate in UI:

1. Send the question above
2. DEBUG: `response_type=match_opinion` (or entities / natural path)
3. `backend_commit` ≈ `93a9abc…`
4. Visible reply must not be `**Fluminense** — panorama`
