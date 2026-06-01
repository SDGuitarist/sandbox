---
title: Prompting Dashboard Engine
date: 2026-06-01
status: complete
type: brainstorm
---

# Prompting Dashboard Engine — Brainstorm

## What We're Building

A local-first prompt engineering workbench for a single developer. The dashboard lets you create prompt templates with variable placeholders, test them against the Claude API, track version history with diffs, and browse your prompt library with search and tag filtering. It runs as a Flask app on localhost with SQLite storage.

**Core workflow:** Create template → define variables → fill variables → send to Claude → view response → iterate (edit creates new version) → compare versions side-by-side.

**Target user:** Solo prompt engineer who wants to organize, test, and iterate on prompts without switching between text files and API playgrounds.

## Why This Approach

### Architecture: Blueprint-based modular Flask

Three blueprints: `prompts` (CRUD + versioning), `testing` (execute + results), `dashboard` (overview + search). This is the proven pattern from 15+ prior sandbox builds. The shared-spec-flask.md template directly supports it.

**Why not flat single-file?** The app has distinct concerns (template management, API execution, search/filtering) that benefit from separation. Prior builds show blueprint structure prevents route prefix collisions and enables clean data ownership.

**Why not API-first + SPA?** Overkill for a single-user local tool. Jinja2 server-rendered pages are simpler, faster to build, and the spec template is optimized for this pattern.

### Database: SQLite with version chain

Two core tables: `prompts` (current state) and `prompt_versions` (immutable history). Each edit creates a new version row. The `prompts` table always points to the latest version. This separates "what's current" from "what changed" cleanly.

**Why not single table with version column?** Querying "latest version of each prompt" requires window functions or subqueries on every dashboard load. The two-table approach makes the common case (list current prompts) a simple SELECT.

### Variable System: Regex extraction + string substitution

Variables use `{{variable_name}}` syntax (double curly braces). Extraction via `re.findall(r'\{\{(\w+)\}\}', template_text)`. Substitution via `str.replace()`. Variables stored as JSON array on the prompt.

**Why not Jinja2 as the template engine?** Jinja2 has control flow, filters, and inheritance — all unnecessary complexity for variable substitution. A prompt template with `{% if %}` blocks would be confusing. Simple regex keeps the mental model clear: variables are slots, nothing more.

### Test Runner: Server-side Claude API call

The test form fills variables, substitutes them into the template, sends to Claude API via the `anthropic` Python SDK, and displays the response on the same page. Results are stored with a reference to the prompt version used.

**Why server-side, not client-side?** API key stays on the server. No CORS issues. Response stored directly to SQLite. Simpler error handling.

### Diff View: Python difflib

Side-by-side diff between any two versions using `difflib.HtmlDiff`. Rendered server-side as HTML table. No JavaScript diff library needed.

### UI: Bootstrap 5 dark theme

CDN-loaded Bootstrap 5 with dark mode (`data-bs-theme="dark"`). Consistent with prior sandbox builds. Code/prompt text areas use monospace font. Response display uses a card with pre-formatted text.

## Key Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Architecture | Blueprint modular (3 blueprints) | Proven at 15+ agent scale, spec template supports it |
| 2 | Version storage | Two tables (prompts + prompt_versions) | Fast dashboard queries, clean separation |
| 3 | Variable syntax | `{{variable_name}}` with regex | Simple, familiar, no engine overhead |
| 4 | LLM provider | Claude API only (MVP) | Single provider simplifies, multi-provider is Phase 2 |
| 5 | Diff rendering | Python difflib server-side | No JS dependency, good enough for text diffs |
| 6 | Auth | None (single-user local tool) | Out of scope per brief |
| 7 | Search | SQLite FTS5 on prompt name + content | Proven pattern, needs FC36 sanitization |
| 8 | UI framework | Bootstrap 5 dark theme (CDN) | Consistent with sandbox standard |
| 9 | API key storage | Environment variable `ANTHROPIC_API_KEY` | Never in code or DB, read from os.environ |
| 10 | Test result storage | `test_runs` table linked to prompt_version | Enables "last tested" dashboard column |

## Open Questions

*All resolved during brainstorm — none remaining.*

