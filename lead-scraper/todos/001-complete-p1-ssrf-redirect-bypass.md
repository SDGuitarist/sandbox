---
status: resolved
priority: p1
issue_id: "001"
tags: [code-review, security]
---

# SSRF: Redirect bypass in _fetch_page

## Problem Statement
`_fetch_page` uses `allow_redirects=True`, so a URL that passes `_is_safe_url` can redirect to a private IP (127.0.0.1, 169.254.169.254). The redirect target is never validated.

## Findings
- **Python reviewer**: P1 — classic SSRF bypass pattern
- **Security sentinel**: P1 — DNS rebinding + redirect bypass
- **Architecture strategist**: P2 — TOCTOU gap

## Proposed Solution
Set `allow_redirects=False`, validate redirect target before following.

## Acceptance Criteria
- [ ] `_fetch_page` does not follow redirects to private IPs
- [ ] Test: URL redirecting to 127.0.0.1 returns None
