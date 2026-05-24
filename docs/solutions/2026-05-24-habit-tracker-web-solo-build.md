---
title: "Habit Tracker Web Solo Build"
date: 2026-05-24
run_id: "059"
type: feat
app: habit-tracker-web
tags: [flask, sqlite, calendar-ui, csrf, toggle-pattern, aria, streaks, solo-build]
plan: docs/plans/2026-05-23-feat-habit-tracker-web-plan.md
---

# Habit Tracker Web Solo Build

## What Was Built

Flask + SQLite + Jinja2 habit tracker with dashboard (streaks, today toggle) and weekly calendar view (ARIA grid, per-cell toggle). 14 files, 696 lines, 9 commits. Solo autopilot build with deepen phase (5 parallel research agents).

## Key Patterns That Worked

### 1. ON CONFLICT DO NOTHING over INSERT OR IGNORE

The deepen phase researched this and found INSERT OR IGNORE suppresses ALL constraint violations (UNIQUE, NOT NULL, CHECK), not just the intended one. ON CONFLICT(habit_id, completed_date) DO NOTHING targets only the specific UNIQUE constraint, letting FK violations propagate as IntegrityError (which the route catches and returns 404).

```python
cursor = conn.execute(
    "INSERT INTO completions (habit_id, completed_date) VALUES (?, ?) "
    "ON CONFLICT(habit_id, completed_date) DO NOTHING",
    (habit_id, target_date),
)
```

**Requires SQLite 3.24.0+ (Python 3.8+).** This is a strict improvement over the feedback-board pattern and should be the default going forward.

### 2. Fragment Anchor Redirect for Server-Rendered Toggle Grids

The Feed-Forward risk flagged that the calendar's POST-redirect-GET cycle would feel "jumpy" when toggling multiple cells. The deepen phase found the solution: redirect with a fragment anchor.

```python
return redirect(url_for("habits.calendar", week=week_start) + f"#habit-{habit_id}")
```

Combined with CSS `scroll-margin-top: 80px` on the anchor target, the browser scrolls back to the toggled row after reload. No JavaScript needed. This pattern is reusable for any server-rendered grid where cells trigger form POSTs.

### 3. WTF_CSRF_TIME_LIMIT = None for Long-Lived Pages

Flask-WTF's default CSRF token expiry is 3600s (1 hour). For a habit tracker dashboard that stays open all day, this causes silent 400 errors when the user toggles hours after loading. Setting `WTF_CSRF_TIME_LIMIT = None` disables the timestamp check while keeping cryptographic validation. Safe for single-user apps where the session cookie provides the time boundary.

### 4. ARIA Grid Roles on Calendar

The calendar uses `role="grid"` with `role="row"`, `role="rowheader"`, `role="columnheader"`, and `role="gridcell"`. Each toggle button has a descriptive `aria-label` (habit name + date + state). Future-date cells use `<span aria-disabled="true">` instead of omitting them from the DOM. This is the correct pattern per WAI-ARIA for interactive grids.

### 5. Week-Boundary Validation (Codex P1 Fix)

The initial implementation validated toggle dates against "within 7 days of today" but the plan specified "within the displayed week view." Codex caught this: a user could POST to a date outside the calendar view they were looking at, and the redirect would land on a week that didn't show the toggled date. Fixed by parsing the `?week=` param and validating `week_start <= target_date <= week_end`.

**Lesson:** "Within N days" and "within the displayed range" are different constraints. The plan said "displayed week" -- implement what the plan says.

## What Went Wrong

### Toggle Path Parity (Codex P1)

`toggle_today` checked if the habit existed and was not archived before toggling. `toggle_date` did not -- it went straight to `toggle_completion`. This meant archived habits could still have their historical completions mutated via the date-specific route.

**Root cause:** When writing `toggle_date`, I focused on date validation (format, future, range) and forgot the habit-level guard that `toggle_today` had. Two routes doing similar things with different preconditions.

**Fix:** Added the same `get_habit_by_id` + archived check to `toggle_date`.

**Prevention:** When a plan has multiple routes that call the same model function, verify they all enforce the same preconditions. A code review checklist item: "Do all callers of X validate the same invariants?"

## Patterns Confirmed from Prior Solution Docs

| Pattern | Source Doc | Status |
|---------|-----------|--------|
| Set deduplication before streak math | cli-habit-tracker-streaks | Implemented, verified correct |
| init_db try/finally for FD leak prevention | feedback-board-solo-build | Implemented |
| ON CONFLICT + rowcount for atomic toggle | feedback-board-solo-build (evolved) | Evolved from INSERT OR IGNORE to ON CONFLICT DO NOTHING |
| CSRF `{{ csrf_token() }}` with parentheses | coworkflow-22-agent-swarm-build | Verified in all 4 templates |
| WAL mode set once in init_db, not per-connection | flask-url-shortener-api | Implemented |
| SECRET_KEY fail-closed in non-debug | feedback-board-solo-build | Implemented |

## Deepen Phase Value

The 5-agent deepen phase added concrete depth to the plan:
- **atomic-toggle:** Found the INSERT OR IGNORE -> ON CONFLICT improvement
- **csrf-mini-forms:** Found the WTF_CSRF_TIME_LIMIT expiry issue
- **calendar-ux:** Found the anchor redirect pattern (directly addressed Feed-Forward risk)
- **streak-computation:** Verified algorithm correctness (no changes needed)
- **sqlite-wal-flask:** Confirmed patterns correct, added depth notes

Without the deepen phase, the CSRF expiry bug and the INSERT OR IGNORE weakness would have shipped. The anchor redirect would not have been discovered until manual testing.

## Feed-Forward

- **Hardest decision:** Whether ON CONFLICT DO NOTHING was worth the SQLite 3.24+ version requirement. It is -- Python 3.8+ has been EOL-eligible since 2024, and the constraint-targeting benefit is a real safety improvement.
- **Rejected alternatives:** g-object DB pattern (context manager is simpler for single-call routes), SQL window function streaks (unnecessary at personal scale), meta-tag CSRF approach (only useful for AJAX/SPA).
- **Least confident:** The ARIA grid roles set screen reader expectations for arrow-key navigation, which requires JavaScript to implement. Without JS, Tab key cycles through all buttons sequentially. The ARIA semantics may promise more than the keyboard UX delivers. Future work: add a lightweight JS handler for arrow-key grid navigation, or downgrade to `role="table"`.
