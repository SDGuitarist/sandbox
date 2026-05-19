# HANDOFF -- Sandbox

**Date:** 2026-05-19
**Branch:** master
**Phase:** Compound complete -- Invoice & CRM (run 046)

## Current State

Invoice & CRM application built via 15-agent swarm autopilot (run 046). Largest
swarm build to date. 80 files, ~6,000 lines, 37 tests, 0 merge conflicts.
Flask + SQLite + Jinja2 with 12 blueprints covering auth, CRM, invoicing,
payments, reports, and global search.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/invoice-crm.md |
| Plan | docs/plans/invoice-crm-plan.md |
| Solution | docs/solutions/2026-05-19-invoice-crm-15-agent-swarm-build.md |
| BUILD_TRACKING | invoice-crm/BUILD_TRACKING.md |
| Reports | docs/reports/046/ |
| Self-Audit | docs/reports/046/self-audit.md |
| App Code | invoice-crm/ |

## Deferred Items

- [046-D1] Full multi-agent review not run (review was inline during assembly)
- [046-D2] PDF invoice export (v2 feature, out of scope for MVP)
- [046-D3] Email sending (v2 feature)
- [046-D4] Multi-user / team features (v2)
- [046-D5] Online payment processing (v2)
- [045-W1] 4 of 7 P3 review findings untracked from feedback board run
- [043-W1] Opening tag escaping in escape.ts (pre-existing, WRC)
- [043-W3] PATCH endpoint for editing voice overrides (WRC next iteration)

## Three Questions

1. **Hardest decision?** Whether to use 15 thin agents or 10 merged agents. 15 thin agents with blueprint-scoped templates resulted in zero merge conflicts.
2. **What was rejected?** Merging blueprints (would share template dirs, causing conflicts), monolith build (user requested 15+ agents), background jobs for recurring/overdue (overkill for MVP).
3. **Least confident about?** The test agent's ability to match exact form field names without reading the route code. 4/37 tests failed on naming mismatches. Future builds should include field names in test agent brief.

## Prompt for Next Session

```
Read HANDOFF.md and docs/solutions/2026-05-19-invoice-crm-15-agent-swarm-build.md.
Invoice & CRM app (run 046) is complete. 37/37 tests pass.
The app is at invoice-crm/. Run with: cd invoice-crm && .venv/bin/python run.py

Options:
1. Run full /workflows:review for comprehensive code review
2. Add deferred features (PDF export, email)
3. Start a new project
```
