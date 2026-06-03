---
status: complete
priority: p2
issue_id: "063"
tags: [code-review, encryption, fernet, app-context, run-064]
dependencies: []
---

# P2: Fernet Singleton Requires App Context, Undocumented

## Problem Statement

`get_fernet()` in `app/encryption.py` accesses `current_app.config['PROMPT_ENCRYPTION_KEY']` without guarding against `RuntimeError: Working outside of application context`. Code that calls `encrypt_field()`/`decrypt_field()` outside a request or app context (CLI commands, tests without app context, background tasks) will get an unclear error.

## Findings

- **File:** `app/encryption.py` lines 7-13
- **Impact:** If called outside app context, the error message is "Working outside of application context" with no mention of the encryption module — hard to diagnose
- **Scope:** All 6 model files that import encrypt/decrypt are affected

## Proposed Solution

**Option A (Recommended):** Add clear docstring noting app context requirement

```python
def get_fernet():
    """Get Fernet instance. Cached per process.
    Requires an active Flask application context.
    Raises RuntimeError if called outside an app context.
    """
    global _fernet
    if _fernet is None:
        key = current_app.config['PROMPT_ENCRYPTION_KEY']
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet
```

**Option B:** Accept key directly as parameter (makes testing easier but changes interface)

**Effort:** Trivial (docstring addition)
**Risk:** None

## Acceptance Criteria

- [ ] `get_fernet()` has docstring noting app context requirement
- [ ] `encrypt_field()` and `decrypt_field()` have docstrings noting app context requirement

## Work Log

- 2026-06-02: Found during Run 064 tail review.
