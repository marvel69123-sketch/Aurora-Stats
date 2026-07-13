# Aurora Audit Report

**Data:** 2026-07-12  
**Backup:** `backups/aurora_backup_20260712_170805`  
**Objetivo:** Estabilizar análises ao vivo e preparar crescimento sem novos bugs.

---

## Resumo executivo

O bug **"First Half + análise pré-jogo"** tinha três causas encadeadas:

1. `intelligence_engine` exigia `is_live AND minute` (truthy) — minute `0` ou falsy gerava texto pré-jogo.
2. `nl_router` em `aurora/` **não** stripava `"ao vivo"` do nome do time visitante.
3. `_find_fixture` / `_name_match` falhavam no live sweep com nomes corrompidos e podiam devolver fixture NS em vez de 1H.

Todas foram corrigidas em `aurora/` e sincronizadas para `artifacts/aurora/` (deploy Replit).

---

## Bugs encontrados

| # | Severidade | Local | Problema |
|---|------------|-------|----------|
| 1 | **CRÍTICO** | `intelligence_engine.py:_exec_summary` | `if is_live and minute:` → pré-jogo com 1H/minute=0 |
| 2 | **CRÍTICO** | `nl_router.py` (aurora/) | Sem `_LIVE_SUFFIX_RE` → `"Cuiaba Ao Vivo"` |
| 3 | **ALTO** | `analyze.py:_name_match` | Substring estrita; não casa `"cuiaba ao vivo"` com `"Cuiabá"` |
| 4 | **ALTO** | `analyze.py:_find_fixture` | Primeiro match por ID (pode ser NS futuro) |
| 5 | **MÉDIO** | `intelligence_engine` / `decision_engine` | `minute if minute else None` descarta 0 |
| 6 | **MÉDIO** | `copilot_unified_router` | Ignorava `entities.is_live` |
| 7 | **MÉDIO** | `i18n_pt.py` | Sem padrão para live sem minuto |
| 8 | **BAIXO** | `artifacts/aurora/start.sh` | Path absoluto `/home/runner/...` frágil |
| 9 | **BAIXO** | Duplicação `aurora/` vs `artifacts/aurora/` | Drift de código (deploy desatualizado) |
| 10 | **INFO** | `copilot_router` vs `copilot_unified` | Dois endpoints; legado markdown permanece |
| 11 | **INFO** | Python local Windows | Sem interpretador real — testes não rodaram nesta máquina |

---

## Bugs corrigidos

### 1. Narrativa live vs pré-jogo
- Gate alterado para **`if is_live:`** (minuto opcional).
- Minute 0 / None em jogo live → "currently live", nunca "pre-match analysis".
- i18n: novo padrão → "está ao vivo, com o placar em …".

### 2. NLP `"ao vivo"`
- `_LIVE_SUFFIX_RE` / `_LIVE_PREFIX_RE` adicionados em `aurora/src/core/nl_router.py`.
- Entities incluem `is_live=True` quando o marcador é detectado.
- Away deixa de ser `"Cuiaba Ao Vivo"`.

### 3. Descoberta de fixture
- `_name_match` com fallback por palavras (>2 chars).
- Preferência por candidatos com `status.short ∈ LIVE_STATUSES`.
- Aceita home/away invertidos.
- Logs estruturados no lookup.

### 4. Hard guarantee no Copilot
- Se API diz live e `meth.is_live` é False → força `True` antes do intelligence engine.
- Payload final usa `final_is_live = report.is_live or api_is_live`.
- `prefer_live` propagado de entities → `analyze_fixture`.

### 5. Fixture status canônico
- `.upper()` em `short`.
- `fixture_minute` preserva `0` (não colapsa para None indevidamente).
- Aceita fallback `elapsed` se necessário.

### 6. Deploy
- `aurora/run.sh`, `aurora/start.sh`, `aurora/requirements.txt` criados.
- `artifacts/aurora/start.sh` tornado **path-relative** (Republish-safe).

### 7. Logs (Fase 7)
Formato padronizado:
```
intent=analyze_match fixture=São Bernardo vs Cuiabá status=1H minute=37 is_live=True pipeline=intelligence_engine
```

---

## Arquitetura final

Ver **[AURORA_ARCHITECTURE.md](./AURORA_ARCHITECTURE.md)**.

Camadas de compatibilidade adicionadas (sem quebrar imports):

