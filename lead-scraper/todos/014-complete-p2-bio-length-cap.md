---
status: pending
priority: p2
issue_id: "014"
tags: [code-review, security]
---

# Add Bio Text Length Cap Before Regex Processing

## Problem Statement
`parse_bio()` runs regex on user-controlled bio text with no input length limit. A crafted bio of several hundred KB could cause elevated processing time (ReDoS). Bio text comes from scraped social media profiles.

## Findings
- **Source:** Security Sentinel
- **File:** `enrich_parsers.py` line 77 (`parse_bio` function)

## Proposed Solution
Add `text = text[:10_000]` at the top of `parse_bio()`. 10KB is generous for any bio.

## Acceptance Criteria
- [ ] `parse_bio()` truncates input to 10,000 chars before regex
- [ ] Existing tests pass
