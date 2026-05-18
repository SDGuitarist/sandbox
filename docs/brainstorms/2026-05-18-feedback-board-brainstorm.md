---
title: "Feedback Board"
type: brainstorm
date: 2026-05-18
status: complete
---

# Feedback Board -- Brainstorm

## What We're Building

A lightweight feedback/suggestion board where anonymous users submit ideas and upvote others' suggestions. A single admin manages the board through a basic-auth-protected dashboard with status tracking and filtering.

**Target user:** Single admin collecting feedback from anonymous visitors (workshop attendees, beta testers, etc.)

**Scale:** Small (dozens of items, not thousands). No pagination needed for MVP.

## Why This Approach

**Flask + SQLite + Jinja2** is the sandbox standard stack. No external APIs needed -- everything runs locally. This keeps the build fully autonomous (no API keys, no Supabase, no third-party services).

**Server-rendered with Jinja2** instead of a separate frontend (Express/EJS) because:
- Single stack = simpler deployment and fewer integration seams
- No cross-stack API contract needed (avoids FC28, FC30)
- Jinja2 auto-escapes HTML by default (mitigates XSS without manual html.escape())
- Flask-WTF provides built-in CSRF protection on forms

**Anonymous submission** (no user accounts) because:
- Lowest friction for feedback collection
- Upvote dedup via IP address is sufficient at workshop scale
- User accounts are a Phase 2 feature if needed

## Key Decisions

### 1. Status State Machine

```
new -> planned -> in_progress -> done
```

Four statuses, forward-only transitions (admin can set any status, no enforcement of ordering). Simplest model that captures the lifecycle.

**Valid statuses:** `new`, `planned`, `in_progress`, `done` (underscored everywhere, including DB CHECK, routes, and templates)

### 2. Upvote Deduplication

One upvote per IP per feedback item. Use `BEGIN IMMEDIATE` transaction for atomic check-and-insert (same pattern as workshop-registration capacity check). Store IP + feedback_id in a `votes` table with UNIQUE constraint.

**Why IP-based:** No user accounts in MVP. Cookie-based is trivially bypassed. IP is good enough at workshop scale.

**Duplicate upvote behavior:** Use `INSERT OR IGNORE` on the UNIQUE(feedback_id, ip_address) constraint. If no row inserted (`cursor.rowcount == 0`), skip vote_count increment. No error shown to user -- the upvote button simply does nothing on re-click. No visual indication of "already voted" in MVP.

### 3. Categories

Fixed list: `Feature`, `Bug`, `Improvement`, `Other`. Stored as TEXT with CHECK constraint. Admin can filter by category.

### 4. Admin Authentication

Basic HTTP auth (same pattern as workshop-registration admin). Password from `ADMIN_PASSWORD` env var. Brute-force protection: track failed attempts per IP, lock out after 5 failures in 60 seconds.

### 5. Architecture

Single Flask app with blueprints:
- `public_bp` (url_prefix="/") -- submission form, feedback list, upvote
- `admin_bp` (url_prefix="/admin") -- dashboard, status updates, CSV export
- Health endpoint inline in app factory

No separate API -- forms POST directly to Flask routes, which redirect back. Standard PRG (Post-Redirect-Get) pattern.

### 6. Database Schema (Sketch)

Two tables:
- `feedback` -- id, title, description, category, status, vote_count, ip_address, created_at, updated_at
- `votes` -- id, feedback_id (FK), ip_address, created_at, UNIQUE(feedback_id, ip_address)

`vote_count` is denormalized on the feedback row for fast display. Updated atomically in the same transaction as the vote insert. `updated_at` tracks when admin last changed the status.

### 6b. Validation Rules

| Field | Required | Type | Constraints | Error Message |
|-------|----------|------|-------------|---------------|
| title | yes | string | 1-200 chars, trimmed | "Title is required (max 200 characters)" |
| description | no | string | max 2000 chars, trimmed | "Description must be under 2000 characters" |
| category | yes | enum | Feature, Bug, Improvement, Other | "Please select a category" |

Server-side validation in the route handler. On failure, re-render the form with flash messages and preserved input.

### 6c. IP Handling

Use `request.remote_addr` for local dev. Add `ProxyFix(app, x_for=1)` for production behind a reverse proxy. IP is used for upvote dedup and brute-force protection. IP is NOT shown in the admin dashboard (privacy default).

### 6d. Rate Limiting

