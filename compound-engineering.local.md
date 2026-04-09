# Review Context -- Sandbox (Bookmark Manager Swarm Build)

## Risk Chain

**Brainstorm risk:** "Auto-fetch page titles via urllib could be slow or fail
on many sites. Needs a timeout and graceful fallback."

**Plan mitigation:** Simplified to plain urllib with 3s timeout and 100KB read
limit. Dropped SSRF protection entirely (single-user personal tool). Added
`verify_first: true` to feed_forward frontmatter.

**Work risks (from Feed-Forward):**
1. url_for endpoint name mismatches between templates and routes agents
   (3 of 17 files affected). Fixed post-assembly.
2. sort_order not validated in routes -- caused 500 on invalid input.
   Fixed by adding SORT_OPTIONS check in both route files.

**Review resolution:** 1 P1, 4 P2, 4 P3 across 4 review agents.
- P1: sort_order not validated in routes (fixed inline)
- P2: missing type hints on db/factory, str cast in search, duplicated search WHERE (fixed), unused SORT_OPTIONS (fixed)
- P3: id param shadowing, route return types, SECRET_KEY regen (deferred)
- Zero security vulnerabilities. Zero critical issues.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| bookmark-manager/app/models.py | All CRUD, search, tag functions | SQL construction, sort validation |
| bookmark-manager/app/blueprints/bookmarks/routes.py | 7 route handlers, validate_url | Input validation, transaction boundaries |
| bookmark-manager/app/templates/bookmarks/list.html | url_for calls, search, pagination | Endpoint name correctness |
| bookmark-manager/app/__init__.py | CSRF, SECRET_KEY, root redirect | Session security |

## Plan Reference

`docs/plans/2026-04-09-feat-bookmark-manager-plan.md`
