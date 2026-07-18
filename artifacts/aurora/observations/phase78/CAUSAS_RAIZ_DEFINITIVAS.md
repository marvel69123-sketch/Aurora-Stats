# Fase 7.8 — Lista Definitiva de Causas Raiz

Status: EVIDÊNCIA COLETADA (sem correção)  
Fonte: `evidence_latest.json` + `REPORT_LATEST.md` + `run_stdout.txt`

---

## Vereditos

| Hipótese | Veredito | Confiança |
|----------|----------|-----------|
| **H1** NRF reproduz “Entendi…” | **CONFIRMADA** | Alta (27 hits) |
| **H2** Forced payload sem `confidence` | **CONFIRMADA** (estrutural) | Alta |
| **H3** Ownership perdido no early stack | **REFUTADA parcialmente** | — |
| **H3b** Gap de ownership (forced / timing) | **CONFIRMADA** | Alta |

---

## Causas raiz definitivas

### CR1 — Sticky template via early NRF (P0)
`GENERAL_CHAT` → `reply_general` → early `filter_or_regenerate(regenerate=mesmo_texto)`.  
No turno 2+: `similar=True` → `action=regenerate` → `same_as_regen=True` → `entendi_out=True`.

**Prova:** `[NRF_OUTPUT] action=regenerate similar=True same_as_regen=True entendi_out=True`

### CR2 — Forced nonsport omite seções obrigatórias (P0)
Dict inline do router **não inclui** `confidence` / `risk` / `bankroll_recommendation`.  
Consumidor: `ConfidenceSection(**payload["confidence"])` → `KeyError: 'confidence'`.

**Prova estática:** keys forced = intent, entities, summaries, markets, match, is_live, brain — **sem confidence**.  
GA completo **tem** confidence.

### CR3 — Loop ocorre ANTES do ownership lock (P0 timing)
Early NRF roda **antes** de `finalize_early_ownership`.  
Late NRF é `skipped_owned` quando `owner=GA locked=True` — então o late path **não** é o loop principal no early stack saudável.

### CR4 — Forced path sem `finalize_early_ownership` (P1 gap)
Quando payload cai no dict incompleto, não há owner/lock → late NRF pode correr + crash de schema.

### CR5 — Misroteamento de intent (P1, evidência extra)
| Mensagem | Intent observado | Esperado |
|----------|------------------|----------|
| `quais jogos estão ao vivo?` | GENERAL_CHAT → Entendi | LIVE/SPORT |
| `que horas são?` | SPORT_QUERY (stub) | utility / general time |

Isso explica inteligência percebida baixa mesmo sem crash.

---

## O que NÃO é causa raiz (nesta corrida)

- Perda de owner GA→none no early stack (não observada; owner permanece GA+locked)
- Necessidade de nova engine
- Frontend
