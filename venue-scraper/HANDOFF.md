# HANDOFF — Venue Scraper

**Date:** 2026-05-05
**Branch:** master
**Phase:** Compound complete (cycle 1)

## Current State

LLM-based venue scraping pipeline is fully functional. Uses Crawl4AI + Anthropic Claude for structured extraction from arbitrary venue websites. Multi-page crawling (homepage + /contact + /about) with merge. Cost controls in place. Solution doc written.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Solution | docs/solutions/2026-05-05-venue-scraper-llm-extraction-pipeline.md |
| Tests | venue-scraper/tests/test_models.py (20 fixture-based tests) |
| Results | venue-scraper/results/ |

## Review Fixes Pending

- No formal multi-agent review conducted yet (opportunity for Cycle 2)
- chunk_token_threshold optimization (currently 2000, unvalidated)
- Non-standard contact paths (/get-in-touch, /inquiries) may miss ~10% of venues

## Deferred Items

- Benchmark chunk_token_threshold values (1500 vs 2000 vs 3000) on 10 real venues
- Add /get-in-touch and /book-now to CONTACT_SUBPATHS if cost is acceptable
- Integration with lead-scraper (venue data enriching lead records)
- Rate limiting / retry logic for Anthropic API (currently relies on Crawl4AI defaults)

## Three Questions

1. **Hardest decision?** Trimming subpaths to 2. Risk of missing contact info on non-standard paths. Accepted 90/10 tradeoff for 70% cost savings.
2. **What was rejected?** Regex extraction (brittle), full-site crawl with link discovery (too expensive), OpenAI (less reliable structured output in testing).
3. **Least confident about?** chunk_token_threshold=2000 -- no benchmark data. Could be leaving accuracy or money on the table.

## Prompt for Next Session

```
Read venue-scraper/HANDOFF.md for context. This is venue-scraper, an LLM-based web scraper that extracts structured venue data using Crawl4AI + Anthropic.
Compound phase complete. Next: either run a formal review cycle, benchmark chunk sizes, or integrate with lead-scraper.
```
