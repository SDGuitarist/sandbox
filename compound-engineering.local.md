# Review Context — Multi-Tenant API Gateway

## Risk Chain

**Brainstorm risk:** SSRF defense completeness at proxy time — allow_redirects=False AND timeout needed

**Plan mitigation:** allow_redirects=False non-negotiable; timeout=10s; registration-time SSRF check

**Work risk (from Feed-Forward):** DNS rebinding remains a known gap at MVP level

**Review resolution:** SSRF guard upgraded (ip.is_global + CGNAT block). 4 P1 + 10 P2 + 5 P3 found. Key fixes: admin auth added, sqlite3 connection leak fixed, streaming socket leak fixed, key prefix collision loop fixed, expires_at validation added, CRLF injection stripping added.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| db.py | @contextmanager wrapper for connection close | Connection leak prevention |
| routes_admin.py | Admin auth, SSRF upgrade, expires_at validation, p95 fix | Auth, SSRF, correctness |
| routes_proxy.py | Header sanitization, stream close, prefix loop fix, query string | Injection, resource leak |

## Plan Reference

`docs/plans/2026-04-05-feat-multi-tenant-api-gateway-plan.md`
