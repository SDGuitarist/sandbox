---
title: "Prompting Dashboard Engine"
date: 2026-06-01
run_id: "061"
project: prompt-dashboard
tags: [flask, sqlite, fts5, swarm, claude-api, blueprint, context-death]
build_method: swarm
agents: 10
files: 25
loc: 1614
status: complete
---

# Prompting Dashboard Engine

## What Was Built

A local-first prompt engineering workbench: create prompt templates with `{{variable}}` placeholders, test them against the Claude API, track version history with side-by-side diffs, and browse a prompt library with FTS5 search and tag filtering. Flask + SQLite + Jinja2 + Bootstrap 5 dark theme. Single-user, no auth.

- **3 blueprints:** dashboard (1 route), prompts (8 routes), testing (3 routes)
- **6 database tables** including FTS5 virtual table with 4 sync triggers
- **17 model functions** in a centralized data layer
- **13 smoke tests**, all passing

## What Went Right

### Spec quality drove zero-conflict assembly

The 10-agent swarm produced 25 files that merged with **0 conflicts**. The shared interface spec included all 6 mandatory sections (Export Names, Cross-Boundary Wiring, Input Validation, Coordinated Behaviors, Transaction Contracts, Authorization Matrix). The architecture review verified every export name, wiring path, and coordinated behavior matched the spec exactly.

### Prior solution docs prevented known failures

- **flask-swarm-acid-test:** Prescribed context manager usage examples (`with get_db() as conn:`), prescriptive code blocks, and vertical blueprint splitting. All followed.
- **flask-url-shortener-api:** WAL mode + busy_timeout, init_db() timing (never in before_request), atomic SQL expressions. All followed.
- **isolation_level warning** from runs 054/056/057: Comment in database.py prevented the 3-build recurrence of `isolation_level=None` breaking commits.

### FTS5 trigger ordering caught during deepening

The plan's P1 fix #1 changed FTS5 DELETE/UPDATE triggers from AFTER to BEFORE. This is critical for external-content FTS5 tables — AFTER triggers read stale values from the already-modified content table, corrupting the search index. Framework-docs-researcher caught this during plan deepening, not during review.

## What Went Wrong

### Context death before the shared tail

The orchestrator ran out of context before starting the 9-step shared tail (review, compound, learnings, etc.). Root cause: the orchestrator accumulates context from every agent spawn prompt + result, plus deepening sub-agents, pre-swarm gates, ownership diffs, and assembly merges. With 10 swarm agents + heavy pre-swarm work (15 P1/P2 deepening fixes, 3 consistency contradictions, 2 document-review passes), the orchestrator hit ~98% context before the tail.

**Key insight:** The context budget heuristic only counts swarm agents but not pre-swarm work density. Run 061 had fewer swarm agents (10) than calibration runs (16-31) yet still died, because the pre-swarm phase was unusually dense.

**Fix needed:** Implement "Tier 2 Pre-Review Resume" checkpoint — already identified in the 2026-05-20 solution doc as future work, never built.

### BUILD_TRACKING rows misplaced

The 10 AGENT_STATUS rows were appended to the end of BUILD_TRACKING.md (after the Template Version section) instead of being inserted into the AGENT_STATUS table. Root cause: incremental `echo >>` writes append to the file end instead of inserting into a specific table location. Fix: use Edit tool for row insertion instead of echo append.

### Raw SQL escaped the model layer

The testing route contained a direct SQL query (`SELECT id FROM prompt_versions ... LIMIT 1`) instead of going through the model layer. This was the only instance in the codebase — the swarm agent likely wrote it for convenience since `get_prompt_versions()` fetches all versions. Fixed by adding `get_latest_version_id()` to models.py.

## Risk Resolution (Feed-Forward)

**Brainstorm risk:** "Claude API synchronous calls may timeout in Flask request cycle"

**Plan mitigation:** 60s explicit timeout on Anthropic client, distinct exception handling for `APITimeoutError`, `APIConnectionError`, `APIStatusError`, `threaded=True` on dev server.

**Review finding:** The mitigation was well-implemented but had two gaps:
1. No generic `except Exception` fallback — unexpected exceptions (e.g., `json.JSONDecodeError`, empty `content` array) would crash with 500 instead of storing an error record.
2. `response.content[0].text` would `IndexError` on empty content arrays.

**Resolution:** Added generic exception handler with server-side logging, and a guard on `response.content[0]`. All error paths now store a test run record — no 500 errors possible from API failures.

## Patterns Worth Reusing

### Prescriptive code blocks in swarm specs

Writing exact Python code for cross-agent integration surfaces (app factory, database module, model function signatures with usage examples) eliminated mismatches. The spec was 1100 lines for 10 agents — large but justified.

### FTS5 external content with BEFORE triggers

External content FTS5 (`content=prompts, content_rowid=id`) avoids doubling storage. But triggers MUST be BEFORE DELETE/UPDATE, not AFTER — FTS5 reads old values from the content table to remove tokens. If the row is already gone, the index corrupts silently.

### Transaction contract annotations in specs

Annotating every model function with "commits internally (BEGIN IMMEDIATE)", "does NOT commit", or "read-only" prevented transaction boundary confusion across 10 agents. The `set_prompt_tags` function correctly does NOT commit because it runs inside the caller's transaction.

### Form parsing deduplication

Create and update routes share identical form parsing logic. Extracting a `_parse_prompt_form()` helper eliminated 18 lines of duplication and ensured validation changes (like the 100k char limit added during review) are applied consistently.

## Metrics

| Metric | Value |
|--------|-------|
| Swarm agents | 10 |
| Files produced | 25 |
| Lines of code | ~1700 (post-review) |
| Merge conflicts | 0 |
| Contract check failures | 2 (fixed by assembly-fix) |
| Smoke tests | 13/13 PASS |
| Review findings | 12 (2 P1, 6 P2, 4 P3) |
| Review findings fixed | 8/8 (all P1 + P2) |
| Context death | Yes (pre-tail, manual completion) |

## Feed-Forward

- **Hardest decision:** Two-table version storage (prompts + prompt_versions). Adds transaction complexity but makes dashboard queries trivial.
- **Rejected alternatives:** Single version table (slow dashboard), SPA frontend (overkill), Jinja2 template engine for variables (too powerful).
- **Least confident:** Whether the context death fix (Tier 2 checkpoint) should be automatic or require plan frontmatter opt-in. The heuristic needs pre-swarm work density, not just agent count.
