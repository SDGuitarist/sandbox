---
status: pending
priority: p3
issue_id: "017"
tags: [code-review, quality]
---

# Fix Domain Substring Matching False Positives

## Problem Statement
In `enrich_websites_deep()`, domain-to-lead matching uses `if domain and domain in url` (line 332). This is a substring match that can false-match: domain "bar.com" would match URL "https://foobar.com/about".

## Findings
- **Source:** Performance Oracle + Architecture Strategist
- **File:** `enrich.py` line 332

## Proposed Solution
Use `_extract_domain(url)` to compare domains exactly instead of substring matching.

## Acceptance Criteria
- [ ] Domain matching uses exact comparison
- [ ] "bar.com" does NOT match "foobar.com"
