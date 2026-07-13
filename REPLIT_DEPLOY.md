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

# 3) Typecheck + build de produção (apaga dist antigo e valida UI nova)
pnpm build
# equivalente frontend:
# bash scripts/build-web-production.sh

# 4) Confirme o shell servido
grep aurora-ui-build artifacts/web/dist/public/index.html
cat artifacts/web/dist/public/aurora-ui-build.txt
# NÃO deve conter "Analisar uma partida" no JS:
! grep -R "Analisar uma partida" artifacts/web/dist/public/assets || echo "OK sem UI legada"

# 5) Backend Aurora
pip install -r artifacts/aurora/requirements.txt

# Smoke (sem porta):
cd artifacts/aurora && python tests/smoke_health.py
# Esperado: SMOKE OK — /aurora/healthz /docs /redoc /openapi.json = 200

# 6) Smoke API ao vivo
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1
# curl http://127.0.0.1:8080/aurora/healthz
# curl -I http://127.0.0.1:8080/docs

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

## Republish (obrigatório para UI)

O source no Git **não** publica sozinho o frontend. Replit serve
`artifacts/web/dist/public` gerado no build de produção.

1. Push deste commit
2. No Replit Shell:

```bash
cd ~/workspace
bash scripts/verify-layout.sh
bash scripts/build-web-production.sh
cat artifacts/web/dist/public/aurora-ui-build.txt
grep aurora-ui-build artifacts/web/dist/public/index.html
```

3. Clique **Republish**
4. Hard refresh no browser (`Ctrl+Shift+R`)
5. Confirme:
   - empty state: título **Aurora** + "Como posso ajudar nas análises de hoje?"
   - sidebar: **Personalizar avatar**
   - `GET /aurora-ui-build.txt` retorna `chatgpt-...`
   - View Source: `<meta name="aurora-ui" content="chatgpt-v2" />`

Se ainda aparecer "Analisar uma partida" / "Oportunidades ao vivo", o browser
ou o CDN ainda está com o shell antigo — o bundle novo **não** contém essas strings.

## Preciso reenviar arquivos?

- Se o Replit já está ligado a este git/workspace: **não**. Push + Republish basta.
- Se alguém subiu zips / moveu `package.json` / `vite.config` para a raiz: **não reenvie o frontend na raiz**. Restaure o monorepo e rode `verify-layout.sh`.
- Correções de NLP/live entram só em `artifacts/aurora/` (depois `bash scripts/sync-aurora-mirror.sh` se usar o espelho local).