`flask-limiter` on public submission: 10 per minute per IP. Admin endpoints: 60 per minute per IP (default). Same pattern as workshop-registration.

### 6e. Database Initialization

`init_db()` in app factory reads `schema.sql` and executes it. Same pattern as prior sandbox Flask apps.

### 6f. Health Endpoint

`GET /health` returns `{"status": "ok", "db": "connected"|"disconnected"}`. Inline in app factory.

### 6g. CSS Approach

Single `style.css` file in `static/css/`. Clean, minimal custom CSS (same approach as workshop-registration). No CSS framework.

### 6h. CSV Export

Exports ALL feedback (ignores current filters). Includes: id, title, description, category, status, vote_count, created_at, updated_at. Excludes: ip_address (privacy). Filename: `feedback-export.csv`. Content-Type: `text/csv`.

### 6i. Admin Dashboard

Sorted by created_at descending (newest first). Filters via query parameters: `GET /admin?status=new&category=Bug`. Filters combine with AND logic. Empty filter = show all. Filter selections preserved after status update redirect.

### 6j. Brute-Force Lockout

In-memory dict (resets on restart, fine for MVP). Sliding window: prune attempts older than 60 seconds, block if 5+ recent failures. Return HTTP 429 with `Retry-After: 60` header. Legitimate admin recovers by waiting 60 seconds.

### 7. Template Structure

- `base.html` -- shared layout (nav, CSS)
- `index.html` -- feedback list with upvote buttons + submission form
- `admin/dashboard.html` -- filterable table with status dropdowns
- `admin/login.html` -- not needed (browser basic auth dialog handles it)

### 8. CSRF Protection

Flask-WTF CSRFProtect on all POST forms. The upvote button is a mini-form with a hidden CSRF token, not a bare link.

## Scope Boundaries

**In scope:**
- Submit feedback (title, description, category)
- List all feedback sorted by votes (descending) then date
- Upvote (one per IP per item)
- Admin: view all, filter by status/category, update status
- Admin: CSV export
- Health endpoint
- CSRF protection, brute-force protection, input validation

**Out of scope (Phase 2+):**
- User accounts, comments, search, pagination, email notifications
- Edit/delete feedback (admin can only change status)
- Rich text / markdown in descriptions

## Lessons Applied

| Lesson | Source | How Applied |
|--------|--------|-------------|
| CSRF on all POST forms | shared-spec-flask template, FC4 | Flask-WTF CSRFProtect |
| SECRET_KEY from env | autopilot-swarm-orchestration | `os.environ.get()` |
| Data ownership table | chain-reaction-contracts | One writer per table in spec |
| Route prefix doubling | FC7 | Routes relative to blueprint prefix |
| Brute-force protection | workshop-registration P2 | Failed-attempt tracker on admin auth |
| HTML-escape user content | workshop-registration bug | Jinja2 autoescaping (default) |
| Atomic operations | workshop-registration capacity | BEGIN IMMEDIATE for upvote dedup |
| Fail-closed auth | FC10 | 401 on any auth error, never pass-through |

## Resolved Questions (from refinement review)

1. **Duplicate upvote UX:** INSERT OR IGNORE, skip increment, no error shown (Decision 2)
2. **Validation rules:** Title required 1-200, description optional max 2000, category from enum (Decision 6b)
3. **Status spelling:** `in_progress` everywhere, underscored (Decision 1)
4. **Lockout mechanics:** Sliding window, in-memory, 429 response (Decision 6j)
5. **IP handling:** ProxyFix for production, not shown in admin (Decision 6c)
6. **CSV export scope:** All feedback, excludes IP (Decision 6h)
7. **Sort tiebreaker:** Public: votes desc then created_at desc. Admin: created_at desc (Decisions 5, 6i)

## Feed-Forward

- **Hardest decision:** Whether to use a separate API (Flask backend + Express frontend) or server-rendered Jinja2. Chose Jinja2 for simplicity -- eliminates cross-stack failure classes (FC28, FC30) entirely.
- **Rejected alternatives:** Separate Express frontend (adds complexity without benefit at this scale), cookie-based upvote dedup (trivially bypassed), free-text categories (harder to filter).
- **Least confident:** Whether the denormalized `vote_count` column stays consistent under concurrent upvotes. The BEGIN IMMEDIATE transaction should handle it, but if two requests hit simultaneously with different IPs, SQLite's write serialization is the safety net. First live test will confirm.
