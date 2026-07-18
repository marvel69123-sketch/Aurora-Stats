# Phase 8.4-A.2 — Running commit

## 1) Qual commit está rodando em produção?

| Fonte | Resultado |
|-------|-----------|
| Esperado após Republish | `872bd19` (ou short `872bd19`) — inclui mop via `93a9abc` |
| Observado via `GET /aurora/healthz` → `backend_commit` | **NÃO OBTIDO** — endpoint retorna **500** / TLS falha |
| Observado via resposta Copilot `backend_commit` | **NÃO OBTIDO** — smoke HTTP bloqueado |

### Como o backend reporta commit

`deploy_identity.get_backend_commit()` lê, em ordem:

1. env: `AURORA_BACKEND_COMMIT` / `BACKEND_COMMIT` / `GIT_COMMIT` / `REPLIT_GIT_SHA` / `GITHUB_SHA`
2. `git rev-parse HEAD` no workspace
3. fallback `"unknown"`

Sem healthz 200, **não é possível confirmar** o SHA do processo vivo.

## 4) Após Republish: `backend_commit` mudou?

| Evidência | Interpretação |
|-----------|----------------|
| Commit `872bd19` *Published your App* com Build-Id | Republish **foi disparado** no Replit após mop |
| healthz 500 agora | Runtime **não prova** o novo SHA; pode estar crashando no boot |
| Comparação before/after `backend_commit` | **IMPOSSÍVEL** nesta auditoria (sem leitura bem-sucedida) |

**Conclusão parcial:** o código certo está no Git; a prova de runtime (`backend_commit`) **falhou**.
