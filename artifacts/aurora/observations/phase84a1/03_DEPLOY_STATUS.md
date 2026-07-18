# Phase 8.4-A.1 — Deploy status

## GitHub (SoT)

| Item | Value |
|------|--------|
| Commit | `93a9abc` |
| Message | `feat(aurora): ship match-opinion renderer so recent-match asks skip panorama` |
| Branch | `main` |
| Push | **OK** → `origin/main` |
| `match_opinion_renderer.py` on remote | **YES** |

Verify:

```bash
git ls-tree -r origin/main --name-only | grep match_opinion
# artifacts/aurora/src/conversation/match_opinion_renderer.py
```

## Replit runtime

| Step | Status |
|------|--------|
| Code on GitHub `main` | DONE |
| Local `pnpm run deploy` prep | BLOCKED (unrelated: `verify-layout` → `copilot_engine missing Chilean aliases`) — not required for backend mop |
| Replit `git pull` + **Republish** | **MANUAL — required** (Cursor cannot click Republish) |

Per `DEPLOY.md`: push alone does not update Autoscale until Republish.

## Backend relevance

8.3-A is **backend-only** (`artifacts/aurora`). After Republish, confirm UI DEBUG `backend_commit` starts with `93a9abc`.