## Resolved Questions

1. **Should tags be a separate table or comma-separated?** → Separate `tags` and `prompt_tags` junction table. Enables proper filtering, avoids LIKE queries on comma strings. Small overhead, big query benefit.
2. **How to handle API errors during test runs?** → Store the error message in the `test_runs.error` column (nullable). Display error in a red alert card on the test page. Never expose raw API error details — log full error server-side, show user-friendly message.
3. **Should version diffs be pre-computed or on-demand?** → On-demand. difflib is fast for text of prompt length (<10KB). Pre-computing would add storage overhead and complexity for no user-perceptible benefit.
4. **Max prompt/response size?** → SQLite TEXT has no practical limit. UI textarea has no hard limit. Claude API has its own token limits which will naturally constrain input size.
5. **How to handle concurrent test runs?** → Not needed for MVP (single user, synchronous requests). The test form submits, waits for Claude response, displays result. No background jobs.

## Scope Boundaries

**In scope (MVP):**
- Prompt template CRUD (name, description, system prompt, user prompt, tags)
- Variable extraction from `{{placeholder}}` syntax
- Test execution against Claude API with variable substitution
- Version history (auto-created on edit) with side-by-side diff
- Test run history per prompt (date, model, tokens used, response preview)
- Dashboard with search (FTS5) and tag filtering
- Bootstrap 5 dark theme UI

**Out of scope (Phase 2+):**
- Multi-provider support (OpenAI, etc.)
- Prompt evaluation / scoring / comparison
- Export/import (JSON)
- Cost tracking
- Multi-user / auth
- Prompt chaining
- Background job processing

## Technical Constraints

- **ANTHROPIC_API_KEY** from environment — app shows "API key not configured" banner if missing, test runner disabled
- **SECRET_KEY** from environment — no dev fallback (FC10)
- **CSRF** on all POST/PUT/DELETE forms — `{{ csrf_token() }}` with parentheses (FC1)
- **FTS5 sanitization** — strip operators before MATCH (FC36)
- **PRAGMA WAL + busy_timeout + foreign_keys** on every connection (FC40)
- **get_db() with context manager** — `with get_db() as conn:` usage pattern (FC2)
- **FK REFERENCES with ON DELETE** on every foreign key column (FC46)
- **Escape before Markup()** in any custom Jinja2 filters (FC47)

## Feed-Forward

- **Hardest decision:** Two-table version storage (prompts + prompt_versions) vs single table. Two-table adds a join for version history but makes the dashboard query trivial. Chose two-table because the dashboard is the most-visited page.
- **Rejected alternatives:** (1) Jinja2 as template engine for variables — too much power, confusing for prompt templates. (2) API-first + React SPA — overkill for local single-user tool. (3) Single version table with window functions — slower dashboard, more complex queries.
- **Least confident:** Whether the Claude API integration will work smoothly with synchronous Flask requests. If Claude responses take >30s, the browser may timeout. Mitigation: set a 60s timeout on the API call and show a loading indicator. If this becomes a problem in practice, Phase 2 could add async execution.

## Refinement Findings

**STATUS: PASS** — 5 gaps found, all addressable in plan phase:

1. **init_db() must use raw sqlite3.connect(), not get_db()** — executescript() issues implicit COMMIT that breaks context manager contract and can corrupt WAL setup. (Source: flask-url-shortener, feedback-board)
2. **isolation_level=None conflicts with BEGIN IMMEDIATE** — 3-build recurrence (runs 054, 056, 057). If get_db() uses autocommit mode, conn.commit() is silently ignored. Plan must prescribe explicit isolation_level setting. (Source: brewops, restaurantops)
3. **WAL mode should be verified after setting** — SQLite silently falls back to DELETE journal on some filesystems. Plan should include: `assert conn.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'`. (Source: job-queue-system)
4. **FLASK_ENV deprecated in Flask 3.0+** — Use FLASK_DEBUG=1 instead. (Source: feedback-board)
5. **Claude API timeout needs distinct exception handling** — Anthropic SDK raises APITimeoutError, APIConnectionError, APIStatusError as distinct types. Plan must prescribe specific exception handling, not bare except. (Source: ethics-toolkit)
