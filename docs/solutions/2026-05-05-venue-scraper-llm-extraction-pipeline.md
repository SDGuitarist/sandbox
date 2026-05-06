---
title: Venue Scraper -- LLM-Based Structured Web Extraction Pipeline
date: 2026-05-05
tags: [crawl4ai, llm-extraction, pydantic, web-scraping, cost-control, anthropic]
problem: Extract structured venue data (contact, capacity, pricing, amenities) from arbitrary venue websites without site-specific parsers
outcome: Working pipeline that crawls venue websites + subpages, extracts structured data via LLM, merges multi-page results, and exports JSON/JSONL
difficulty: medium
reuse_potential: high
---

## Problem

Venue websites have no standard structure. Traditional scraping (CSS selectors, XPath) requires per-site maintenance. We needed a scraper that works on any venue site out of the box, extracting structured business intelligence (contact info, capacity, pricing, amenities) without writing site-specific code.

## Solution

**Architecture:** Crawl4AI (async browser-based crawler) + Anthropic Claude as the extraction LLM + Pydantic for output validation.

### Key Design Decisions

**1. LLM extraction with strict schema**

Crawl4AI's `LLMExtractionStrategy` takes a Pydantic JSON schema and an instruction prompt. The LLM returns structured JSON matching the schema. Pydantic validates at runtime -- if the LLM hallucinates a field type, it gets caught.

```python
# Co-locate prompt with schema (they change together)
EXTRACTION_PROMPT = """Extract venue information from this page.
Rules:
- Return null for any field not explicitly stated. Never guess.
..."""

strategy = LLMExtractionStrategy(
    schema=VenueData.model_json_schema(),
    extraction_type="schema",
    instruction=EXTRACTION_PROMPT,
    input_format="markdown",
)
```

**2. Multi-page crawl + merge pattern**

Contact info often lives on /contact or /about, not the homepage. Solution: crawl base URL + 2 subpaths, then merge results.

Merge rules:
- Scalar fields: first non-null wins (homepage takes priority)
- List fields (amenities, social_links): union with dedup, preserve order

This is the venue-scraper equivalent of a "fan-out then reduce" pattern.

**3. Cost control (critical for LLM-based scraping)**

Without controls, each venue costs ~$0.15-0.30 in API calls (3 pages x chunked extraction). Mitigations:
- Trimmed CONTACT_SUBPATHS from 8 to 2 (/contact, /about) -- covers ~90% of contact pages, 70% cost reduction
- 15 URL cap per run (prevents accidental $50 bills)
- `chunk_token_threshold=2000` with 0.1 overlap -- balances accuracy vs token usage
- `excluded_tags=["nav", "footer", "aside", "header"]` -- reduces page noise before LLM sees it
- `CacheMode.BYPASS` -- prevents silent LLM skip on cache hits (Crawl4AI bug #1455)

**4. Validation layer separates concerns**

`validate_extraction()` is the single point where raw LLM output becomes typed data. Handles: string JSON, dict, list (takes first element), and all error cases return None. This makes the function independently testable with JSON fixtures -- zero API calls in tests.

## Problems Encountered & Fixed

| Problem | Root Cause | Fix |
|---------|-----------|-----|
| Proxy auth failed in Crawl4AI | chromium-headless-shell needs persistent-context path, not launch args | Use `BrowserConfig` persistent context path |
| Empty extractions on some sites | Markdown extraction returned empty string | HTML fallback when markdown is empty |
| Runaway costs during development | 8 subpaths per URL, no URL limit | Trim to 2 subpaths + 15 URL cap |
| Crawl4AI returning cached empty results | Cache hit returns previous (empty) result | `CacheMode.BYPASS` on every run |

## Testing Strategy

Fixture-based tests with zero live API calls:
- `tests/fixtures/venue_complete.json` -- happy path with all fields
- `tests/fixtures/venue_minimal.json` -- only name
- `tests/fixtures/venue_missing_name.json` -- fails validation (name is required)

Tests cover: schema validation, list/string/dict input handling, URL validation, config assertions (cache bypass, concurrency limit, wait strategy).

## Reuse Patterns

This pipeline pattern (Crawl4AI + LLM + Pydantic) works for any "extract structured data from unstructured websites" problem:
1. Define a Pydantic model for your target schema
2. Write an extraction prompt co-located with the schema
3. Use `validate_extraction()` as your safety net between LLM output and your app
4. Multi-page crawl + merge when data is distributed across subpages
5. Always cap: URLs per run, subpaths per URL, tokens per chunk

## Feed-Forward

- **Hardest decision:** Trimming subpaths to just 2. Risk of missing contact info on sites that use non-standard paths (e.g., /get-in-touch, /inquiries). Accepted the 90/10 tradeoff for cost savings.
- **Rejected alternatives:** (a) Regex-based extraction (too brittle), (b) Full-site crawl with link discovery (too expensive), (c) OpenAI instead of Anthropic (Anthropic's structured output was more reliable in testing).
- **Least confident:** Whether `chunk_token_threshold=2000` is optimal. Larger chunks give better context but cost more. No systematic benchmark yet.
