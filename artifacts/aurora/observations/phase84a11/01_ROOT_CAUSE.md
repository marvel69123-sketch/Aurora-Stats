# 8.4-A.11 — Root Cause

## Symptom (Simulator)

Persona `advanced`: **0/21 PASS**, 43 loops overall.
After a real fixture, short asks like `xg?` / `pressão?` / `kelly?` fell into:

```
intent=general_chat
Entendi. Posso te ajudar com isso de forma direta…
```

## Why

1. Continuity 8.4-A.8 only claimed `mercados?` / `placar?` / … — not analytics vocabulary.
2. Pronoun layer 8.4-A.10 only claimed `e dele?` / `e o outro?`.
3. Advanced terms had **active fixture** in session (`last_match`) but no pre-GA claim → GA loop.

## Fix

**Advanced Football Continuity** — detect advanced terms when fixture context exists, claim before GA/fallback, reuse fixture without inventing xG/odds/stake numbers.
