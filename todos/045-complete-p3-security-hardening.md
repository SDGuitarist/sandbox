---
status: pending
priority: p3
issue_id: "045"
tags: [code-review, security, brewops]
---

# Security Hardening (Dev Defaults + Headers)

## Problem Statement
Expected dev/demo defaults that should be addressed before any external deployment:

1. **Hardcoded fallbacks:** SECRET_KEY defaults to 'dev-fallback-key', ADMIN_PASSWORD defaults to 'admin'
2. **Plaintext password:** compared with `!=` instead of `check_password_hash()`
3. **Missing headers:** No Content-Security-Policy, no Strict-Transport-Security
4. **Global brute-force:** single counter (not per-IP), DoS risk
5. **run.py:** hardcoded `debug=True`
6. **No length limits:** notes, unit, phone fields accept arbitrary length
7. **hire_date:** no format validation

## Findings
- Security reviewer: C1, C2, H1, H2, M1-M4, L1

## Proposed Solution
For a sandbox/demo app, document the limitations. For deployment readiness:
1. Require SECRET_KEY and ADMIN_PASSWORD env vars (no fallbacks)
2. Use werkzeug.security password hashing
3. Add CSP and HSTS headers
4. Add field length limits

## Acceptance Criteria
- [ ] Documented that dev defaults exist and are not production-safe
