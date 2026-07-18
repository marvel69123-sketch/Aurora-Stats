# Fase 7.9-C — Documento 1: Diff

## `turn_ownership.py`
- Logs: `[OWNER_BEFORE]` `[OWNER_LOCK]` `[OWNER_AFTER]`
- **Defer** hard lock para GA `assistant_kind=general`
- `can_presence_claim()` — emotional/HPL/profile podem reivindicar deferred GA
- `finalize_presence_ownership()` — 2ª passagem após presence (trava GA se ninguém reivindicou)
- Prioridade: EMOTIONAL → HPL/social → recovery → NRE → META/HCE → GA

## `copilot_unified_router.py` (só ponto de aplicação do lock)
- Emotional / profile / HPL / natural / intel / smalltalk: gate `can_presence_claim`
- Após presence stack: `finalize_presence_ownership(payload)`
- **Não** altera forced nonsport ownership

## Não alterados
NRF, fallback forced, intents, GeneralAssistant, emotional_presence.py, frontend
