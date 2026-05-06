# HANDOFF -- Venue Scraper

**Date:** 2026-05-05
**Branch:** master
**Phase:** Compound complete (cycle 2)

## Current State

Full pipeline implemented: SerpAPI search discovery -> smart link-based subpage crawling -> sanitized CSV outreach export. 81 tests passing. 4-agent review done, all P1/P2 findings fixed. Solution doc written.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | venue-scraper/docs/brainstorms/2026-05-05-venue-scraper-low-effort-upgrades-brainstorm.md |
| Plan (deepened) | venue-scraper/docs/plans/2026-05-05-feat-venue-scraper-search-discovery-csv-plan.md |
| Solution (cycle 1) | docs/solutions/2026-05-05-venue-scraper-llm-extraction-pipeline.md |
| Solution (cycle 2) | docs/solutions/2026-05-05-venue-scraper-search-discovery-csv-pipeline.md |

## Usage

```bash
# Search for SD film venues and export CSV
export SERPAPI_API_KEY=your_key
export ANTHROPIC_API_KEY=your_key
python scrape.py --search-film --csv --output results/

# Custom search query
python scrape.py --search "recording studios San Diego" --csv

# Existing URL file (still works)
python scrape.py urls.txt --csv
```

## Deferred Items

- Benchmark chunk_token_threshold (1500 vs 2000 vs 3000)
- Add TTL to SerpAPI disk cache (currently caches forever)
- Pipeline venue processing with asyncio.gather (50% faster, moderate refactor)
- Verify excluded_tags doesn't affect CrawlResult.links on live venues
- Integration with lead-scraper (venue data enriching lead records)

## Three Questions

1. **Hardest decision?** Additive vs exclusive fallback for subpage discovery. Chose additive.
2. **What was rejected?** Two-phase double-crawl, global networkidle, import-time key validation.
3. **Least confident about?** Whether excluded_tags affects link extraction. Additive fallback protects if wrong.

## Prompt for Next Session

```
Read venue-scraper/HANDOFF.md for context. This is venue-scraper, a search-to-CSV pipeline for finding venue contact info.
Cycle 2 complete. Next: get a SERPAPI_API_KEY and run it live on SD film venues for the May 30 workshop.
```
