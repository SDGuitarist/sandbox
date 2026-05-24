---
project: bookmark-tagger
date: 2026-05-23
app: Bookmark Tagger
tech_stack: Flask + SQLite + Jinja2
build_method: manual (plan-flow pipeline test)
agent_count: 0
files: 14
loc: 755
test_count: 30
reviews: 2
p1_findings: 0
p2_findings: 5
status: complete
category: pipeline-validation
tags:
  - flask
  - sqlite
  - ssrf-protection
  - plan-flow-pipeline
  - compound-engineering
  - url-fetching
  - csrf
  - tag-management
---

# Bookmark Tagger: Plan-Flow Pipeline Test

## What Was Built

A throwaway Flask + SQLite bookmark tagger app (14 files, 755 LOC, 30
tests). Users paste a URL, the app auto-fetches title and meta description,
users add comma-separated tags, and everything is stored in SQLite. A
single-page list view supports search by keyword and filter by tag.

## Why It Matters

This was the first real test of the `/plan-flow` pipeline skill (plan ->
deepen -> self-review -> Codex handoff). The goal was to answer: does the
pipeline produce a plan thorough enough that implementation requires zero
deviations?

**Result: Yes.** The plan covered schema, routes, CSRF, input validation,
SSRF protection, search, and orphan cleanup. The deepening phase (6
parallel research agents) caught 5 issues that would have been bugs in
production. Implementation followed the plan exactly with no mid-build
redesigns.

## Key Problems Solved

### 1. SSRF via User-Provided URL Fetching

`urllib.request.urlopen()` accepts arbitrary schemes including `file://`.
Solution: scheme allowlist check before any network call.

```python
def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and parsed.hostname is not None
```

Called at both the route layer (user-facing flash) and inside
`fetch_page_meta()` (defense-in-depth). Accepted non-goal: private IP
blocking and redirect-hop validation are out of scope because the app is
local-only.

### 2. Meta Description Extraction -- Both Attribute Orderings

HTML meta tags have no mandatory attribute order. The initial regex only
matched `<meta name="description" content="...">`. Codex caught this in
the first review.

Fix: two-pass regex -- try name-first, fall back to content-first.

### 3. Tag Management with Case-Insensitive Dedup

Tags entered as "Python" and "python" must not create duplicates.
`get_or_create_tag()` lowercases before insert. `INSERT OR IGNORE` with
a `UNIQUE` constraint handles dedup. Orphan tags are cleaned up after
every bookmark deletion.

### 4. LIKE Search Escaping

`%` and `_` in user input are wildcards in SQLite LIKE. `_escape_like()`
backslash-escapes them. All LIKE clauses use `ESCAPE '\'`.

### 5. Monkeypatch Target Pitfall

Tests initially patched `app.fetch_meta.fetch_page_meta` (where the
function is defined), but `__init__.py` imports it with `from app.fetch_meta
import fetch_page_meta`, creating a local binding. The patch target must be
`app.fetch_page_meta` (where the name is looked up).

## Codex Review Findings

### First Review (5 issues, all fixed in `6108081`)

1. Meta description regex only handled one attribute ordering
2. Bookmark descriptions not rendered in the list UI
3. Tag truncation was silent (no flash warning)
4. Missing `ftp://` and no-hostname rejection tests
5. No direct `fetch_page_meta` parser tests (all monkeypatched)

### Second Review

Clean. No findings.

## Pipeline Validation Results

The `/plan-flow` pipeline produced a plan that:

- Required **zero deviations** during implementation
- Pre-identified the SSRF risk via the Security sentinel research agent
- Added charset detection, content-type validation, input limits, and
  `<int:id>` route converter during deepening
- Produced EARS acceptance criteria specific enough to generate tests from

The deepening step was the key differentiator. Without it, the SSRF
protection and input validation limits would have been discovered during
implementation or review instead of during planning.

## Prevention Strategies

### For Future Builds

1. **SSRF trust boundary in plans:** Every plan that accepts user-supplied
   URLs must declare a trust boundary (`local-only | authenticated | public`).
   Validation depth follows exposure level.

2. **HTML attribute order:** When using regex for HTML extraction, always
   test both attribute orderings. Prefer a parser when dependencies allow.

3. **Monkeypatch target rule:** Always patch where the name is looked up,
   not where it is defined. If the module does `from x import y`, patch
   `module.y` not `x.y`.

4. **Branch scope check:** Before review, run `git diff main...HEAD
   --name-only` and verify every changed file relates to the plan's scope.
   Codex caught unrelated plan-flow tooling files on the feature branch.

5. **Never skip deepen + Codex:** This build is proof the pipeline works.
   The deepen step caught 5 issues. Codex caught 5 more. Zero issues
   survived to production.

## Related Docs

- `docs/solutions/2026-04-09-bookmark-manager-swarm-build.md` -- prior
  bookmark app (same domain, 3-agent swarm). Its `fetch_title.py` had no
  SSRF protection.
- `docs/solutions/2026-04-05-flask-url-shortener-api.md` -- SQLite WAL mode
  + busy timeout pattern used in this build's `db.py`.
- `docs/solutions/2026-04-05-url-health-monitor.md` -- SSRF protection
  pattern with private IP blocking (the stronger version this build
  explicitly deferred).
- `docs/solutions/2026-05-18-feedback-board-solo-build.md` -- Solo Flask
  build with CSRF pattern reused here.

## Risk Resolution

**Feed-Forward risk from plan:** "SSRF via URL fetching -- user-provided
URLs could target internal services or cloud metadata endpoints."

**What actually happened:** Scheme-only validation (`http`/`https`
allowlist) was implemented and tested. The deepen phase's Security sentinel
flagged this risk before implementation. Codex verified the protection in
both review passes. The risk was resolved within the accepted boundary
(local-only app). If the app were ever exposed publicly, private IP
blocking and redirect-hop validation would be required.

## Feed-Forward

- **Hardest decision:** Whether the monkeypatch target fix belonged in the
  solution doc or in agent-pitfalls.md. It's a general Python testing
  pitfall, not specific to this app. Documented here with a note to
  propagate to agent-pitfalls.md during learnings update.

- **Rejected alternatives:** Considered skipping the solution doc since
  this is a throwaway test app. Rejected because the pipeline validation
  results are the valuable artifact, not the app itself.

- **Least confident:** Whether the plan-flow pipeline's success here
  generalizes to more complex apps. This app had ~230 planned LOC and
  simple requirements. A larger app with external integrations, auth, or
  real-time features might expose pipeline gaps that this test didn't
  surface.