```
aurora/src/
  routers/       # handlers
  core/          # engines canônicos
  engines/       # re-exports
  providers/     # API client alias
  repositories/  # DB aliases
  utils/         # helpers
tests/           # pytest
```

**Deploy canônico:** `artifacts/aurora/` via `artifact.toml` → `start.sh` → `uvicorn main:app :8080`.

---

## Arquivos modificados (diff principal)

| Arquivo | Mudança |
|---------|---------|
| `aurora/src/core/fixture_status.py` | Live detection robusta |
| `aurora/src/core/intelligence_engine.py` | Opening live sem exigir minute |
| `aurora/src/core/nl_router.py` | Strip ao vivo + entity is_live |
| `aurora/src/core/i18n_pt.py` | Tradução live sem minuto |
| `aurora/src/core/decision_engine.py` | Minute 0 preservado |
| `aurora/src/routers/analyze.py` | Name match + prefer live |
| `aurora/src/routers/copilot_unified_router.py` | prefer_live + hard guarantee + logs |
| `artifacts/aurora/...` (mesmos críticos) | Sync deploy |
| `artifacts/aurora/start.sh` | Path-relative |
| `aurora/run.sh`, `start.sh`, `requirements.txt` | Deploy local |
| `aurora/tests/*` | Testes automáticos |
| `AURORA_ARCHITECTURE.md` | Mapa completo |
| `AURORA_AUDIT_REPORT.md` | Este relatório |

---

## Arquivos / código morto (identificado, não removido em massa)

Remoção agressiva foi evitada para não quebrar o deploy Replit.

| Item | Motivo de manter |
|------|------------------|
| `artifacts/aurora_backup_v3/` | Backup histórico |
| `copilot_router.py` (`/chat`) | Clientes legados |
| `copilot_engine.detect_intent` | Usado por `/chat` |
| `GET /fixtures/live` + `GET /live` | Formatos diferentes |

**Próximo passo seguro:** deprecar `/chat` após migrar o frontend 100% para `/copilot`.

---

## Melhorias realizadas

1. Pipeline ao vivo corrigido ponta a ponta (NLP → fixture → meth → narrativa → i18n).
2. Logs estruturados para debug de produção.
3. Testes de regressão (live, NLP, engines).
4. Scripts de deploy portáveis.
5. Camada de pacotes (`engines/`, `providers/`, `repositories/`) sem big-bang de imports.
6. Backup completo antes das mudanças.
7. Documentação de arquitetura e auditoria.

---

## Testes

```bash
cd aurora
pip install -r requirements.txt
python -m pytest tests/ -v

cd ../artifacts/aurora
python -m pytest tests/ -v
```

Casos cobertos:
- Status 1H/2H/HT/… → `is_live=True`
- `"analise sao bernardo x cuiaba ao vivo"` → entities limpas + `is_live`
- Opening live nunca contém "pre-match"
- i18n nunca traduz live para "pré-jogo"
- Live intelligence scoring / follow-up / intents básicos

> Nesta máquina Windows não há Python real (só stub da Store). Rodar os testes no Replit ou com Python 3.12 instalado.

---

## Próximos passos

1. **Republish no Replit** e validar: `"analise sao bernardo x cuiaba ao vivo"` com jogo em 1H.
2. Confirmar logs: `is_live=True`, `pipeline=intelligence_engine`, sem "pré-jogo".
3. Unificar `aurora/` ↔ `artifacts/aurora/` (script de sync ou single source).
4. Reduzir custo API: cache de team IDs; evitar last+next quando live hit.
5. Deprecar `POST /aurora/chat` após migração total.
6. Mover fisicamente `core/` → `engines/` quando o sync único estiver estável.
7. Adicionar testes de integração com mock httpx da API-Football.

---

## Verificação manual recomendada

```
analise sao bernardo x cuiaba ao vivo
```

Esperado:
- `intent=analyze_match`
- `status=1H` (ou 2H/HT…)
- `is_live=True`
- `minute` preenchido pela API
- Resumo em PT com **"ao vivo"** / placar — **sem** "análise pré-jogo"
- Sem pedir placar/minuto/escanteios se a API já enviou

---

## Conclusão

A Aurora está corrigida no caminho crítico de análise ao vivo e sincronizada com o artefato de deploy. A arquitetura está documentada, com logs, testes e backup. O próximo risco principal é o **drift** entre `aurora/` e `artifacts/aurora/` — tratar como prioridade operacional após o Republish.
