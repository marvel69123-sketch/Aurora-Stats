# Replit — Republish guide (Aurora)

## Estrutura oficial (única)

```
~/workspace/                         ← raiz do monorepo
  package.json                       ← name: "workspace"  (NUNCA o frontend)
  pnpm-workspace.yaml
  tsconfig.base.json
  tsconfig.json
  artifacts/
    web/                             ← FRONTEND SoT (React/Vite)
      package.json                   ← @workspace/web
      vite.config.ts
      tsconfig.json                  ← extends ../../tsconfig.base.json
      src/
      public/
      .replit-artifact/artifact.toml ← static serve
    aurora/                          ← BACKEND SoT (FastAPI)
      main.py
      start.sh
      requirements.txt
      src/                           ← NLP, live, analyze, copilot
    api-server/                      ← scaffold Node + artifact.toml que
                                       aponta o serviço Python para aurora/
  lib/                               ← packages TS compartilhados
  aurora/                            ← espelho local OPCIONAL (não é deploy)
```

### Proibido na raiz

- `vite.config.ts` / `vite.config.js`
- `package.json` do frontend (`@workspace/web`)
- `src/` do React
- `public/` do frontend
- copiar arquivos “para a raiz funcionar”

### Fonte de verdade

| Peça | Caminho |
|------|---------|
| Frontend | `artifacts/web` |
| Backend Aurora | `artifacts/aurora` |
| Deploy Python (Replit ID) | `artifacts/api-server/.replit-artifact/artifact.toml` → roda `artifacts/aurora` |
| Espelho local | `aurora/` via `bash scripts/sync-aurora-mirror.sh` |

---

## Comandos no Replit (Shell)

```bash
cd ~/workspace

# 1) Verificar layout (falha se a estrutura estiver quebrada)
bash scripts/verify-layout.sh

# 2) Instalar deps
pnpm install

# 3) Typecheck + build de todos os packages
pnpm build

# 4) Build só do frontend (static)
pnpm --filter @workspace/web run build

# 5) Backend Aurora
pip install -r artifacts/aurora/requirements.txt

# 6) Smoke NLP (sem API key)
cd artifacts/aurora
python -c "
from src.core.nl_router import route
for m in [
  'botafogo pb x confiança ao vivo',
  \"nublense x o'higgins ao vivo\",
  'sao bernardo x cuiaba ao vivo',
]:
  r = route(m)
  assert r.intent == 'analyze_match', (m, r.intent)
  print('OK', m, '→', r.entities)
"

# 7) Smoke API (precisa API_FOOTBALL_KEY)
uvicorn main:app --host 0.0.0.0 --port 8080
# outro terminal:
# curl -s http://127.0.0.1:8080/aurora/healthz
```

Secrets:
- `API_FOOTBALL_KEY`

Env frontend (defaults no vite.config):
- `PORT=22333`
- `BASE_PATH=/`

---

## Republish

1. `bash scripts/verify-layout.sh`
2. `pnpm install && pnpm build`
3. Confirme `artifacts/web/dist/public`
4. Confirme `artifacts/aurora/start.sh`
5. **Republish** no Replit
6. Health: `GET /aurora/healthz`
7. Teste: `POST /aurora/copilot` com as 3 mensagens acima — intent deve ser `analyze_match`

## Preciso reenviar arquivos?

- Se o Replit já está ligado a este git/workspace: **não**. Push + Republish basta.
- Se alguém subiu zips / moveu `package.json` / `vite.config` para a raiz: **não reenvie o frontend na raiz**. Restaure o monorepo e rode `verify-layout.sh`.
- Correções de NLP/live entram só em `artifacts/aurora/` (depois `bash scripts/sync-aurora-mirror.sh` se usar o espelho local).
