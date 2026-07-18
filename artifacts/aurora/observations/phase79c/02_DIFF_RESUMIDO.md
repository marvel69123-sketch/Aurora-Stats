# Fase 7.9-C — Documento 2: Diff Resumido

1. **1ª passagem** `finalize_early_ownership`: GA `kind=general` → **defer** (sem lock)
2. Presence (emotional/HPL/…) pode **claim** via `can_presence_claim`
3. **2ª passagem** `finalize_presence_ownership`: trava EMOTIONAL/META/NRE/… ou GA residual
4. Logs: `[OWNER_BEFORE]` `[OWNER_LOCK]` `[OWNER_AFTER]` `[FINAL_SOURCE]`
5. Overwrite tentada: `[OWNER_AFTER] overwrite_blocked=<layer>`
