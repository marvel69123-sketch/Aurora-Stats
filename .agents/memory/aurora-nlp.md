---
name: Aurora NLP architecture
description: Intent detection rules, team alias map, and command-word stripping in copilot_engine.py — easy to break if order changes.
---

## Rule: match_patterns run BEFORE knowledge search

In `detect_intent()`, the `_MATCH_PATTERNS` loop must run before `_KNOWLEDGE_RE`. If knowledge runs first, messages like "me explique Arsenal x Chelsea" route to knowledge_search instead of analyze_match.

**Why:** `_KNOWLEDGE_RE` has a broad `me\s+(?:fale|conte|explique)\s+...` pattern that catches legitimate match requests.

**How to apply:** Order in `detect_intent()`: greeting → help → explain_last → live → bankroll → learning → match_patterns → knowledge → unknown.

## Rule: _clean_team strips command prefix words

`_CMD_PREFIX_RE` removes Portuguese/English command verbs from the start of a captured team name. Without this, "Analisar Arsenal x Chelsea" extracts "Analisar Arsenal" as the home team.

**Why:** The catch-all match pattern `^(.+?)\s+SEP\s+(.+)$` captures everything including the command verb.

**How to apply:** Always call `_clean_team()` on both capture groups from `_MATCH_PATTERNS`.

## Rule: Team aliases in _TEAM_ALIASES dict

Common aliases (PSG, Galo, Man Utd, Brasil, França, etc.) are normalized via `normalize_team_name()` before being sent to API-Football. Always add new aliases here — never rely on API-Football's fuzzy search for Portuguese/abbreviated names.

**Why:** API-Football uses exact/close English name matching; Portuguese names and abbreviations fail silently.

## Rule: Separator regex includes "contra"

`_SEP = r"(?:vs\.?|versus|v\.?(?!\w)|\bx\b|\bcontra\b|\×)"` — "contra" is common in Brazilian Portuguese for football matches (e.g. "Galo contra Flamengo").
