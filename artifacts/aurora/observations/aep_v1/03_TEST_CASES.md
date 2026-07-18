# AEP — Test Cases (Phase 1 seed)

## 1) Capabilities

**File:** `tests/evals/capabilities/cases.json`  
**ID:** `cap_001_o_que_voce_faz`

| Step | Input |
|------|-------|
| 1 | `o que você faz?` |

**Expect:** `intent == assistant_capabilities`, `no_loop`

---

## 2) Follow-up markets

**File:** `tests/evals/followups/cases.json`  
**ID:** `fu_001_mercados_after_match`

| Step | Input |
|------|-------|
| 1 | `Argentina x Brasil` |
| 2 | `mercados?` |

**Expect:** `followup_found == true`

---

## 3) Pronoun / fixture reuse

**ID:** `fu_002_e_dele_fixture_reuse`

| Step | Input |
|------|-------|
| 1 | `Argentina x Brasil` |
| 2 | `e dele?` |

**Expect:** `fixture_reused == true`

---

## 4) Invalid fiction

**File:** `tests/evals/football/cases.json`  
**ID:** `fb_001_goku_naruto_invalid`

| Step | Input |
|------|-------|
| 1 | `Goku x Naruto` |

**Expect:** `fixture_quality == INVALID`, `entity_invalid == true`, `no_invented_analysis`

---

## 5) Repair

**File:** `tests/evals/repair/cases.json`  
**ID:** `rp_001_voce_nao_entendeu`

| Step | Input |
|------|-------|
| 1 | `o que você faz?` |
| 2 | `você não entendeu` |

**Expect:** `repair_mode == true`

---

## Reserved categories (empty packs)

- `onboarding/`
- `identity/`
- `partial/`
- `regression/`

Add new cases as JSON objects with `id`, `category`, `steps[]`, `expect{}`.
