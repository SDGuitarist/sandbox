# Review Context -- Bookmark Tagger

## Risk Chain

**Brainstorm risk:** N/A (no brainstorm -- plan-flow pipeline test)

**Plan mitigation:** SSRF protection via scheme allowlist (http/https only). Trust boundary documented as local-only. Private IP blocking explicitly out of scope.

**Work risk (from Feed-Forward):** "SSRF via URL fetching -- user-provided URLs could target internal services or cloud metadata endpoints"

**Review resolution:** 2 Codex reviews, 0 P1s, 5 P2s (all fixed). Top findings: regex ordering, UI gap, silent truncation, missing tests, branch contamination. Feed-Forward risk (SSRF) verified within accepted boundary.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| bookmark-tagger/app/fetch_meta.py | SSRF check + dual regex ordering | URL fetching security |
| bookmark-tagger/app/__init__.py | CSRF, input validation, tag truncation warning | Route-level validation |
| bookmark-tagger/app/models.py | LIKE escaping, orphan cleanup | SQL injection, data integrity |

## Plan Reference

`docs/plans/2026-05-23-feat-bookmark-tagger-plan.md`
