---
status: resolved
priority: p2
issue_id: "006"
tags: [code-review, configuration]
---

# Incomplete .env.example

## Problem Statement
`.env.example` is missing critical variables: `ADMIN_PASSWORD`, `WORKSHOP_PRICE_CENTS`, `WORKSHOP_CAPACITY`, `FLASK_API_URL`, `SUPABASE_ANON_KEY`, `SQUARE_REDIRECT_BASE`, `EXPRESS_PORT`.

## Proposed Solution
Update `.env.example` to list ALL env vars used across both Flask and Express stacks.

## Acceptance Criteria
- [x] Every `os.environ.get()` and `process.env.*` call has a corresponding entry in `.env.example`
