---
status: resolved
priority: p2
issue_id: "008"
tags: [code-review, quality]
---

# No HTTP status code check before parsing response

## Problem Statement
A 404 or 500 response body gets parsed by BeautifulSoup, potentially extracting bogus emails from error pages.

## Proposed Solution
Add `if resp.status_code != 200: return None` after the GET in `_fetch_page`.

## Acceptance Criteria
- [ ] Non-200 responses are not parsed
