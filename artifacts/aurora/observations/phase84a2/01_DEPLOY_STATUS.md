# Phase 8.4-A.2 — Deploy status

## GitHub SoT (`origin/main`)

| Field | Value |
|-------|--------|
| HEAD | `872bd19` — *Published your App* (Replit Deployment) |
| Prior feature | `93a9abc` — match-opinion renderer |
| Docs | `a7475fc` |
| `match_opinion_renderer.py` on tree | **YES** |
| `93a9abc` ancestor of HEAD | **YES** |

Replit publish marker:

```text
Replit-Commit-Deployment-Build-Id: b3b68a8f-2c2f-4c22-b037-fcb4dcd3cd8e
```

→ houve **tentativa de Republish** depois do push do 8.3-A.

## Runtime probe (esta sessão)

| Host | `/aurora/healthz` | Notes |
|------|-------------------|--------|
| `https://aurora-stats.marvel69123-sketch.replit.app` | **500** (WebFetch) / SSL EOF (local curl/httpx) | candidato principal — **não saudável** |
| `https://aurora-stats-marvel69123-sketch.replit.app` | 404 “isn't live yet” | alias morto |
| `https://marvel69123-sketch-aurora-stats.replit.app` | 404 “isn't live yet” | alias morto |
| `https://aurora-stats.replit.app` | 404 “isn't live yet” | alias morto |

## Verdict (deploy status)

| Layer | Status |
|-------|--------|
| Code on GitHub includes mop | **OK** |
| Republish commit exists after mop | **OK** (`872bd19`) |
| Live Autoscale healthy + readable `backend_commit` | **FAIL / UNREADABLE** |
| Production smoke Fluminense | **BLOCKED** (sem healthz 200) |
