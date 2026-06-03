---
status: complete
priority: p1
issue_id: "062"
tags: [code-review, encryption, fernet, industry-guidance, run-064]
dependencies: []
---

# P1: Industry Guidance Wrongly Encrypted (Non-Encrypted Field)

## Problem Statement

`app/models/industry_models.py` imports and applies `encrypt_field`/`decrypt_field` to `industry_guidance.guidance_text`. This field is NOT in the spec's encrypted-fields list. It stores admin-authored, non-PII guidance text. If seed data exists as plaintext, `decrypt_field()` on those rows will raise `cryptography.fernet.InvalidToken`, crashing the guidance admin pages.

## Findings

- **File:** `app/models/industry_models.py` lines 1-3 (imports), line 41-43 (`save_guidance`), lines 28-34 (`get_guidance_for_industry`)
- **Spec:** Only `prompt_components.content`, `template_components.content`, `prompt_grades.worked_well/needs_improvement/notes` are encrypted
- **Impact:** Admin `/admin/guidance` page crashes on load if seed data exists as plaintext (seed script stores guidance without encryption)

## Proposed Solution

**Option A (Recommended):** Remove encryption from industry_models.py

```python
# Before
from app.encryption import encrypt_field, decrypt_field

def save_guidance(conn, industry_id, component_id, guidance_text):
    encrypted = encrypt_field(guidance_text)
    conn.execute(
        '''INSERT INTO industry_guidance ... VALUES (?, ?, ?)''',
        (industry_id, component_id, encrypted)
    )

def get_guidance_for_industry(conn, industry_id):
    rows = conn.execute(...).fetchall()
    return [{'component_id': r['component_id'],
             'guidance_text': decrypt_field(r['guidance_text'])} for r in rows]

# After
# Remove the import entirely
def save_guidance(conn, industry_id, component_id, guidance_text):
    conn.execute(
        '''INSERT INTO industry_guidance ... VALUES (?, ?, ?)''',
        (industry_id, component_id, guidance_text)
    )

def get_guidance_for_industry(conn, industry_id):
    rows = conn.execute(...).fetchall()
    return [{'component_id': r['component_id'],
             'guidance_text': r['guidance_text']} for r in rows]
```

**Effort:** Small (3-4 line change)
**Risk:** Low — removes incorrect behavior
**Test:** Admin guidance page loads without crash; save/edit guidance persists correctly

## Acceptance Criteria

- [ ] `industry_models.py` does not import `encrypt_field` or `decrypt_field`
- [ ] `save_guidance` stores guidance_text as plaintext
- [ ] `get_guidance_for_industry` returns guidance_text as plaintext (no decrypt)
- [ ] Admin guidance page loads without `InvalidToken` exception

## Work Log

- 2026-06-02: Found during Run 064 tail review. FC2 over-application of neighboring encryption pattern.
