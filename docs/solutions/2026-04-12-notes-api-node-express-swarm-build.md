---
title: "Notes API -- First Node/Express Swarm Build"
date: 2026-04-12
category: integration-issues
tags: [node, express, better-sqlite3, swarm, rest-api, junction-table, test-isolation]
module: notes-api
symptom: "Untested assumption: swarm build pattern works outside Flask"
root_cause: "Stack-agnostic claim was unverified -- Node/Express has different module resolution, test isolation, and middleware patterns than Flask"
---

# Notes API -- First Node/Express Swarm Build

## Problem

The swarm build pattern (parallel agents with shared interface spec) had only been tested with Flask + SQLite + Jinja2. The HANDOFF.md listed "Node/Express swarm build" as a deferred item to validate the stack-agnostic claim. Key uncertainty: whether `createApp(db)` injection and `req.app.locals.db` would work for test isolation in a 3-agent swarm.

## What Worked

The swarm build pattern **translates cleanly to Node/Express**. 3 agents (core, notes, tags) produced 11 files with 836 LOC total. All 45 tests passed on first assembly. All 13 endpoints responded correctly in smoke test.

### Key Pattern Translations (Flask → Node/Express)

| Pattern | Flask | Node/Express |
|---------|-------|-------------|
| App factory | `create_app()` returns Flask app | `createApp(db)` returns Express app |
| DB injection | `g.db` via app context | `app.locals.db` via constructor arg |
| Test isolation | `create_app()` with temp DB path | `createApp(createTestDb())` with `:memory:` |
| Route mount | `app.register_blueprint(bp, url_prefix=...)` | `app.use('/api/notes', require('./routes/notes'))` |
| DB access in routes | `from models import func; func(get_db(), ...)` | `const db = req.app.locals.db; func(db, ...)` |
| Synchronous DB | N/A (stdlib sqlite3 is sync-ish) | `better-sqlite3` is fully synchronous |

### What the Plan Got Right

1. **Explicit prohibition rule**: "Route files MUST NOT require db.js" -- all 13 route handlers used `req.app.locals.db` correctly. No agent violated this.
2. **Example route handler in spec**: The concrete code example showing `const db = req.app.locals.db` eliminated ambiguity. Prior Flask builds that omitted usage examples had identical misuse across all agents.
3. **`createTestDb()` returning `:memory:`**: Each test got a fresh isolated DB. No shared state. Tests ran in 0.3s.
4. **`createApp(db)` requiring the db argument**: Making it throw on missing db (not fallback to singleton) caught injection errors early.
5. **Relative route paths**: The "CRITICAL" callout about mount-relative paths prevented the route-prefix-doubling bug from the finance tracker build.

## What the Review Found (Post-Assembly)

Only 2 minor fixes needed:
1. **Missing tag existence check** in `addTagToNote` route -- FK violation would return generic 500 instead of 404. Fixed by importing `getTagById` from tags model.
2. **Missing `Number()` cast** on tag creation response -- `better-sqlite3` returns BigInt for `lastInsertRowid`. Notes route had the cast; tags route didn't. Normalized.

Neither was a spec ambiguity -- both were agent implementation oversights caught by review agents.

## Risk Resolution

**Flagged risk (from brainstorm/plan Feed-Forward):** Whether the swarm build pattern translates cleanly from Flask to Node/Express.

**What actually happened:** It translated with zero structural issues. The `createApp(db)` / `req.app.locals.db` pattern is arguably cleaner than Flask's `g.db` because the dependency injection is explicit in the constructor. The main adaptation was: Node modules are `require()`-d once but Express route handlers execute per-request, so `req.app.locals.db` resolves correctly to the injected DB each time.

**Lesson learned:** The shared spec pattern is genuinely stack-agnostic. The critical factor is not the framework -- it's the spec precision. Usage examples, prohibition rules, and concrete code patterns in the spec matter more than which language or framework is used.

## Prevention / Best Practices

1. **Always include a concrete route handler example in the spec** -- not just a route table. The example should show the `db` extraction pattern.
2. **Make DB injection mandatory, not optional** -- `createApp(db)` that throws on missing db is better than `createApp(db?)` that falls back to a singleton.
3. **Add `Number()` cast on all `lastInsertRowid` returns** -- better-sqlite3 may return BigInt. Cast in the model function or route handler.
4. **Verify FK targets exist before INSERT** -- don't rely on FK constraint errors for user-facing 404s. The constraint error message is internal and should not leak.

## Deepening Insights Applied

The plan was deepened with 4 review agents (architecture, security, performance, simplicity) + Context7 docs. Key improvements from deepening:
- Error handler sanitized (500s never leak internal messages)
- Input validation adds type checks before `.trim()` (prevents TypeError on non-string body fields)
- Reject over-length input instead of silent truncation
- 50kb body size limit on `express.json()`
- Default LIMIT 200 on list queries as safety net
- Removed redundant Endpoint Registry table (Route Table was sufficient)
- Removed `express.urlencoded()` (JSON-only API)
- Simplified db.js (no singleton, explicit `createDb()` calls only)

## Related Docs

- [autopilot-swarm-orchestration](2026-04-09-autopilot-swarm-orchestration.md) -- scalar returns, data ownership, spec precision
- [bookmark-manager-swarm-build](2026-04-09-bookmark-manager-swarm-build.md) -- tag patterns, endpoint registry
- [recipe-organizer-swarm-build](2026-04-09-recipe-organizer-swarm-build.md) -- composite PK, junction tables
- [personal-finance-tracker-swarm-build](2026-04-09-personal-finance-tracker-swarm-build.md) -- route prefix doubling
- [flask-swarm-acid-test](2026-04-07-flask-swarm-acid-test.md) -- test isolation, usage examples

## Stats

- **Agents:** 3 (core, notes, tags)
- **Files:** 11
- **LOC:** 836
- **Tests:** 45 (all passing)
- **Endpoints:** 13
- **Review fixes:** 2 (minor)
- **Build time:** ~3 minutes (parallel agents)
