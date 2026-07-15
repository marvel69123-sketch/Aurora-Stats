# Aurora — Deploy (procedimento único)

> Infraestrutura apenas. Não altera lógica da Aurora.
> Fonte de verdade do código: **GitHub `main`** (commits feitos por você / Cursor).
> **Não dependa de commits automáticos do Replit Agent** (“Published your App”).

---

## 0) Pré-requisitos

| Ferramenta | Versão |
|------------|--------|
| Node | >= 20 |
| pnpm | >= 9.15 (recomendado 10+) |
| Python | 3.12+ (backend) |
| Git | com bash (Windows: Git for Windows) |

```bash
# Se ainda não tem pnpm:
npm install -g pnpm@10
pnpm -v
```

**Nunca** rode `npm install` na raiz deste monorepo (workspaces + catalog = pnpm).

---

## 1) Estrutura (não inverter)

```
Aurora-Stats/                 ← raiz (package name: workspace)
  package.json
  pnpm-workspace.yaml
  artifacts/web/              ← frontend SoT
  artifacts/aurora/           ← backend SoT (FastAPI)
  artifacts/api-server/       ← artifact.toml → aponta para aurora/
```

Antes de qualquer install/build:

```bash
pnpm run verify:layout
# ou: bash scripts/verify-layout.sh
```

---

## 2) Install (comando correto)

Na **raiz** do monorepo:

```bash
pnpm install
```

Equivalente via script:

```bash
pnpm run install:deps
```

Se `npm install` for executado por engano, o `preinstall` aborta e orienta a usar pnpm.

Backend Python (separado):

```bash
pip install -r artifacts/aurora/requirements.txt
```

Secrets / env:

- `API_FOOTBALL_KEY` (obrigatório para análise real)
- Frontend: `PORT=22333`, `BASE_PATH=/` (defaults no Vite)

---

## 3) Procedimento único de deploy

### Opção A — script único (recomendado)

Na raiz:

```bash
pnpm run deploy
```

Isso faz, nesta ordem:

1. `verify-layout`
2. `pnpm install` (frozen-lockfile, com fallback)
3. build de produção do frontend (`build-web-production.cjs`)
4. imprime checklist de backend + Republish

### Opção B — passos manuais

```bash
cd ~/workspace   # ou pasta local do clone

bash scripts/verify-layout.sh
pnpm install
pnpm run build:web:prod

# Backend smoke (opcional mas recomendado)
pip install -r artifacts/aurora/requirements.txt
cd artifacts/aurora && python tests/smoke_health.py
```

Confirme o build UI:

```bash
cat artifacts/web/dist/public/aurora-ui-build.txt
grep aurora-ui-build artifacts/web/dist/public/index.html
```

---

## 4) Publicar (GitHub → Replit)

1. **Commit e push no GitHub** (você controla o histórico):

   ```bash
   git status
   git add <arquivos>
   git commit -m "…"
   git push origin main
   ```

2. No **Replit Shell** (workspace ligado ao mesmo repo):

   ```bash
   cd ~/workspace
   git pull origin main
   pnpm run deploy        # ou só build:web:prod se deps ok
   ```

3. Clique **Republish** no Replit.

4. Hard refresh no browser: `Ctrl+Shift+R`.

5. Smoke rápido:

   - UI carrega `/`
   - `GET /aurora/healthz` → 200
   - `GET /aurora-ui-build.txt` → id do build atual

---

## 5) Replit: o que usar e o que evitar

| Usar | Evitar |
|------|--------|
| GitHub `main` como SoT | Commits automáticos do Agent (“Published your App”) |
| `pnpm install` / `pnpm run deploy` | `npm install` na raiz |
| Republish após push + build | Esperar que o Agent publique sozinho |
| `artifacts/aurora` + `artifacts/web` | Mover frontend/`package.json` para a raiz |

O hook `[postMerge]` em `.replit` (`scripts/post-merge.sh`) só roda **install** após merge no workspace — **não cria commits**. É opcional e não substitui o fluxo GitHub → push → Republish.

---

## 6) Scripts oficiais (`package.json` raiz)

| Script | Função |
|--------|--------|
| `pnpm install` / `install:deps` | Instalar deps do monorepo |
| `verify:layout` | Auditoria da estrutura |
| `dev:web` | Vite frontend |
| `build:web:prod` | Build UI de produção |
| `build` | Web prod + api-server scaffold |
| `typecheck` | Typecheck monorepo |
| `deploy` / `deploy:build` | Procedimento único de prep de deploy |
| `sync:aurora` | Espelho local opcional `aurora/` |

---

## 7) Troubleshooting

| Problema | Correção |
|----------|----------|
| `Use pnpm instead` / preinstall exit 1 | Rode `pnpm install`, não `npm install` |
| `Unsupported engine … pnpm` | `npm install -g pnpm@10` |
| UI antiga após Republish | Hard refresh; confira `aurora-ui-build.txt` |
| Deploy SIGABRT / pnpm 9 pin | Nunca adicione `"packageManager": "pnpm@9…"` no `package.json` |
| Layout quebrado | `pnpm run verify:layout` e restaure paths oficiais |

---

## 8) Resumo em uma linha

```bash
pnpm install && pnpm run deploy && git push origin main
# → Replit: pull + Republish + hard refresh
```
