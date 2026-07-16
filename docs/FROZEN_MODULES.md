# Aurora — Módulos Congelados (oficial)

Documento de registro dos módulos **protegidos**.  
Alterações exigem aprovação explícita + checklist anti-regressão.  
Falha no protocolo pré-merge → **ABORTAR MERGE**.

---

## Módulos congelados

| Módulo | Escopo | Doc detalhada |
|---|---|---|
| Integrity Guard / PARTIAL / Resolver | Backend fixture quality | — |
| MatchHeader | FE match identity / logos / live header | — |
| Premium Live | Live refresh, stats, momentum, featured live markets | — |
| Mercado em destaque | FE featured market block (dados do payload) | — |
| Estatísticas ao vivo / Momentum | FE live panels | — |
| Decision Center / Market / Confidence / Methodology / Learning / Knowledge engines | Backend intelligence | — |
| FollowUp Engine | Backend conversation follow-ups | — |
| Analyze / payloads | Backend analyze contracts | — |
| **Conversation Personalization System (v3.6.x)** | FE gear, prefs, chrome, Técnica/Casual layout | [`FROZEN_CONVERSATION_PERSONALIZATION.md`](./FROZEN_CONVERSATION_PERSONALIZATION.md) |

---

## Conversation Personalization System (v3.6.x)

**Congelado em v3.6.5.**

Inclui: engrenagem, modal, `localStorage`, multi-abas, emojis, entusiasmo, cabeçalhos, Aurora Técnica expandida, Casual com accordion (sem Casual real), fallback seguro, feature flag.

Detalhes, smoke tests e protocolo:  
→ [`docs/FROZEN_CONVERSATION_PERSONALIZATION.md`](./FROZEN_CONVERSATION_PERSONALIZATION.md)

---

## Protocolo pré-merge (mínimo)

Antes de merge em `main`, confirmar intactos:

1. MatchHeader  
2. Premium Live  
3. Resolver  
4. Estatísticas  
5. FollowUp  
6. Small Talk  
7. Conversation Personalization  

Se qualquer item falhar → **ABORTAR MERGE**.

Smoke FE sugerido:

```bash
cd artifacts/web && npm run typecheck
cd artifacts/aurora && python -m pytest tests/test_fixture_integrity.py -q
```

---

## Regras sagradas

1. Nunca regredir.  
2. Sempre evoluir de forma aditiva.  
3. Não mexer no que está bom.  
4. Personalização nunca altera inteligência.  
5. Módulos congelados têm prioridade máxima de proteção.
