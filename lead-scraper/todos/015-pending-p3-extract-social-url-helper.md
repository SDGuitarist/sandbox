---
status: pending
priority: p3
issue_id: "015"
tags: [code-review, quality]
---

# Extract Shared Social URL Parsing Helper

## Problem Statement
Social URL to `"platform:handle"` conversion is duplicated in `enrich_websites_deep` (lines 351-368) and `enrich_with_venue_scraper` (lines 685-698). Nearly identical code parsing Instagram/Twitter/LinkedIn/Facebook URLs.

## Findings
- **Source:** Architecture Strategist + Simplicity Reviewer

## Proposed Solution
Extract `normalize_social_urls(urls: list[str]) -> list[str]` into `enrich_parsers.py`. Both callers shrink to one line. ~25 LOC saved.

## Acceptance Criteria
- [ ] Single function for social URL normalization
- [ ] Both callers use the shared function
- [ ] Tests cover each platform (Instagram, Twitter, LinkedIn, Facebook, TikTok)
