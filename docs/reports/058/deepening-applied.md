# Deepening Applied -- Run 058

**Date:** 2026-05-23
**Agents used:** 4 (security best-practices, framework-docs, architecture-strategist, learnings-researcher)

## Changes Merged

### From security best-practices researcher:
1. Added `PERMANENT_SESSION_LIFETIME = timedelta(hours=8)` (was Flask default 31 days)
2. Added `SESSION_COOKIE_HTTPONLY = True` and `SESSION_COOKIE_SAMESITE = 'Lax'`
3. Added `session.clear()` before setting session data (session fixation prevention)
4. Added `MAX_CONTENT_LENGTH = 2 * 1024 * 1024` (2MB, prevent DoS)
5. Improved CSP: removed `'unsafe-inline'` from style-src (Bootstrap 5 doesn't need it), added `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`, `object-src 'none'`
6. Added `Referrer-Policy: strict-origin-when-cross-origin` header

### From framework-docs researcher:
7. Added `check_deliverability=False` to email_validator call (avoids DNS latency on form submit)
8. Confirmed flask-limiter `methods` parameter works for filtering by HTTP method
9. Confirmed werkzeug.security uses scrypt by default in 3.x (no changes needed)

### From architecture strategist:
10. Confirmed 4 blueprints sharing url_prefix is safe (no route conflicts)
11. Confirmed default isolation_level works with BEGIN IMMEDIATE (SELECT doesn't start implicit transactions)
12. Added explanatory note to db.py rules about why default isolation_level works
13. Identified need for explicit requirements.txt with email-validator (FC33)

### From learnings researcher:
14. Added explicit requirements.txt section (email-validator critical dependency)
15. Added .gitignore and run.py sections
16. Confirmed all 6 prior-build patterns are correctly handled in spec

## Conflicts Resolved

**isolation_level debate:** Architecture reviewer recommended isolation_level=None.
Learnings researcher confirmed ACID test validated default. BrewOps FC40 shows
isolation_level=None makes conn.commit() a no-op (3rd recurrence). Resolution:
keep default isolation_level with explanatory note. Both approaches are functionally
correct, but default avoids the misleading no-op commit pattern.

## Items NOT Merged (P3, deferred)

- HSTS header (only for production, adds dev complexity)
- TRUSTED_HOSTS config (new in Flask 3.1, not needed for MVP)
- Honeypot time-based check (adds hidden timestamp field, increases form complexity)
