---
status: pending
priority: p2
issue_id: "012"
tags: [code-review, architecture, usability]
---

# Add --step Flag to Enrich CLI Command

## Problem Statement
`cmd_enrich` runs all 5 enrichment steps unconditionally and sequentially. If you only need Hunter.io (because you just added websites), you wait through bio parsing, website fetching, deep crawling, and venue scraping first. Venue scraper alone has a 10-minute timeout.

## Findings
- **Source:** Architecture Strategist
- **File:** `run.py` lines 72-86

## Proposed Solution
Add `--step` argument: `python run.py enrich --step hunter`. Choices: bio, website, deep, venue, hunter, all (default).

## Acceptance Criteria
- [ ] `--step all` runs all 5 steps (default, backward compatible)
- [ ] `--step bio` runs only bio parsing
- [ ] `--step hunter` runs only Hunter.io
- [ ] Invalid step name shows error
