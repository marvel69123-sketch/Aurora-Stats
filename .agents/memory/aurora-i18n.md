---
name: Aurora Portuguese i18n (presentation layer)
description: How Aurora's copilot output is translated to Brazilian PT at the boundary, and two non-obvious traps.
---

# Aurora i18n — output-boundary translation only

Aurora translates ALL user-facing `/aurora/copilot` text to Brazilian Portuguese at the presentation
boundary only (`i18n_pt.py`), wired via `translate_report(payload)` in `copilot_unified_router.py`
after the LLM block. Calculation engines and numeric fields are never touched.

## Trap 1 — translate_text() pass order & case-sensitivity
`translate_text()` runs 4 passes; ORDER AND CASE MATTER:
1. regex sentence-frame PATTERNS
2. literal multi-word PHRASES (case-INSENSITIVE, longest-first)
3. embedded category/market DISPLAY labels (case-SENSITIVE, `\b` boundaries)
4. standalone WORDS

**Why:** the earlier version ran embedded labels FIRST with IGNORECASE. That pre-mutated substrings
inside full-sentence reasons before the phrase pass could match them, and even uppercased lowercase
prose (e.g. `methodology` → `METODOLOGIA`). Phrases-before-embedded + case-sensitive embedded fixes
bankroll reasoning, venue, no-standings, and tactical-style leaks.
**How to apply:** if a full-sentence translation "half-applies" or a word gets wrongly capitalized,
suspect an earlier pass mutating the substring. Keep phrases before embedded; keep embedded case-sensitive.

## Trap 2 — knowledge_db descriptions must NOT be translated in the DB
`knowledge_engine.consult()` red-flag triggers match ENGLISH substrings (e.g. `referee`, `confidence`,
`expected goal`) against the raw DB description. Translating the DB would break triggering.
**Fix used:** translate in `KnowledgeContext.to_notes()` on title+description BEFORE truncation
(`[:120]` golden / `[:100]` relevant), so the visible prefix is clean PT while `consult()` keeps using
raw English. `translate_report` re-running on already-translated notes is effectively idempotent (matching
is English-oriented), so double-translation is harmless.

## Intentional loanwords (do NOT "fix" to PT)
stake, drawdown, momentum, odds, EV/VE, BTTS, xG, Poisson, Kelly, and the product name
"Aurora Evolution Engine" are standard Brazilian betting jargon — leaving them is correct.

## Snake_case leak source
Confidence explanation prose comes from `intelligence_engine._confidence_explanation`, which does
`_CATEGORY_LABELS.get(k, k)` — methodology_v1 keys absent from that map (value_bet_detection,
cards_pattern, corners_pattern, referee_influence, tactical_style, historical_learning) fall back to
the raw snake_case key. These are mapped as phrases in `i18n_pt.py` TEXT_TRANSLATIONS.
