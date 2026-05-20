---
title: Client Music Planner
date: 2026-05-19
status: complete
type: brainstorm
run: "048"
---

# Client Music Planner -- Brainstorm

## What We're Building

A two-sided portal where wedding/event musicians manage their repertoire and create shareable event portals for clients. Clients receive a unique link (no login required), browse the musician's song library with filters, build their event playlist with drag-and-drop ordering, flag must-play and do-not-play songs, submit song requests not in the repertoire, and approve the final timeline.

**Target user:** Solo freelance musician doing weddings, corporate events, parties.

**Moat:** Accumulated repertoire data is a switching cost. If multiple musicians adopt, clients start expecting the experience (network effect). Music-specific workflow only a musician would design correctly.

## Why This Approach

### Two-sided auth model (musician session + client token)

Musicians need persistent accounts to manage repertoire across events. Clients need zero-friction access -- no registration, no password. A token-based link (`/portal/<token>`) is the simplest model that achieves this. The token is a `secrets.token_urlsafe(32)` stored in the event row. No HMAC needed because the token is random, not derived from user data (FC19 does not apply -- that's for tokens encoding an ID).

**Why not PIN code?** PINs are short and guessable. A 32-byte URL-safe token has 256 bits of entropy. No rate-limiting needed at MVP scale.

**Why not magic link / email auth for clients?** Adds email infrastructure complexity. Clients just need to click a link the musician shares via text/email/WhatsApp.

### Repertoire as the core data asset

Songs are the central entity. Every feature flows from the song table: filtering, playlist building, must-play flags, export. The data model must be rich enough to be useful (key, tempo, genre, energy, duration) but not so complex that data entry is painful.

**Bulk CSV import** addresses the cold-start problem -- musicians have existing song lists in spreadsheets.

### Drag-and-drop playlist builder

SortableJS provides cross-browser drag-and-drop with a simple API. Position stored as integer in `playlist_item` table. On reorder, the client sends an array of item IDs in new order; the server updates positions in a single transaction.

**Parallel array desync risk (from recipe-organizer):** When the client sends `track_ids[]` and `positions[]` as separate arrays, `zip()` silently truncates if lengths differ. Must validate `len(track_ids) == len(positions)` before processing.

### Separation of song requests from repertoire

Client song requests go into a `song_request` table, not the main `song` table. This preserves repertoire integrity -- the musician's song library is curated; client requests are suggestions that may or may not be learnable. The musician sees requests alongside selections in the event dashboard.

## Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Token-based client access via `/portal/<token>` | Zero friction, no client accounts needed |
| 2 | `secrets.token_urlsafe(32)` for tokens | 256-bit entropy, no HMAC needed (random, not derived) |
| 3 | SortableJS for drag-and-drop | Proven library, simple API, works with vanilla JS |
| 4 | Separate `song_request` table | Preserves repertoire integrity |
| 5 | Position as integer in `playlist_item` | Simple, allows reorder via UPDATE batch |
| 6 | CSV bulk import for repertoire | Solves cold-start problem |
| 7 | Client approval = `event.client_approved` flag + timestamp | Simple binary state, no multi-step workflow |
| 8 | Post-approval read-only for client | Prevents accidental changes after musician prepares |
| 9 | Flask + SQLite + Jinja2 + Bootstrap 5 | Sandbox standard stack, proven at 16-agent scale |
| 10 | 18-20+ agent vertical blueprint split | Biggest swarm to date, extends run 047 pattern |

## Data Model (High Level)

### Tables

| Table | Owner | Purpose |
|-------|-------|---------|
| `user` | Musician | Auth, profile |
| `song` | Musician | Repertoire catalog |
| `event` | Musician | Event metadata + client token |
| `playlist_item` | Client (scoped to event) | Song selections with position, must_play/do_not_play flags |
| `song_request` | Client (scoped to event) | Songs not in repertoire |

### Data Ownership

| Data | Create | Read | Update | Delete |
|------|--------|------|--------|--------|
| user | Musician (register) | Musician (self) | Musician (self) | -- |
| song | Musician | Musician + Client (via event token) | Musician | Musician |
| event | Musician | Musician + Client (via token) | Musician (metadata) + Client (approval) | Musician |
| playlist_item | Client (via token) | Musician + Client | Client (reorder, flags) | Client (remove from playlist) |
| song_request | Client (via token) | Musician + Client | Client (edit note) | Client (retract) |

### Key Constraints

- Client can only see songs belonging to their event's musician
- Client can only modify playlist_items and song_requests for their specific event
- After client_approved=True, client-side writes are blocked
- Musician can see all events and all client selections
- Token lookup decorator validates event exists and is not expired/archived

## Blueprint Architecture (18-20 agents)

| # | Blueprint | Routes | Templates | Rationale |
|---|-----------|--------|-----------|-----------|
| 1 | core-infra | -- | -- | App factory, db.py, models, config, decorators, filters |
| 2 | auth | /auth/* | login, register | Musician authentication |
| 3 | layout-static | -- | base.html, navbar, footer | Shared layout + CSS + JS |
| 4 | repertoire | /repertoire/* | list, detail, form | Song CRUD for musician |
| 5 | repertoire-import | /repertoire/import | import form, preview | CSV bulk import |
| 6 | events | /events/* | list, detail, form | Event CRUD for musician |
| 7 | event-dashboard | /events/<id>/dashboard | dashboard | Musician views client selections |
| 8 | event-export | /events/<id>/export | export preview | CSV/print setlist export |
| 9 | portal-browse | /portal/<token> | browse, song detail | Client browses repertoire |
| 10 | portal-filters | /portal/<token>/filter | filter sidebar/AJAX | Genre/energy/search filtering |
| 11 | portal-playlist | /portal/<token>/playlist | playlist builder | Drag-and-drop playlist |
| 12 | portal-flags | /portal/<token>/flags | -- (AJAX) | Must-play / do-not-play toggles |
| 13 | portal-requests | /portal/<token>/requests | request form | Song requests |
| 14 | portal-approve | /portal/<token>/approve | confirmation | Approval flow |
| 15 | portal-layout | -- | portal base, header | Client-side shared layout |
| 16 | dashboard | /dashboard | musician dashboard | Musician home with event summary |
| 17 | api-playlist | /api/playlist/* | -- | JSON endpoints for DnD reorder |
| 18 | api-filters | /api/filters/* | -- | JSON endpoints for AJAX filtering |
| 19 | tests | -- | -- | Test suite |
| 20 | seed-data | -- | -- | Sample data for development |

**Total: 20 agents** -- biggest swarm to date.

## Coordinated Behaviors (FC5 Prevention)

| Behavior | Pattern | All agents must follow |
|----------|---------|----------------------|
| Flash messages | `flash("message", "category")` where category is success/error/warning/info | Bootstrap alert with dismiss |
| Empty states | "No [items] yet. [Action link]." pattern | Consistent across all list views |
| Error display | Flash for form errors, JSON `{"error": "message"}` for API | Never expose stack traces |
| Date formatting | `event.date.strftime('%B %d, %Y')` | Jinja2 filter `|format_date` |
| Loading states | `.loading` CSS class on buttons during AJAX | Disable button + spinner icon |
| Token validation | `@require_portal_token` decorator | Returns 404 for invalid tokens (not 403) |
| Auth validation | `@login_required` decorator | Redirects to `/auth/login` |
| CSRF | Flask-WTF CSRFProtect on all forms | `{{ csrf_token() }}` in every form |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Token enumeration | Low | High | 256-bit random tokens, 404 on invalid (no info leak) |
| Parallel array desync in playlist | Medium | Medium | Length equality check before zip() |
| SortableJS CDN failure | Low | Medium | Bundle locally or use fallback manual ordering |
| Large repertoire performance | Low | Low | SQLite handles 10K songs fine; add pagination if needed |
| Client modifies after approval | Medium | Medium | Server-side check in decorator, not just UI hiding |
| Route prefix doubling | Medium | Medium | Spec prescribes relative paths (FC7) |
| Form field name mismatch | High | High | Spec prescribes exact WTForms field names (FC9) |

## Open Questions (Resolved)

All key decisions resolved during brief expansion:

1. **Client access method?** -- Token URL (decided: simplest, most friction-free)
2. **Drag-and-drop library?** -- SortableJS (decided: proven, simple API)
3. **Song requests vs repertoire?** -- Separate table (decided: preserves integrity)
4. **Approval flow complexity?** -- Binary flag (decided: simplest that works)
5. **Agent count?** -- 20 agents (decided: extends run 047 pattern)

## Feed-Forward

- **Hardest decision:** Token-based access is novel territory for this repo. No prior solution doc covers it. The `@require_portal_token` decorator is the critical security boundary -- if it's wrong, clients can see other musicians' data or modify other events. This decorator must validate: (1) token exists in event table, (2) event is not archived, (3) event is not past approval deadline. Every portal blueprint depends on it.
- **Rejected alternatives:** PIN codes (too guessable), magic links via email (adds email infrastructure), OAuth for clients (massive overkill for a link-sharing flow).
- **Least confident:** The drag-and-drop reorder persistence. SortableJS fires an `onEnd` event with the new order, but mapping that to a server-side batch UPDATE of position integers across multiple playlist_items in a single transaction -- while handling concurrent modifications if two browser tabs are open -- hasn't been done in this repo before. The parallel array desync check from recipe-organizer helps, but the full flow (drag end -> collect IDs in order -> POST to API -> validate -> UPDATE positions in transaction -> return success) needs careful spec prescription.

## Refinement Findings

**Gaps found:** 4 (all addressed in plan phase)

1. **Transaction Boundary Prescription for Multi-Step Writes** -- Spec must annotate every model function as "commits internally" or "does NOT commit -- caller commits." Three multi-step flows need atomic treatment: portal-approve, portal-flags (check post-approval first), api-playlist batch update. (Source: workshop-registration-hub FC29)

2. **Template Render Context Section is Non-Negotiable at 20 Agents** -- Flask swarm specs need ~20% of lines for exact `render_template()` variable names per route/template pair. Without this, portal agents will independently guess variable names and diverge. (Source: flask-swarm-acid-test, task-tracker-categories)

3. **Spec Consistency Checker Mandatory Before Launch** -- Pipeline gate at Step 9w.5. The 16-agent Command Center build found 3 cross-section contradictions in 1200 lines. A 20-agent spec will be larger. (Source: command-center run 047)

4. **Cross-Boundary Wiring Table with Exact Code Blocks** -- Data Ownership table is necessary but insufficient. Need exact function signatures, usage examples, and "who calls it and when" for: (a) portal-playlist writes that event-dashboard reads, (b) portal-approve writes that all portal blueprints check, (c) portal-flags writes that event-dashboard renders. (Source: invoice-crm run 046, project-tracker)
