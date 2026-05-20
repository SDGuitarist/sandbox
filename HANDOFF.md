# HANDOFF -- Sandbox

**Date:** 2026-05-19
**Branch:** master
**Phase:** Ready for autopilot -- Client Music Planner (run 048)

## What To Do

Launch full autopilot run for the **Client Music Planner** -- a two-sided portal where musicians share a branded link with wedding/event clients, who browse the musician's repertoire, build their event playlist, flag must-plays and do-not-plays, and approve the timeline.

**This should be the biggest run to date (run 046 was 15 agents, run 047 was 16).**

### Concept

- **Musician side:** Manage repertoire (songs with key, tempo, genre, energy, duration), create shareable event portals per client, view client selections, export final setlist
- **Client side:** Browse musician's repertoire (filterable by genre/energy/mood), drag-and-drop playlist builder, flag must-play/do-not-play, add song requests not in repertoire, approve timeline, leave notes
- **Moat:** Accumulated repertoire data is a switching cost. If multiple musicians adopt, clients start expecting the experience (network effect). Music-specific workflow only a musician would design correctly.
- **Monetization:** Free for 1 active event, $15/mo unlimited events, $25/mo with analytics + branding

### Key Decisions for Brainstorm/Plan

1. Two-sided portal architecture (musician auth + client token-based access)
2. How clients access their portal (unique link with token? PIN code?)
3. Repertoire data model (songs, tags, categories, energy levels)
4. Playlist builder UX (drag-and-drop? checkbox? timeline slots?)
5. How many agents/blueprints -- target 18-20+ for biggest run
6. Flask + SQLite + Jinja2 (same stack as runs 046/047)

### Pre-Flight Status (verified this session)

| Check | Status |
|-------|--------|
| Git working tree | Clean |
| Stale branches | Pruned (30 -> 4) |
| Stale worktrees | Pruned |
| BUILD_TRACKING.md | Archived to command-center/ |
| Permissions | dangerouslySkipPermissions: true |
| Agent-pitfalls | Current (FC9, FC33, FC34 from run 046) |
| Parallel run risk | None (single session only) |

### Autopilot Launch Prompt

```
Read HANDOFF.md. This is the Sandbox project, launching run 048: Client Music Planner.

Target: biggest autopilot swarm to date (18-20+ agents). Two-sided portal --
musicians manage repertoire and create event portals, clients browse and build
playlists via shareable links.

Stack: Flask + SQLite + Jinja2 + Bootstrap 5 (same as runs 046/047).
No parallel sessions -- single autopilot run only (FC34 mitigation).

Run /autopilot for the full compound loop: brainstorm -> plan -> spec convergence
-> swarm work -> review -> compound -> learnings.
```

## Prior Runs (for context)

| Run | Project | Agents | Grade | Solution Doc |
|-----|---------|--------|-------|-------------|
| 046 | Invoice & CRM | 15 | B (3.8) | docs/solutions/2026-05-19-invoice-crm-15-agent-swarm-build.md |
| 047 | Command Center | 16 | A (4.5) | docs/solutions/2026-05-19-solopreneur-command-center-swarm-build.md |
| 045 | Feedback Board | 1 (solo) | A (4.5) | docs/solutions/2026-05-18-feedback-board-solo-build.md |

## Deferred Items From Prior Runs

### Run 046 (Invoice & CRM)
- 046-W1 ACCEPTED: No brute-force login protection. MEDIUM.
- 046-W2 ACCEPTED: Line-item parsing duplication. MEDIUM.
- P2s: no session regen, negative amounts, LIKE wildcards, no pagination

### Run 047 (Command Center)
- P3: CSV export duplication, form field names not prescribed
- Future: responsive design, email integration, calendar sync
