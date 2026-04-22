# Lead Scraper -- Handoff

**Date:** 2026-04-21
**Branch:** `feat/v2-outreach-intelligence` (PR #3 against master)
**Tests:** 137/139 passing (2 pre-existing: missing anthropic module, flaky mock)
**Phase:** Compound complete -- ready for Phase 2

## What Was Done

### Phase 1: Implementation (11 commits)
Full outreach intelligence pipeline: segment classification (Claude Haiku 4.5), hook research (Perplexity Sonar Pro), campaign CRUD, message generation with opener LLM, queue review/approve/skip/sent workflow.

### Phase 1: Review (5-agent review)
Security Sentinel, Architecture Strategist, Performance Oracle, Code Simplicity Reviewer, Learnings Researcher. 17 findings: 3 P1, 7 P2, 7 P3.

### Phase 1: Review Fixes (10 commits)
All 3 P1s and 7 P2s fixed in cascade order. Solution doc: `docs/solutions/2026-04-21-v2-review-cascade-fixes.md`.

| Fix | Summary |
|-----|---------|
| 1 | Indexes on leads(segment, hook_quality) and outreach_queue(campaign_id, status) |
| 2 | .env.example with all 4 API key placeholders |
| 3 | Path traversal check in _read_template |
| 4 | Skip _persist_hook on 429 (tier=-1 sentinel) |
| 5 | Anti-injection warning in LLM system prompts |
| 6 | Remove dead campaigns.status column |
| 7 | Move _available_segments() + TEMPLATES_DIR to config.py |
| 8 | --limit flag (default 50) for segment/hook/generate |
| 9 | Batch DB connections (1 per loop, not 1 per lead) |
| 10 | Extract test helpers to tests/conftest.py (-156 lines) |

## Next Session: Phase 2

### P3s Deferred from Phase 1 Review

- CSV formula injection on import
- CSRF on Flask delete endpoint
- Cache templates in generate loop
- Extract _transition_status() helper
- CSV field map redundant keys
- CSV phone column warning
- .env parser quoted values

### Opener Benchmark (Verify-First from Phase 1 Feed-Forward)

The opener generation quality risk was flagged but never verified. Before expanding:

1. Run 5-lead benchmark with rubric: sounds like Alex, hook-specific, 1-2 sentences, opens conversation
2. If <4/5 pass, add voice guide examples to Haiku prompt
3. If 4+/5 pass, opener quality is validated for production use

### --limit Calibration

Default 50 needs testing with a real campaign. May need adjustment up (for batch) or down (for dev safety).

## Key Files

| File | Role |
|------|------|
| enrich.py | All enrichment steps (segment, hook, bio, website, hunter, venue) |
| campaign.py | Campaign CRUD, message generation, queue management |
| config.py | Config, API keys, TEMPLATES_DIR, available_segments() |
| models.py | Lead queries, held leads |
| run.py | CLI dispatcher |
| db.py | SQLite connection management, migration |
| tests/conftest.py | Shared setup_db fixture and insert_lead helper |

## Solution Docs

- `docs/solutions/2026-04-19-contact-enrichment-5-step-pipeline.md` -- Phase 1 enrichment patterns
- `docs/solutions/2026-04-21-v2-review-cascade-fixes.md` -- Review fix patterns (this phase)

## Feed-Forward

- **Hardest decision:** Cascade ordering vs. file-grouped batching for review fixes. Cascade won because behavioral fixes depended on schema being stable first.
- **Rejected alternatives:** Fixing P3s in the same pass (scope creep risk, diminishing returns on a PR already at 21 commits).
- **Least confident:** Opener generation quality. Gated by 5-lead benchmark with rubric. If benchmark fails, add voice guide examples to Haiku prompt. This is Phase 2's verify-first item.
