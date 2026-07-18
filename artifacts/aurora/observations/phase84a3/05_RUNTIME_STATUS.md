# Phase 8.4-A.3 — Runtime status

| Ambiente | `/aurora/healthz` | Notas |
|----------|-------------------|--------|
| Local TestClient | **200** | `backend_commit=872bd19` |
| Local uvicorn :18081 | **200** | startup completo |
| Produção Replit host | **500 / TLS fail** | processo/edge unhealthy |
| Código SoT `main` | OK | inclui mop |

## Restore status

| Item | Status |
|------|--------|
| Diagnóstico código | DONE — app saudável localmente |
| Falso positivo Chilean / verify-layout | FIXED (pending push) |
| Runtime Autoscale | **NOT RESTORED** — requer logs + Republish no Replit |
| Smoke Fluminense prod | BLOCKED até healthz 200 |

## Bottom line

Backend **código** está OK. Backend **publicado** não responde. Recuperação = ação no painel Replit + Republish, não novo patch de opinion renderer.
