---
status: resolved
priority: p1
issue_id: "004"
tags: [code-review, quality]
---

# Social URL parsing in enrich_parsers.py is dead code

## Problem Statement
`social_urls`, `SOCIAL_DOMAINS`, `_SHARE_PATTERNS`, JSON-LD sameAs parsing — 80+ lines of code that extract data which is never consumed. No column stores it, enrich.py only reads emails and phones.

## Proposed Solution
Remove social_urls from ParsedContactInfo, remove SOCIAL_DOMAINS, _SHARE_PATTERNS, all social-link parsing, JSON-LD block, and 4 associated tests. Cuts enrich_parsers.py from 115 to ~50 lines.

## Acceptance Criteria
- [ ] enrich_parsers.py only extracts emails and phones
- [ ] No unused data structures remain
- [ ] Tests updated to match
