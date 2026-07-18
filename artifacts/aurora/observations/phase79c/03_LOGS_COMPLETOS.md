# Fase 7.9-C — Documento 3: Logs

Stdout: `smoke_stdout.txt`

## Pride (melhoria)

```text
[OWNER_BEFORE] owner=none … assistant_kind=general
[OWNER_AFTER]  action=defer_ga_general deferred=True
[OWNER_BEFORE] owner=none … emotional=pride
[OWNER_LOCK]   owner=EMOTIONAL locked=True
[OWNER_AFTER]  action=emotional
[FINAL_SOURCE] source=EMOTIONAL owner_final=EMOTIONAL lock_moment=presence_pass
[FINAL_SOURCE] … lock_moment=pre_response
```

## Tags obrigatórias

| Tag | Conteúdo |
|-----|----------|
| OWNER_BEFORE | owner inicial / locked |
| OWNER_LOCK | momento do mark_owner |
| OWNER_AFTER | defer / emotional / keep / overwrite_blocked |
| FINAL_SOURCE | source + owner_final + lock_moment |
