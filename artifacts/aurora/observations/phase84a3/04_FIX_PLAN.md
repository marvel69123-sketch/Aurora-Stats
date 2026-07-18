# Phase 8.4-A.3 — Fix plan

## A) Imediato no Replit (obrigatório para restaurar runtime)

1. Abrir **Deployments** → build `b3b68a8f-…` / latest  
2. Copiar **Build log** + **Runtime log** (procurar `Traceback`, `ModuleNotFoundError`, `Address already in use`, OOM)  
3. No Shell do workspace:
   ```bash
   cd ~/workspace && git pull origin main
   cd artifacts/aurora && python -m uvicorn main:app --host 0.0.0.0 --port 8080
   # em outro terminal:
   curl -sS http://127.0.0.1:8080/aurora/healthz
   ```
4. Se local-no-Replit = 200 → **Republish** Autoscale  
5. Se local-no-Replit falha → o traceback do passo 3 é a causa real

## B) Já corrigido neste repo (deploy prep)

- `scripts/verify-layout.sh`: check Chilean aliases aponta para `team_aliases.py`  
  (antes falhava com falso positivo em `copilot_engine.py` e bloqueava `pnpm run deploy`)

## C) Não fazer

- Não reverter `match_opinion_renderer` (não é a causa)  
- Não adicionar workers  
- Não exigir env secrets no healthz  

## D) Validação pós-restore

```text
GET /aurora/healthz → 200 + backend_commit ∈ {872bd19, a7475fc, 93a9abc+}
POST /aurora/copilot "o que você achou do jogo do fluminense ontem?"
  → response_type=match_opinion (sem panorama)
```
