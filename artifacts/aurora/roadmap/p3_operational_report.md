# P3-A — Operational Intelligence Report

**Date:** 2026-07-20  
**Status:** **INSTRUMENTATION SHIPPED · LIVE DENSITY BLOCKED (no API key)**  
**Mode:** `soft_no_key`  
**Corpus:** 30 real named pairs (BR / EPL / La Liga / Serie A / Bundesliga / Ligue 1 / International / fiction controls)  
**Freeze:** P0 · P1 · P2.5 · P2b Gateway/Cache/NMB/DRS/Waves **not modified**

---

## Executive verdict

P3-A delivered the **ops collector + real corpus harness**.  
This environment has **no `API_FOOTBALL_KEY`**, so the live density numbers below measure the **auth/config failure mode** (soft-miss dominated), **not** league coverage quality.

**Thin Premium GO cannot be certified until the corpus is re-run with a live key.**

---

## Mandatory metrics (this run)

| Metric | Value | Interpretation |
|--------|------:|----------------|
| resolve_rate | **0.0** | No fixture_id — API key absent |
| t3_t4_live_rate | **0.0** | All T0 |
| pct_drs_ge_60 | **0.0** | mean DRS = 5.0 |
| premium_fixture_rate | **0.0** | No premium bundles |
| soft_miss_rate | **1.0** | Expected without provider |
| narrative_usage_rate | 1.0 | Partial honesty narrative still stamps |
| calendar_empty_rate | 1.0 | No kickoff calendar without resolve |
| provider_health | **not_configured** | Limiting factor = `API_FOOTBALL_KEY` |
| provider_failure_rate | n/a | 0 probed network calls (fetcher never reached) |
| provider_latency | n/a | — |

DRS live distribution: `{T0: 30}`

---

## Answers to objective questions

### 1. Qual o resolve_rate real?
**0.0** neste ambiente (key ausente). Valor **não é** a taxa de resolve de produção — é o piso de falha de configuração.

### 2. Qual o % de fixtures em T3/T4?
**0.0%** neste run.

### 3. Qual o % de DRS ≥ 60?
**0.0%** neste run.

### 4. Qual o premium_fixture_rate?
**0.0** neste run.

### 5. Quais providers estão limitando cobertura?
**api-football** — bloqueado por **credencial não configurada** (`API_FOOTBALL_KEY`). Não há evidência desta corrida sobre rate-limit 429 ou gaps por liga.

---

## Criteria answers

### 1. Aurora já possui densidade suficiente para Thin Premium?
**NO (neste ambiente).**  
Instrumentação pronta; densidade live **não certificável** sem key.  
Re-rodar com key; Thin Premium GO só se `resolve_rate ≥ 0.50` e `pct_drs_ge_60 ≥ 0.35` (alvo charter ≥ 0.50).

### 2. Quais ligas possuem baixa cobertura?
**Indeterminado com key ausente** — todas as hints (BR Serie A, EPL, La Liga, …) colapsaram para soft partial igualmente.  
Após re-run com API, usar `live_density_metrics.json → by_league` ordenado por `t3_t4_rate` / `resolve_rate`.

### 3. Qual é o novo teto operacional?
```text
operational_ceiling ≈ min(API_access, resolve_rate, provider_path_health, signal_fill)
```
Neste host o teto é **API_access (key)**. Com key saudável, o teto volta a ser **resolve × secondary signal density** (P2b closure).

### 4. Quais sinais estão limitando T3/T4?
Neste run: **fixture** (não resolve) → cascata em statistics / xG / events / odds / lineups.  
Com key, esperar ranking em `signals_limiting_t3_t4` (tipicamente xG/odds/lineups em fixtures resolvidos).

---

## What shipped (observability only)

| Piece | Path |
|-------|------|
| Collector | `src/ops/live_density.py` |
| Analyze stamp | soft-miss + success paths (record only) |
| Real corpus runner | `roadmap/scripts/run_p3a_operational_corpus.py` |
| Unit tests | `tests/test_p3a_live_density_ops.py` (3 passed) |

**Not modified:** ownership/continuity/ambiguous/fiction guards · Gateway · Cache · NMB · DRS · Wave modules.

---

## Recommendations

1. **Set `API_FOOTBALL_KEY` and re-run**  
   `python roadmap/scripts/run_p3a_operational_corpus.py`  
2. Publish refreshed `live_density_metrics.json` / provider / premium reports from that run.  
3. Gate Thin Premium on live `pct_drs_ge_60 ≥ 0.50` for covered leagues.  
4. Keep production stamp (`record_analyze_sample`) for continuous SLOs.  
5. Do **not** treat this soft_no_key run as evidence against P2b architecture — it only proves ops instrumentation + config dependency.

---

## Artifacts

- `roadmap/live_density_metrics.json`
- `roadmap/provider_health_report.json`
- `roadmap/premium_fixture_report.json`
- `roadmap/p3_operational_report.md`

## How to certify (operator)

```text
$env:API_FOOTBALL_KEY = "<key>"
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe roadmap\scripts\run_p3a_operational_corpus.py
```
