"""
Aurora Architecture — Source of Truth
Generated: 2026-07-12
"""

# Aurora Architecture

## Objetivo

Plataforma estável de **análise esportiva ao vivo** (API-Football + engines Aurora + Copilot NL).

## Fontes de código

| Caminho | Papel |
|---------|--------|
| `artifacts/aurora/` | **SOURCE OF TRUTH + Deploy Replit** (`start.sh` → uvicorn :8080) |
| `aurora/` | Espelho local opcional — `bash scripts/sync-aurora-mirror.sh` (sempre FROM artifacts) |
| `artifacts/aurora_backup_v3/` | Backup legado (não usar) |
| `artifacts/web/` | Frontend React (chat Copilot) — SoT do Vite |
| `artifacts/api-server/` | Scaffold Node; `artifact.toml` aponta o serviço Python para `artifacts/aurora` |

> **Regra:** edite NLP/live/fixture **apenas** em `artifacts/aurora/`. Nunca copie o frontend para a raiz. Nunca use o espelho `aurora/` como origem de deploy.

---

## Fluxo completo (Copilot)

```
POST /aurora/copilot
    │
    ├─ chat_db session + context
    ├─ nl_router.route(message)
    │     → intent + entities {home, away, is_live?}
    │
    ├─ analyze_match
    │     → analyze.analyze_fixture (live sweep FIRST)
    │     → methodology_engine (is_live via fixture_status)
    │     → confidence / market / methodology_v1 / decision_center
    │     → intelligence_engine.generate  ← narrativa live vs pré-jogo
    │     → i18n_pt.translate_report
    │
    ├─ live_opportunities
    │     → live._build_live_response
    │     → live_intelligence_engine.build_live_payload
    │
    └─ bankroll / learning / knowledge / greeting / follow-up / LLM opcional
```

### Regra de ouro (ao vivo)

Se `status.short ∈ {1H, 2H, HT, ET, BT, P, SUSP, INT, LIVE}`:

- `is_live = True`
- **Nunca** gerar "análise pré-jogo"
- Usar placar/minuto/escanteios da API quando disponíveis
- Logs: `intent= status= minute= is_live= pipeline= fixture=`

---

## Entry points

| Arquivo | Uso |
|---------|-----|
| `artifacts/aurora/main.py` | `from src.main import app` (uvicorn `main:app`) |
| `artifacts/aurora/src/main.py` | App FastAPI real |
| `artifacts/aurora/run.sh` | Dev: `uvicorn main:app` :8080 |
| `artifacts/aurora/start.sh` | Prod Replit: `uvicorn main:app` :8080 |
| `artifacts/api-server/.replit-artifact/artifact.toml` | Config de deploy (aponta para artifacts/aurora) |
| `aurora/` | Espelho local apenas |

---

## Routers (`src/routers/`)

| Router | Rotas principais |
|--------|------------------|
| `copilot_unified_router` | `POST /aurora/copilot` — endpoint principal |
| `analyze` | `GET /aurora/analyze` |
| `live` | `GET /aurora/live` |
| `intelligence_router` | `GET /aurora/intelligence` |
| `decision_router` | `GET /aurora/decision`, `/opportunities` |
| `score` / `report` | Score + relatório texto |
| `copilot_router` | `POST /aurora/chat` (legado markdown) |
| `fixtures` / `leagues` / `teams` / `players` / `standings` | Proxy API-Football |
| `brain` / `learning` / `memory` / `knowledge` / `evolution` | Meta / DB |

---

## Engines (`src/core/` → também `src/engines/`)

| Engine | Função |
|--------|--------|
| `fixture_status` | **Fonte única** `is_live` / `minute` |
| `methodology_engine` | Poisson 3 camadas |
| `methodology_v1` | Gate 15 categorias |
| `confidence_engine` | Qualidade de dados |
| `market_engine` | Ranking de mercados |
| `decision_center` | 23 mercados + EV |
| `intelligence_engine` | Narrativa NL (live vs pré-jogo) |
| `live_intelligence_engine` | Ranking de oportunidades ao vivo |
| `nl_router` | Intent NLP |
| `follow_up_engine` | Follow-ups de sessão |
| `conversation_llm` | Camada OpenAI (só narrativa) |
| `i18n_pt` | Tradução PT-BR na borda |

---

## Banco (SQLite `aurora.db`)

| Módulo | Responsabilidade |
|--------|------------------|
| `chat_db` | Sessões, mensagens, `context_json` |
| `memory_db` | Memória de longo prazo |
| `learning_db` | Histórico de previsões / ROI |
| `knowledge_db` | Regras metodológicas |

Aliases: `src/repositories/`

---

## API externa

`src/client.py` → `api_football_get(path, params)`  
Header: `x-apisports-key` (`API_FOOTBALL_KEY`)  
Provider alias: `src/providers/`

---

## Frontend

`artifacts/web` — React + Vite + Tailwind  
`POST ${BASE}/aurora/copilot` via `useChat.ts`

---

## Layout alvo (compatibilidade)

```
aurora/src/
  routers/        # handlers FastAPI
  core/           # engines (legado, ainda canônico)
  engines/        # re-exports claros
  providers/      # API clients
  repositories/   # DBs
  utils/          # helpers
  tests/          # pytest
```

Imports antigos (`from src.core...`) permanecem válidos.

---

## Pipeline ao vivo (detalhe)

1. NLP detecta `"ao vivo"` → strip do nome do time → `entities.is_live=True`
2. `_find_fixture` varre `/fixtures?live=all` primeiro
3. Entre candidatos por ID, **prefere** status live
4. `_map_api_status`: `elapsed` → `minute`
5. `parse_fixture_status` → `meth.is_live`
6. Hard guarantee no copilot: se API live e meth não → força `meth.is_live=True`
7. `_exec_summary` abre com **"currently live"** se `is_live` (mesmo com minute=0)
8. i18n traduz para **"está ao vivo"** — nunca pré-jogo

---

## Custo de API (redução)

- Live sweep primeiro (evita `/teams` + last/next se jogo já está ao vivo)
- Cache 30s em `GET /aurora/live`
- Evitar fan-out desnecessário quando fixture já resolvida no live feed

---

## Deploy Replit

1. Build: `pip install -r artifacts/aurora/requirements.txt`
2. Run: `artifacts/aurora/start.sh` → `uvicorn main:app :8080`
3. Health: `GET /aurora/healthz`
4. Secret obrigatório: `API_FOOTBALL_KEY`
