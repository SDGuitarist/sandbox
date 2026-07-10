---
status: resolved
priority: p2
issue_id: "007"
tags: [code-review, security]
---

# Flask Binds to 0.0.0.0 Instead of 127.0.0.1

## Problem Statement
`run.py:6` binds Flask to all interfaces. Since Express proxies to Flask, Flask should only listen on localhost.

## Proposed Solution
Change to `app.run(host='127.0.0.1', port=5000, threaded=True)`.

## Acceptance Criteria
- [ ] Flask binds to 127.0.0.1 only
