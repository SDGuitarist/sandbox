---
status: pending
priority: p3
issue_id: "046"
tags: [code-review, agent-native, brewops]
---

# No JSON API Endpoints (Agent-Native Gap)

## Problem Statement
The model layer is exemplary (40/40 functions are Flask-free and callable standalone), but no JSON API endpoints exist. All routes return HTML or redirects. An HTTP-based API consumer cannot interact without scraping HTML.

## Findings
- Agent-native reviewer: 0/40 HTTP-accessible, 40/40 model-callable
- Validation constants trapped in route files (not accessible to programmatic callers)

## Proposed Solution
Add `/api/v1/` blueprint with JSON endpoints. Since model functions are already Flask-free, each endpoint is ~5-10 lines. Low priority for a single-admin web app.

## Acceptance Criteria
- [ ] Documented as intentional (web-only app) or API added
