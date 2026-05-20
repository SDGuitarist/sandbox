---
review_agents:
  - security-sentinel
  - performance-oracle
  - architecture-strategist
  - data-integrity-guardian
---

# Review Context -- Lead-Scraper x Venue-Scraper Cross-Pollination

## Risk Chain

**Brainstorm risk:** Phase 3 source dispatch refactor -- `_merge_sources()` can overwrite type field via `sources.overrides.json`

**Plan mitigation:** `_NON_OVERRIDABLE_FIELDS = {"type"}` set in config.py, `_merge_sources()` skips keys in this set, two named tests required

**Work risk (from Feed-Forward):** `screen_leads()` can overwrite `email_domain_mismatch` reason when a lead also fails a screening check, making `clear_domain_mismatch()` unable to find it later

**Review resolution:** 4-agent review found 3 P0 + 4 P1. All 7 fixed. Top findings: broken cost cap (tokens never counted), missing DB lock registrations, domain mismatch check on wrong email. Feed-forward dispatch risk confirmed resolved (4 guard tests pass).

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| enrich.py | LLM extraction loop, force_enriched_at, screen_leads mismatch guard | Cost control, hold system interactions |
| config.py | type field on all sources, _NON_OVERRIDABLE_FIELDS | Dispatch routing |
| run.py | Type dispatch, delete-source, clear-mismatch, --max-cost | DB lock registration |
| models.py | delete_source(), clear_domain_mismatch(), query_held_leads() | Cascade delete safety, hold visibility |
| scrapers/venue_csv.py | CSV normalization, http->https | URL scheme mismatch |
| scrapers/google.py | SerpAPI + LLM extraction pipeline | SSRF trust boundary |
| venue-scraper/db.py | SQLite backend, upsert, outreach status | Transaction safety |

## Plan Reference

`docs/plans/2026-05-19-feat-cross-pollination-lead-venue-integration-plan.md`
