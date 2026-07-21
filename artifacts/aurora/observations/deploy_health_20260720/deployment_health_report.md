# Deployment Health Report — 2026-07-20

## Verdict (PASSO 5)

| # | Pergunta | Resposta |
|---|----------|----------|
| 1 | Deploy saudável? | **NÃO** |
| 2 | Serviço está respondendo? | **NÃO** (host principal TLS/edge falha; aliases 404) |
| 3 | Existe regressão? | **SIM** (código SoT: `Query.strip` em `analyze_match`; prod: Autoscale não serve) |
| 4 | Existe risco de produção? | **SIM** — app inacessível + path analyze quebrado no SoT pré-fix |
| 5 | Correção mínima necessária | **Republish Autoscale** + patch `Query` leak (já aplicado localmente) |

---

## PASSO 1 — Identidade & liveness

| Campo | Valor |
|-------|--------|
| Commit local (`HEAD`) | `b984c48` — `feat(aurora): route real sport asks into SPORT pipeline (P2.5-S)` |
| Commit publicado GitHub (`origin/main`) | `b984c48` (igual ao local) |
| Último marker Replit “Published your App” no git | `b30ec32` (**antes** de P2.5-S) |
| Autoscale target | Replit `deploymentTarget = "autoscale"` (`.replit`) |
| Health path | `GET /aurora/healthz` (`artifact.toml` startup probe) |

### Probes produção

| Host | Resultado |
|------|-----------|
| `https://aurora-stats.marvel69123-sketch.replit.app/aurora/healthz` | TLS/connection closed (local); WebFetch **500** sem body JSON de app |
| mesmo host `/` e `/docs` | TLS fail / edge 500 |
| `aurora-stats-marvel69123-sketch.replit.app` | **404** “isn't live yet” |
| `marvel69123-sketch-aurora-stats.replit.app` | **404** “isn't live yet” |
| `backend_commit` em prod | **ilegível** (healthz não responde) |

### Local (SoT)

| Check | Resultado |
|-------|-----------|
| `TestClient` `/aurora/healthz` | **200** `status=ok` `backend_commit=b984c48` |
| Startup contract | healthz não toca sport/API-Football; fail-open em brain/identity |

**Conclusão P1:** SoT Git saudável; **deploy Autoscale não está saudável / não publica commit legível**.

---

## PASSO 2 — Logs (últimos evidência disponíveis)

Produção: logs Replit **inacessíveis** desta máquina (sem MCP/CLI Replit).  
Corpus: 36 arquivos locais + smoke live TestClient → `deploy_health_20260720/`.

### Classificação

| Classe | Itens |
|--------|-------|
| **fatal** | `AttributeError: 'Query' object has no attribute 'strip'` em `cost_protection.begin_request` via `analyze_fixture` (pré-fix) |
| **degradation** | API-Football 429/rateLimit (~979 hits históricos); `API_FOOTBALL_KEY not configured` fail-open; fixture miss → 404 user-facing; Intelligence/Web fallback |
| **harmless** | AUDIT `OWNER_*` / `pipeline_trace` em WARNING; uvicorn local WinError; smoke script `NameError` |

Namespaces pedidos (`src.conversation.*`, `src.routers.*`, `aurora.pipeline_trace`): **0 ERROR**; WARNs majoritariamente audit.

Detalhes: `warning_analysis.json`, `runtime_errors.json`.

---

## PASSO 3 — Padrões sistêmicos

| Pergunta | Achado |
|----------|--------|
| Exceção repetitiva? | **SIM (local SoT pré-fix)** — `Query.strip` em todo `analyze_match` via chamada interna a `analyze_fixture` |
| Loop de warning? | **SIM (audit)** — `OWNER_AFTER owner=SPORT` ×54 etc.; não é retry storm |
| Exception swallowing? | **SIM** — `except Exception: pass` em `sport_understanding` / stamps `dialog_mode` (fail-open) |
| Fallback excessivo pós P2.5-S? | **POSSÍVEL/PRESENTE no path analyze** — force `analyze_match` sem `home`/`away` → Inference V2 / fallback; com entities OK ainda batia no crash Query |

---

## PASSO 4 — `dialog_mode=SPORT` (P2.5-S)

| Risco | Status |
|-------|--------|
| Recursion (call stack) | **ABSENT** |
| Repeated routing | **POSSIBLE** (gates redundantes, não loop) |
| Fixture misses | **PRESENT** (enrich não seta home/away; mismatch club lists) |
| Excessive fallback | **PRESENT** quando intent vira `analyze_match` sem fixture |
| Quebra `/aurora/healthz`? | **NÃO** — sport é lazy no request path |

Validação P2.5-S (routing): `sports_understanding_validation.json` — **PASS** (5/5 SPORT).

---

## Correção mínima (aplicada no working tree)

1. **Código:** unwrap `Query` defaults em `analyze_fixture` + `_coerce_user_id` em `cost_protection`  
   → elimina `Query.strip`; pós-fix smoke: `HAS_QUERY_STRIP_ERR=False` (resta 404 sem API key = degradation esperada).
2. **Ops (obrigatório):** no Replit — `git pull` + `pnpm run deploy` + **Republish**; confirmar `GET /aurora/healthz` → 200 com `backend_commit` ≥ patch.

Arquivos: `minimal_fix.patch`, `root_cause.md`.
