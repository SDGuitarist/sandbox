---
status: resolved
priority: p2
issue_id: "006"
tags: [code-review, performance]
---

# enrich_parsers.py parses HTML 3 times

## Problem Statement
Three separate BeautifulSoup instances from the same HTML: SoupStrainer("a"), full parse, SoupStrainer("script"). A single full parse suffices.

## Proposed Solution
Parse once with `BeautifulSoup(html, "lxml")`. Extract links, text emails, and JSON-LD from the same tree.

## Acceptance Criteria
- [ ] Single BS4 parse per page
- [ ] All existing tests still pass
