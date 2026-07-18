# Fase 7.7 — Documento 4: Plano de Correção

**Status: PROPOSTA — NÃO IMPLEMENTAR nesta fase.**

Ordem cirúrgica (evoluir, nunca regredir; evidência primeiro).

---

## Ordem de implementação (quando aprovado)

### 1) Hotfix schema (P0) — anti-crash
- Garantir que **todo** payload que chega em `CopilotResponse` tenha `confidence`, `risk`, `bankroll_recommendation` (helper `ensure_soft_sections`).
- Aplicar no forced nonsport dict e shells de exceção.
- **Não** muda UX de texto; só evita KeyError.

### 2) Quebrar sticky Entendi (P0) — anti-loop
- Variar `reply_general` **ou**
- Em `filter_or_regenerate`, se `similar` e regenerate == mesmo prefixo, usar escape phrase distinta (já existe soft: “Pode falar comigo normalmente…”).
- Early GA: `regenerate` não pode ser o próprio texto idêntico.

### 3) Ownership no forced path (P1)
- Após forced HCE/GA, chamar `finalize_early_ownership` para marcar GA/HCE + `rewrite_locked`.
- Impede late NRF de reescrever turnos já resolvidos.

### 4) MEMORY_QUERY path (P1)
- Não cair em Entendi incompleto: HCE memory handler ou soft payload **completo** com confidence.

### 5) Gap de ownership emocional/social (P1)
- Marcar owner após Emotional/HPL bem-sucedidos (sem novas engines).

### 6) NeverEmpty / IntelFallback (P2)
- Só preencher se realmente vazio; nunca substituir summary com conteúdo útil.

---

## Anti-loop / Recovery Mode — ARQUITETURA (só proposta)

```text
Detectar repetição
  ctx.recent_assistant_replies + prefix similarity ≥ threshold
  OU mesma final_source=fallback N vezes seguidas
        ↓
Detectar frustração
  user rephrase count ↑, correções, "não é isso", curtíssimas irritadas
        ↓
Recovery Mode (não é engine nova — modo no router)
  - bloquear regenerate com mesmo template
  - forçar pergunta de clarificação curta OU retomar last_question HCE
  - log [RECOVERY] mode=on reason=loop|frustration
  - NÃO inventar dados esportivos
```

Critérios de saída do Recovery Mode:
- usuário dá entidade clara (time/confronto) OU confirma clarificação OU muda de tópico.

---

## O que NÃO fazer

- Nova engine  
- Expansão arquitetural  
- Mudança de frontend/UX visual  
- Prompts maiores como “solução”
