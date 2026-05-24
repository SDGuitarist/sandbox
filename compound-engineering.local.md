# Review Context -- Sandbox (Habit Tracker Web)

## Risk Chain

**Brainstorm risk:** "Whether the weekly calendar UI will feel intuitive for toggling completions on past dates."

**Plan mitigation:** Weekly calendar with CSS Grid, per-cell mini-form POSTs, visual states (green/gray/dimmed). Backfill constraint: within current week only.

**Deepen resolution:** 5 research agents. Anchor redirect pattern found for scroll preservation. ARIA grid roles added. ON CONFLICT DO NOTHING replaced INSERT OR IGNORE. WTF_CSRF_TIME_LIMIT=None prevents stale-page 400s.

**Work risk (from Feed-Forward):** "Whether the CSS Grid calendar with mini-form buttons will feel responsive and not 'jumpy' when toggling."

**Review resolution:** Codex found 2 P1, 0 P0, 0 P2. Both P1s fixed (toggle path parity + week-boundary validation). Clean re-review.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/blueprints/habits/routes.py | Toggle routes, calendar view | P1 fix area -- toggle_date preconditions |
| app/templates/calendar.html | ARIA grid, anchor IDs | ARIA roles may over-promise keyboard nav |
| app/models.py | ON CONFLICT toggle, streaks | Core business logic |
| app/__init__.py | CSRF time limit, security headers | Security config |

## Plan Reference

`docs/plans/2026-05-23-feat-habit-tracker-web-plan.md`
