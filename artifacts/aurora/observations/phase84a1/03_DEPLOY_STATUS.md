# Phase 8.4-A.1 — Deploy status

## Procedure (DEPLOY.md)

1. Commit + push GitHub `main` ← **this phase**
2. Replit workspace: `git pull origin main` + `pnpm run deploy` (if UI build needed)
3. **Republish** no Replit (Autoscale)
4. Hard refresh UI; confirm `backend_commit` = SHA deste push

## Status at write time

| Step | Status |
|------|--------|
| Local mop file present | DONE |
| Local smoke 8.3-A | PASS |
| Commit on `main` | pending → see git after push |
| Push `origin/main` | pending → see git after push |
| Replit Republish | **manual** — required after push (Agent cannot click Republish) |
| Live prod HTTP smoke | pending URL / post-Republish |

## Note

Backend SoT is `artifacts/aurora`. Pushing mop to `main` is necessary and sufficient
for code presence; runtime updates only after Replit pulls + Republish.
