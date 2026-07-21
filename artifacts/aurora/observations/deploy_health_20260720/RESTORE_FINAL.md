# Restore attempt — final status

## Status final: OFFLINE

## Causa final
Autoscale Replit não está servindo um worker saudável no host
`aurora-stats.marvel69123-sketch.replit.app` (TLS/edge fail / HTTP 500 sem body JSON).
Código SoT no GitHub está OK e build local passou; o bloqueador restante é **Republish no Replit** (ação de UI/conta, inacessível daqui sem login).

## Ações realizadas
1. Commit + push fix Query: `0c52710` — `fix(aurora): unwrap FastAPI Query defaults in analyze_fixture`
2. Sync mirror + push: `7b61ef0` — `chore: sync aurora mirror for deploy layout verify`
3. `verify-layout` OK; `pnpm run deploy` OK (build local)
4. Probes prod repetidos → healthz não 200

## HEAD / origin/main
`7b61ef06fcb6e71600e7e413c5ceca7464f2a20a`

## backend_commit publicado (prod)
**ilegível** — healthz não responde

## Ação humana obrigatória (1 passo)
No workspace Replit ligado a este repo:
```bash
cd ~/workspace
git pull origin main
pnpm run deploy   # opcional se build já ok
```
Depois: **Publishing → Publish / Republish**.

Smoke alvo:
`GET /aurora/healthz` → `{"status":"ok",...,"backend_commit":"7b61ef0"}` (ou prefixo)
