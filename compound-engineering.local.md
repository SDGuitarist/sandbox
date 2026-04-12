# Review Context -- Sandbox

## Risk Chain

**Brainstorm risk:** Whether the swarm build pattern translates cleanly from Flask to Node/Express -- first Node swarm build, untested stack switch.

**Plan mitigation:** Created detailed shared interface spec with: explicit prohibition rule against importing db.js in routes, concrete route handler example, mandatory DB injection (throws on missing db), Node-specific patterns (better-sqlite3 sync API, createTestDb with :memory:).

**Work risk (from Feed-Forward):** Whether req.app.locals.db works correctly when routes are loaded via require() in the app factory.

**Review resolution:** 0 P1, 1 P2 (rate limiting - out of scope), 3 P3. Two minor fixes applied. All 45 tests pass. Risk fully resolved.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| notes-api/app.js | Express app factory with DB injection | Test isolation via app.locals.db |
| notes-api/routes/notes.js | 7 route handlers including tag associations | DB access pattern, FK handling |
| notes-api/routes/tags.js | 6 route handlers including notes-for-tag | BigInt cast, duplicate name handling |
| notes-api/db.js | createDb/createTestDb factory functions | :memory: for tests, pragmas |

## Plan Reference

docs/plans/2026-04-12-feat-notes-api-with-tags-plan.md
