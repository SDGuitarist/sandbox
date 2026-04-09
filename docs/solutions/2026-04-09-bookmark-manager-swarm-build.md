---
title: "Swarm-Built Flask Bookmark Manager with Endpoint Registry Lesson"
date: 2026-04-09
project: bookmark-manager
category: swarm-build
tags: [flask, sqlite, swarm, parallel-agents, contract-check, YAGNI, url_for, endpoint-names]
stack: [Python, Flask, SQLite, Jinja2, urllib]
status: complete
lines: 1089
files: 17
agents_build: 3
agents_review: 9
difficulty: beginner
problem: "Build a personal bookmark manager using parallel swarm agents; template/route endpoint name mismatches caused runtime errors"
solution: "Prescriptive specs with usage examples + post-assembly contract check + endpoint registry pattern"
root_cause: "Swarm spec listed route behavior but not exact function names; templates agent guessed different names than routes agent defined"
symptom: "Flask BuildError on url_for calls -- 3 of 17 files had wrong endpoint names"
---

# Swarm-Built Flask Bookmark Manager

## Problem

Built a personal bookmark manager (Flask + SQLite, 17 files, 1089 lines) using a 3-agent swarm (core, routes, templates). Two integration issues surfaced at assembly:

1. **`url_for` endpoint mismatches** -- Templates agent used `bookmarks.list_bookmarks` and `bookmarks.detail`; routes agent defined `bookmarks.index` and `bookmarks.show_bookmark`. Flask raised `BuildError` on every page.
2. **sort_order not validated in routes** -- Invalid `?sort=evil` caused unhandled 500 (ValueError from `_sort_clause`).

## Root Cause

1. **No endpoint registry in the spec.** The plan listed route behavior (GET /bookmarks -> list) but not the exact Python function names that Flask uses for `url_for`. Each agent chose independently.
2. **Validation responsibility gap.** Plan said "sort_order MUST be validated against SORT_OPTIONS" in the models spec, but didn't say routes must also validate. Routes agent assumed models would handle it gracefully.

## Solution

### Fix 1: Corrected url_for endpoints post-assembly

Updated all template references to match actual route function names:
- `bookmarks.list_bookmarks` -> `bookmarks.index`
- `bookmarks.detail` -> `bookmarks.show_bookmark`
- `tags.list_tags` -> `tags.index`

### Fix 2: Added sort_order validation in routes

```python
sort_order = request.args.get('sort', 'newest')
if sort_order not in SORT_OPTIONS:
    sort_order = 'newest'
```

Applied in both `bookmarks/routes.py` and `tags/routes.py`.

## Prevention: Endpoint Registry Pattern

Future swarm specs that involve Flask (or any framework with named endpoints) must include an **Endpoint Registry** table:

| Blueprint | Function Name | Method | Path | url_for Name |
|-----------|---------------|--------|------|-------------|
| bookmarks | index | GET | / | bookmarks.index |
| bookmarks | new_bookmark | GET | /new | bookmarks.new_bookmark |
| bookmarks | create_bookmark_route | POST | /new | bookmarks.create_bookmark_route |
| bookmarks | show_bookmark | GET | /\<int:id\> | bookmarks.show_bookmark |
| bookmarks | edit_bookmark | GET | /\<int:id\>/edit | bookmarks.edit_bookmark |
| bookmarks | update_bookmark_route | POST | /\<int:id\>/edit | bookmarks.update_bookmark_route |
| bookmarks | delete_bookmark_route | POST | /\<int:id\>/delete | bookmarks.delete_bookmark_route |
| tags | index | GET | / | tags.index |
| tags | show | GET | /\<name\> | tags.show |

This table must be in the shared spec so both the routes agent and templates agent reference the same names.

## What Worked Well

1. **9-agent plan deepening cut ~165 LOC of YAGNI** -- Dropped SSRF module, preferences blueprint, and card view before any code was written. The simplicity reviewer's argument was compelling: single-user personal tool needs none of these.

2. **Prescriptive usage examples prevented known swarm bugs** -- The spec included exact `with get_db() as conn:` patterns and `bookmark_id = create_bookmark(conn, ...)` scalar return examples. These prevented the context-manager and scalar-return bugs documented in prior solution docs.

3. **EXISTS subquery pattern for search** -- Performance review recommended `EXISTS (SELECT 1 FROM bookmark_tags bt JOIN tags t ...)` instead of flat JOIN + DISTINCT. Avoids duplicate rows and short-circuits on first match.

4. **Batch tag fetching** -- `get_tags_for_bookmarks(conn, bookmark_ids)` fetches all tags for a page of bookmarks in one query, returning `dict[int, list[Row]]`. Prevents N+1 queries in the list template.

5. **Contract check caught all 3 mismatches before smoke test** -- The spec-contract-checker agent validated 75 contract points and flagged the 3 url_for issues. Without it, these would have been discovered at runtime.

## Architecture Decisions Worth Reusing

| Decision | Pattern | Why |
|----------|---------|-----|
| Many-to-many tags | Junction table with CASCADE + orphan cleanup | Free-form tags, no predefined categories |
| Search | LIKE with EXISTS subqueries, _escape_like helper | Simple, no FTS5 dependency, handles wildcards |
| Sort | Query param + SORT_MAP allowlist, not stored preference | YAGNI for single-user; bookmarkable URLs |
| CSRF | Session-based token via before_request hook | No extra dependencies beyond Flask |
| SECRET_KEY | `secrets.token_hex(24)` per startup | Personal tool; sessions don't need to survive restarts |
| DB connections | Context manager with immediate=True for writes | WAL mode, auto commit/rollback |

## Related Solution Docs

- [flask-swarm-acid-test](2026-04-07-flask-swarm-acid-test.md) -- Context manager usage examples are mandatory
- [task-tracker-categories-swarm](2026-04-09-task-tracker-categories-swarm.md) -- Scalar return usage examples catch type mismatches
- [autopilot-swarm-orchestration](2026-04-09-autopilot-swarm-orchestration.md) -- Full swarm pipeline with verification stages
- [swarm-scale-shared-spec](2026-03-30-swarm-scale-shared-spec.md) -- Spec scales linearly with agents; route manifest is critical

## Risk Resolution

- **Flagged risk (plan Feed-Forward):** "Auto-fetch title via urllib could be slow or fail on many sites."
- **What happened:** Simplified to plain urllib with 3s timeout and 100KB read limit. No SSRF protection (intentional for personal tool). Works well in smoke tests.
- **Lesson:** The deepening phase correctly identified this as the riskiest feature, and the simplification (dropping SSRF) eliminated the DNS TOCTOU critical vulnerability entirely. Trust the review agents' YAGNI calls.

## New Rule for Spec Template

Add to the shared spec template for all future Flask swarm builds:

```markdown
### Endpoint Registry

| Blueprint | Function Name | Method | Path | url_for Name |
|-----------|---------------|--------|------|-------------|
| ... | ... | ... | ... | ... |

Templates agent: use ONLY the `url_for Name` column. Do not invent endpoint names.
```
