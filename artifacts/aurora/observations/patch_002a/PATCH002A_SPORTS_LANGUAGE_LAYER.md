# AURORA-PATCH-002A — Sports Language Layer (SLL)

## Status: IMPLEMENTED

Additive pre-router layer. CSL **not** implemented.

---

## 1. Files changed

| File | Change |
|------|--------|
| `src/conversation/sports_language.py` | SLL core: aliases, compare detect, confidence gate, flag, `[SLL]` logs, HI-safe compact compare rewrite |
| `src/routers/copilot_unified_router.py` | Inject SLL immediately after `raw_user_message` (before memory / MasterIntent / engines) |
| `src/conversation/context_recovery.py` | Skip re-expand when `ctx.sll.applied`; seed nick canons from SLL aliases |
| `src/core/team_aliases.py` | Compact routing aliases (`mancity`, `manutd`, `realmadrid`, …) |
| `tests/test_sports_language_patch002a.py` | New SLL unit tests (flag, confidence, slang, EU) |
| `tests/test_sports_language_patch002.py` | Existing recovery/nickname tests (still green) |

**FROZEN (untouched):** `ownership_stability`, `sport_continuity_guard`, `methodology_engine`, `confidence_engine`, `market_engine`, intelligence/learning engines.

---

## 2. Exact injection point

`copilot_unified_router.py` → `_copilot_inner`, right after:

```python
ctx["raw_user_message"] = message
```

Then:

```python
from src.conversation.sports_language import apply_sports_language_layer
_sll = apply_sports_language_layer(message, ctx)
if _sll.applied and _sll.normalized_text:
    message = _sll.normalized_text
```

Pipeline becomes: **User → SLL → Aurora Router → Engines**.

---

## 3. Examples before / after

| Input | Before (POST-001) | After SLL |
|-------|-------------------|-----------|
| `Mengão ou Verdão?` | `general_chat` + “Entendi…” | `analisar Flamengo x Palmeiras` → sport path |
| `Flu ou Fla?` | GA waffle | `analisar Fluminense x Flamengo` |
| `City ou United?` | GA / broken entity | `analisar ManCity x ManUtd` → home/away Manchester City / United |
| `Galo ou Bahia?` | weak/GA | aliases + recovery pair |
| `Quem está em melhor fase?` | unchanged (no alias → **DO NOTHING**) | `applied=False` |

Metadata stamped on `ctx["sll"]`: `raw_text`, `normalized_text`, `resolved_aliases`, `clubs`, `is_compare`, `ask_kind`, `confidence`, `applied`.

Log shape:

```
[SLL] raw='Mengão ou Verdão?' normalized='analisar Flamengo x Palmeiras' aliases=['Mengão→Flamengo','Verdão→Palmeiras'] ...
```

---

## 4. Regression risks

| Risk | Mitigation |
|------|------------|
| Over-normalize (`real`, `city`, `united` in prose) | Confidence gate (`MIN_APPLY_CONFIDENCE=0.72`); compare/sport cues required for low-trust nicks |
| Double-expand (`Manchester City` → `Manchester Manchester City`) | Skip token if already inside multi-word canon; compact routing tokens not re-expanded |
| HI `_PAIR` only sees single tokens | Compare rewrite uses compact labels (`ManCity`, `ManUtd`, …) |
| OWNER_LOCK rate up slightly (1→3 on EVAL) | Fresh sessions still; sticky lock on some Atlético/Inter cases — out of SLL scope |
| Alias table growth | Additive only in `team_aliases` + SLL map |

---

## 5. Rollback

```bash
# Windows PowerShell
$env:ENABLE_SPORTS_LANGUAGE_LAYER = "0"
# or: false | off | no
```

Default is **ON** (`1`). Flag off → SLL no-ops (`skipped_reason=flag_disabled`), original message passes through unchanged.

---

## 6. Validation (EVAL-001)

| Metric | Baseline (PATCH-001) | After PATCH-002A |
|--------|----------------------|------------------|
| Success rate | **84.5%** | **91.8%** |
| SPORT_REASONING | **12 (10.9%)** | **3 (2.7%)** |
| Entity | 3.6% | 2.7% |
| Owner Lock | 0.9% | 2.7% |
| **HPS** | **76.4** | **83.7** |

HPS = `clamp(SuccessRate − 2·Entity% − OwnerLock%)`.

Unit tests: **28 passed** (`test_sports_language_patch002a` + `patch002` + `entity_safety_patch001`).

Artifacts: `observations/patch_002a/`.

---

## Success criteria

- [x] No overall regressions (success ↑)
- [x] SPORT_REASONING reduced
- [x] Success > 90%
- [x] HPS improved
- [x] Feature flag mandatory
- [x] CSL not implemented
