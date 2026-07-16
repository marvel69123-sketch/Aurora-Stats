# Aurora Conversation Personalization — índice

**Status:** módulo **congelado** (v3.6.5).

Documentação oficial de proteção e smoke tests:

→ [`FROZEN_CONVERSATION_PERSONALIZATION.md`](./FROZEN_CONVERSATION_PERSONALIZATION.md)

Registro nos módulos protegidos:

→ [`FROZEN_MODULES.md`](./FROZEN_MODULES.md)

## Resumo operacional (não alterar sem sprint aprovada)

- Flag: `conversationPersonalizationEnabled` (`flags.ts`)
- Prefs: `localStorage` → `aurora_conversation_preferences_v1`
- Chrome: emojis / entusiasmo / cabeçalhos (`visualChrome.ts`)
- Técnica: análise completa expandida
- Casual: accordion only (formatter real **não** implementado)
