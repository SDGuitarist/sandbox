---
title: "Recipe Organizer Swarm Build"
date: 2026-04-09
category: swarm-build
tags: [flask, sqlite, swarm, junction-table, search, csrf, batch-fetch]
module: recipe-organizer
symptom: "Need to build a multi-blueprint Flask app with many-to-many relationships and ingredient search"
root_cause: "Standard CRUD + junction table pattern with LIKE-based search"
---

# Recipe Organizer Swarm Build

## Problem

Build a personal recipe organizer with ingredient-based search using a 3-agent
swarm (core, routes, templates). Key challenge: many-to-many recipe-ingredient
relationship with a junction table, and a search feature that finds recipes by
ingredient name.

## Solution

22 source files + 2 test files built by 3 swarm agents. All verification gates
passed: ownership (0 violations), contract check (all 6 contracts), smoke test
(16/16), test suite (21/21).

## Key Lessons

### 1. Parallel Array Desync is a Real Risk (Feed-Forward Verified)

The brainstorm flagged `request.form.getlist()` with parallel arrays as the
least-confident area. Review confirmed: Python's `zip()` silently truncates
mismatched-length lists, causing ingredient IDs to pair with wrong quantities.

**Fix:** Add length equality check before zip():
```python
if not (len(ingredient_ids) == len(quantities) == len(units)):
    flash("Ingredient data is malformed.", "error")
    return rerender()
```

**Lesson:** When the Feed-Forward flags a risk, the review MUST verify it. This
one was real. Trust the uncertainty signal.

### 2. Simplicity Deepening Saved ~100 LOC Before Build

The deepening phase removed 4 YAGNI features before any code was written:
- Sort system (4 options) -- hardcoded newest-first instead
- Ingredient detail page -- search already covers this
- `default_unit` column -- junction table has its own unit
- Separate batch counts function -- inline subquery instead

**Lesson:** Run simplicity review during planning, not just after implementation.
Removing features from a plan is free; removing them from code costs time.

### 3. Composite PK on Junction Tables (Gold Standard)

The bookmark-manager uses `PRIMARY KEY (bookmark_id, tag_id)` on its junction
table. The initial plan had a surrogate `id` column plus a UNIQUE constraint.
Architecture review caught this -- the surrogate ID is unnecessary and wastes
space. Match the gold standard: composite PK, no surrogate.

### 4. WAL Mode is Persistent in SQLite

Architecture agent flagged missing `PRAGMA journal_mode=WAL` in `get_db()` as
P1. Performance agent correctly noted WAL is persistent per-database-file -- once
set in `init_db()`, it stays until explicitly changed. Setting it per-connection
is redundant.

**Lesson:** Cross-reference agent findings. When two agents disagree, check the
authoritative source (SQLite docs). WAL is persistent.

### 5. get_db Must Always Commit/Rollback

The initial plan had conditional commit (`if immediate: conn.commit()`). The gold
standard always commits on success, always rolls back on exception, regardless
of the `immediate` flag. This prevents silent data loss if a read-only path
accidentally writes.

### 6. Correlated Subqueries Scale Poorly

`get_all_ingredients` uses a correlated COUNT subquery per row. At 20 rows/page
this is fine, but the unbounded dropdown call (`limit=1000`) amplifies this.
Better approach: LEFT JOIN + GROUP BY, or a lightweight `get_ingredient_names`
for dropdowns that skips the count entirely.

### 7. Two-Connection Race in Edit Routes

Edit routes that first read (to check existence) then write (to update) in
separate `get_db()` blocks create a TOCTOU gap. The gold standard wraps both
in a single `get_db(immediate=True)` block.

## Risk Resolution

1. **Flagged risk:** Parallel array parsing with getlist() might desync.
   **What happened:** Review confirmed zip() truncation is a real vulnerability.
   **Lesson:** Feed-Forward uncertainty signals are valuable. Verify them in review.

2. **Flagged risk:** Ingredient linking UX might be clunky without JS.
   **What happened:** 12 lines of JS (clone/remove rows) solved it cleanly.
   **Lesson:** Minimal JS is the sweet spot between pure HTML (too clunky) and
   full frameworks (overkill).

## Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-04-09-recipe-organizer-brainstorm.md |
| Plan | docs/plans/2026-04-09-feat-recipe-organizer-plan.md |
| Reports | docs/reports/025/ |
| Solution | docs/solutions/2026-04-09-recipe-organizer-swarm-build.md |

## Stats

- **Files:** 24 (22 source + 2 test)
- **Lines:** ~1960
- **Agents:** 3 (core, routes, templates)
- **Merge conflicts:** 0
- **Smoke tests:** 16/16
- **Unit tests:** 21/21
- **Review findings:** 2 P1 (fixed), 5 P2 (deferred), 5 P3 (deferred)
