---
status: resolved
priority: p2
issue_id: "008"
tags: [code-review, cleanup]
---

# Dead layout.ejs + Unused compression Package

## Problem Statement
1. `frontend/views/admin/layout.ejs` is a dead file -- dashboard.ejs is self-contained
2. `compression` is in package.json but never imported/used in app.js

## Proposed Solution
1. Delete layout.ejs
2. Add `const compression = require('compression'); app.use(compression())` to app.js after helmet

## Acceptance Criteria
- [ ] layout.ejs removed
- [ ] compression middleware active in app.js
