# Review Context -- Sandbox (Feedback Board, Run 045)

## Risk Chain

**Brainstorm risk:** Denormalized vote_count consistency under concurrent upvotes.

**Plan mitigation:** BEGIN IMMEDIATE + SQL atomic increment (vote_count = vote_count + 1). Confirmed INSERT OR IGNORE rowcount=0 during plan deepening.

**Work risk (from Feed-Forward):** before_request admin auth hook interaction with Flask-WTF CSRF on admin POST routes.

**Review resolution:** 3 agents found 2 P1, 5 P2, 7 P3. All P1/P2 fixed. Key fixes: init_db try/finally, deduplicated query builder, typed return values, documented CSRF/auth hook ordering. Zero learnings violations. Security false positive on blocklist check.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| feedback-board/app/db.py | New -- DB layer with get_db + init_db | init_db connection leak (fixed), WAL placement |
| feedback-board/app/models.py | New -- 7 model functions | Upvote dedup atomicity, query builder extraction |
| feedback-board/app/__init__.py | New -- App factory | SECRET_KEY fail-closed, CSRF/auth ordering |
| feedback-board/app/blueprints/admin/routes.py | New -- Admin with brute-force | Hook ordering comment, eviction cap |
| feedback-board/app/blueprints/public/routes.py | New -- Public routes | Input validation, CSRF on upvote forms |

## Plan Reference

`docs/plans/2026-05-18-feat-feedback-board-plan.md`
