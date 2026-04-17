---
status: resolved
priority: p2
issue_id: "005"
tags: [code-review, security]
---

# SSRF blocklist missing IPv6 and only checks first DNS result

## Problem Statement
`_PRIVATE_NETWORKS` only has IPv4 ranges. Missing ::1/128, fc00::/7, fe80::/10. Also only checks `addr_info[0]`, not all results.

## Proposed Solution
Add IPv6 ranges. Iterate all getaddrinfo results.

## Acceptance Criteria
- [ ] IPv6 loopback and link-local are blocked
- [ ] All DNS results checked, not just the first
