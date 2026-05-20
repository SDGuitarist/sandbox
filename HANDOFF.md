# HANDOFF -- Sandbox

**Date:** 2026-05-19
**Branch:** master
**Phase:** Ready for autopilot -- VenueConnect (run 049)

## What To Do

Launch full autopilot run for **VenueConnect** -- a three-sided venue booking and settlement platform for the live music industry. Venues list available dates/rooms, musicians request bookings, promoters manage events. After the show, the system generates settlement sheets with door splits.

**This should be the biggest and most complex run to date (run 048 was 20 agents). Target 22-25 agents.**

### Concept

- **Venue side:** Manage rooms/stages, set availability windows, view booking requests, approve/reject, upload stage plots, generate settlement sheets post-show
- **Musician side:** Search venues (FTS5), browse availability calendar, request bookings, view contracts, track payment status, manage band profile
- **Promoter side:** Create events across venues, manage ticket tiers, oversee booking lifecycle, view settlement calculations, analytics dashboard
- **Booking lifecycle (state machine):** available -> requested -> confirmed -> advanced -> performed -> settled -> paid
- **Moat:** Settlement sheet automation (who gets what after the show) is the #1 pain point. Every venue currently does this with spreadsheets.

### Key Decisions for Brainstorm/Plan

1. Three-role multi-tenant architecture (venue manager, musician, promoter) -- first sandbox build with RBAC
2. Calendar with time-slot conflict detection (double-booking prevention)
3. Booking state machine (7 states, guarded transitions)
4. PDF generation for contracts + settlement sheets (weasyprint or reportlab)
5. FTS5 full-text search for venues (name, location, capacity, genre)
6. Financial calculations (guarantee vs door split, ticket tiers, promoter fee %, tax)
7. In-app notification system (read/unread)
8. Chart.js analytics (venue revenue by month, genre distribution, occupancy rate)
9. Flask + SQLite + Jinja2 + Bootstrap 5 (same stack as runs 046-048)
10. How many agents/blueprints -- target 22-25 for biggest run

### Untested Patterns (novel for sandbox pipeline)

| Pattern | Status | Why it matters |
|---------|--------|---------------|
| Multi-tenant with 3 roles | Never tested | Permission logic across roles is the hardest spec surface |
| Calendar with conflict detection | Never tested | Time-slot math + double-booking prevention |
| Complex state machine (7 states) | Never tested | Only binary flags in prior builds |
| PDF generation | Never tested | New library (weasyprint/reportlab) |
| FTS5 full-text search | Never tested | All prior builds use LIKE |
| Financial calculations | Partially (invoice line items) | Door splits, guarantees, percentages |
| In-app notifications | Never tested | Read/unread state management |
| Chart.js integration | Never tested | Data visualization |

### Pre-Flight Checklist (do at start of next session)

- [ ] Verify git working tree is clean
- [ ] Verify dangerouslySkipPermissions: true in .claude/settings.local.json
- [ ] Archive BUILD_TRACKING.md to client-music-planner/
- [ ] Copy autopilot-tracking-template.md to BUILD_TRACKING.md
- [ ] Read agent-pitfalls.md (current through run 048)
- [ ] No parallel sessions (FC34 mitigation)

### Autopilot Launch Prompt

```
Read HANDOFF.md. This is the Sandbox project, launching run 049: VenueConnect.

Target: biggest and most complex autopilot swarm to date (22-25 agents).
Three-sided platform -- venues, musicians, promoters. 7-state booking lifecycle,
calendar with conflict detection, PDF generation, FTS5 search, financial
calculations, notifications, charts.

Stack: Flask + SQLite + Jinja2 + Bootstrap 5 (same as runs 046-048).
No parallel sessions -- single autopilot run only (FC34 mitigation).

Run /autopilot for the full compound loop: brainstorm -> plan -> spec convergence
-> swarm work -> review -> compound -> learnings.
```

## Prior Runs (for context)

| Run | Project | Agents | Grade | Solution Doc |
|-----|---------|--------|-------|-------------|
| 048 | Client Music Planner | 20 | B (4.2) | docs/solutions/2026-05-19-client-music-planner-20-agent-swarm-build.md |
| 047 | Command Center | 16 | A (4.5) | docs/solutions/2026-05-19-solopreneur-command-center-swarm-build.md |
| 046 | Invoice & CRM | 15 | B (3.8) | docs/solutions/2026-05-19-invoice-crm-15-agent-swarm-build.md |
| 045 | Feedback Board | 1 (solo) | A (4.5) | docs/solutions/2026-05-18-feedback-board-solo-build.md |

## Deferred Items From Prior Runs

### Run 048 (Client Music Planner)
- 048-W1: create_event notes gap (MEDIUM, spec gap -- not code bug)
- 048-D1 through D7: ALL RESOLVED in post-run P2 fix commit (b5308dc)

### Run 046 (Invoice & CRM)
- 046-W1 ACCEPTED: No brute-force login protection. MEDIUM.
- 046-W2 ACCEPTED: Line-item parsing duplication. MEDIUM.
