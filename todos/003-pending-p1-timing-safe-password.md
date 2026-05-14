---
status: resolved
priority: p1
issue_id: "003"
tags: [code-review, security]
---

# Timing-Vulnerable Admin Password Comparison

## Problem Statement
Both Flask and Express compare the admin password using standard `!=`/`!==` operators which short-circuit on first mismatched byte, enabling timing side-channel attacks.

- Python: `app/admin/routes.py:34` -- `password != admin_password`
- JavaScript: `frontend/middleware/auth.js:11` -- `password !== process.env.ADMIN_PASSWORD`

## Proposed Solution
- Python: Use `hmac.compare_digest(password, admin_password)`
- JavaScript: Use `crypto.timingSafeEqual(Buffer.from(password), Buffer.from(process.env.ADMIN_PASSWORD))` with length pre-check

## Acceptance Criteria
- [x] Python uses `hmac.compare_digest` for password comparison
- [x] JavaScript uses `crypto.timingSafeEqual` for password comparison
