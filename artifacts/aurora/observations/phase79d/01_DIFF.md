# Fase 7.9-D — Documento 1: Diff

## `turn_ownership.py`
- `finalize_forced_ownership()` — marca `forced_nonsport`, pass=`forced`, lock imediato
- GA `general` com pass `forced` **não defere** (trava na hora)
- Logs: `[FORCED_OWNER]` `[FORCED_LOCK]` + `[FINAL_SOURCE] lock_moment=forced_path`

## `copilot_unified_router.py`
- Após montar payload do forced nonsport → `finalize_forced_ownership(payload)`
- Sem mudança de texto / intents / NRF / fallback content

## Testes
- `tests/test_forced_ownership_79d.py`
- `scripts/phase79d_p1_1_smoke.py`
