---
status: resolved
priority: p1
issue_id: "002"
tags: [code-review, cross-stack, frontend]
---

# Admin Dashboard Broken: Wrong Field Names + Helmet CSP Blocks Scripts

## Problem Statement
The admin dashboard is non-functional due to two issues:

1. **renderStats() reads wrong field names** (`frontend/views/admin/dashboard.ejs:72-84`): Reads `data.paid` but Flask returns `data.paid_count`. Reads `data.pending` but Flask returns `data.pending_payment`. Stats always show 0.
2. **Helmet CSP blocks CDN and inline scripts** (`frontend/app.js:14`): Default Helmet CSP blocks `cdn.jsdelivr.net` (Supabase JS) and inline `<script>` blocks. Admin dashboard JS cannot execute.

## Findings
- Architecture review: P2-02, P2-03, P2-06
- Combined severity: P1 (dashboard completely broken)

## Proposed Solution

1. Fix `renderStats()` to use correct field names: `data.paid_count`, `data.waitlist_count`, derive `pending_payment` count from registrants array or add a separate fetch to `/api/admin/stats`
2. Configure Helmet CSP to allow `cdn.jsdelivr.net`, `'unsafe-inline'`, and Supabase WebSocket connections

## Acceptance Criteria
- [ ] Admin dashboard stats show correct counts
- [ ] Capacity meter fills correctly
- [ ] Supabase realtime connection works
- [ ] No CSP errors in browser console
