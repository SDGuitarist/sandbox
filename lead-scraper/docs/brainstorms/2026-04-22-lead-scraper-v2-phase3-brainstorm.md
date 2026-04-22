---
title: "Lead Scraper V2 Phase 3 Brainstorm: Hardening Deferrals"
date: 2026-04-22
project: lead-scraper
phase: brainstorm
feed_forward:
  risk: "Phase 3 scope is small enough that it might not justify a full compound cycle. If plan + work take under 30 minutes, skip review and compound -- just commit to master."
  verify_first: false
---

## Context

Phase 1 (outreach pipeline) and Phase 2 (opener quality + security) are complete. Both compound cycles are done. 142 tests passing, opener benchmark 5/5 on real data.

8 deferred items remain across 3 categories. This brainstorm triages them into Phase 3 scope.

## Deferred Items Triage

### From Phase 1 Review (P3s)

| Item | Decision | Rationale |
|------|----------|-----------|
| Template caching in generate loop | **WON'T FIX** | 3 templates, ~0.1ms per read, called at most 50 times per batch (--limit default). At worst 5ms total. Premature optimization with zero user impact. |
| .env parser quoted values | **WON'T FIX** | Custom .env parser handles the simple case (KEY=value). Quoted values with spaces (`KEY="hello world"`) are an edge case nobody has hit. If it matters, switch to python-dotenv (1 line). Not worth custom parsing code. |

### From Phase 2 Review

| Item | Decision | Rationale |
|------|----------|-----------|
| Upgrade CSRF to Flask-WTF | **DEFER** | Only needed if app goes on-network. Currently localhost-only. X-Requested-With check is sufficient. Revisit if deployment scope changes. |
| CSP headers + move inline script to static JS | **DEFER** | Same condition as CSRF upgrade -- only matters on-network. Jinja2 autoescaping already blocks stored XSS. |
| Null byte stripping in CSV sanitizer | **FIX** | One line change (`value = value.replace("\x00", "")`), closes a real (if unlikely) attack vector. Zero risk. |
| Rename sanitize_csv_cell for dual-use clarity | **FIX** | Function is now used at both import and export. Rename to `sanitize_dangerous_chars()` and update the docstring. 3 call sites. |

### Unverified (Resolved)

| Item | Status | Evidence |
|------|--------|----------|
| Opener benchmark on real data | **RESOLVED** | 5/5 pass on scraped leads (Sentakku, Greenbook, Packt, Mehmet, LearneRRing) |
| --limit default (50) calibration | **KEEP DEFAULT** | 663 leads scraped, 50 classified in 2 runs, no cost issues. 50 is a good batch size for API-calling enrichment steps. Revisit only if running full pipeline on 1000+ leads. |

## Phase 3 Scope

Two items survive triage:

1. **Null byte stripping** -- add `\x00` to strip list in sanitize function (1 line)
2. **Rename sanitize_csv_cell** -- rename to `sanitize_dangerous_chars()`, update 3 call sites (utils.py, ingest.py, app.py), update 1 test import

Both are zero-risk, zero-behavior-change refactors. Combined: ~10 lines changed.

## Should This Be a Full Compound Cycle?

**No.** This is 10 lines across 4 files with no behavioral change. A full brainstorm -> plan -> work -> review -> compound cycle would produce more documentation than code. 

**Proposed approach:** Skip plan and review. Commit directly to master with tests. Update HANDOFF.md to reflect all deferrals resolved or explicitly won't-fixed.

## Items Explicitly Closed (Won't Fix / Defer)

These should be removed from HANDOFF.md's deferred list with clear rationale:

- Template caching: WON'T FIX (premature optimization, 5ms worst case)
- .env parser quoted values: WON'T FIX (use python-dotenv if needed)
- CSRF upgrade to Flask-WTF: DEFER until on-network deployment
- CSP headers: DEFER until on-network deployment

## Feed-Forward

- **Hardest decision:** Whether Phase 3 needs a full compound cycle. It doesn't -- 10 lines of zero-risk refactoring doesn't need 5-agent review.
- **Rejected alternatives:** Including CSRF/CSP upgrades (they're deployment-contingent, not code-quality items). Keeping template caching as deferred (it's premature optimization and should be explicitly won't-fixed).
- **Least confident:** Whether renaming `sanitize_csv_cell` to `sanitize_dangerous_chars` is the right name. The function strips control chars AND prefixes formula chars. Maybe `sanitize_cell_value` is clearer. Decide during implementation.
