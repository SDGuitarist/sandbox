---
title: "CLI Habit Tracker with Streaks"
date: 2026-04-08
status: complete
origin: "autopilot-integration-test"
---

# CLI Habit Tracker with Streaks -- Brainstorm

## Problem
Track daily habits from the terminal and maintain streak counts to build
consistency. Users want to see which habits they've done today, how long their
current streak is, and get a quick overview without leaving the command line.

## Context
- Greenfield project in `habit-tracker/` subdirectory of sandbox
- Python 3.12+ (sandbox standard)
- Storage: single JSON file at `~/.habit_tracker.json`
- No external dependencies -- stdlib only (argparse, json, pathlib, datetime)
- Single file: `habit_tracker.py`
- Prior art: CLI todo app in this same sandbox used identical pattern

## What We're Building

A CLI tool with these commands:
- `add <name>` -- create a new habit to track
- `log <id>` -- mark a habit as done for today
- `list` -- show all habits with today's status and current streak
- `delete <id>` -- remove a habit
- `stats <id>` -- show detailed streak info for one habit

## JSON Schema

```json
{
  "habits": [
    {
      "id": 1,
      "name": "Exercise",
      "created_at": "2026-04-08",
      "completions": ["2026-04-06", "2026-04-07", "2026-04-08"]
    }
  ]
}
```

Streak is computed from `completions` -- count consecutive days backward from
today (or yesterday if not yet logged today). Not stored; always calculated.

IDs are auto-incrementing integers (same pattern as todo app).

## Why This Approach

### Computed streaks vs stored streaks
Storing a `streak: 5` counter requires updating it on every log AND on every
day the user doesn't log. Computed streaks from the completions list are
simpler, always correct, and never stale.

### Flat date list vs calendar structure
A flat list of ISO date strings is easy to append, deduplicate, and sort.
Calendar structures (year > month > day) add complexity for zero benefit at
personal scale.

## Key Decisions

1. **argparse (stdlib)** -- same rationale as todo app. Zero deps, four commands.
2. **`~/.habit_tracker.json`** -- home directory, works from any cwd.
3. **Computed streaks** -- derive from completions list, never store.
4. **Integer IDs** -- `habit_tracker.py log 3` is easier than UUIDs.
5. **Idempotent logging** -- `log 3` twice on same day is a no-op (deduped).
6. **Date-only granularity** -- no time tracking, just did-you-do-it-today.
7. **Single file** -- `habit_tracker.py`, no package structure.

## Open Questions
(All resolved during brainstorm)

1. What if user logs a habit and the streak was broken yesterday? -- Start a
   new streak of 1. Old streaks are gone.
2. Show longest streak ever? -- Yes, in `stats` command output. Computable
   from completions list.
3. Timezone handling? -- Use system local date via `datetime.date.today()`.
   Don't overthink it for a personal CLI tool.

## Feed-Forward
- **Hardest decision:** Computed vs stored streaks. Computed is simpler but
  requires scanning the full completions list each time. At personal scale
  (hundreds of entries max) this is negligible.
- **Rejected alternatives:** Click/Typer (unnecessary deps), SQLite storage
  (overkill for single-user JSON), stored streak counters (stale data risk).
- **Least confident:** Whether the `stats` command adds enough value to
  justify a 5th command, or if streak info in `list` output is sufficient.
  Plan phase should decide scope.

## Refinement Findings

**Gaps found:** 3

1. **Python CLI Todo App -- `get_next_id` empty-list guard** -- The brainstorm describes ID generation as `max(ids) + 1` but does not mention guarding against the empty-list case; calling `max()` on an empty list raises `ValueError` on the very first `add` command.
   - Source: `docs/solutions/2026-04-05-cli-todo-app-python.md`
   - Relevance: The habit tracker uses the identical ID scheme. The plan must include `if not habits: return 1` before any `max()` call, or the tool crashes on a fresh install.

2. **Python CLI Todo App -- argparse subcommand dispatch pattern** -- The brainstorm chooses argparse but does not capture the `set_defaults(func=cmd_add)` / `args.func(args)` dispatch pattern; without it the implementation will likely use a brittle if/elif chain over subcommand names.
   - Source: `docs/solutions/2026-04-05-cli-todo-app-python.md`
   - Relevance: The dispatch pattern is a direct carry-over from the prior-art todo app the brainstorm already references -- the plan should explicitly adopt it to avoid reinventing the wheel.

3. **Python CLI Todo App -- no file locking needed for single-user tools** -- The brainstorm is silent on file locking for `~/.habit_tracker.json`; the solution doc explicitly calls this out as over-engineering and provides the rationale for skipping it.
   - Source: `docs/solutions/2026-04-05-cli-todo-app-python.md`
   - Relevance: The plan should document this decision (single-user tool, no concurrent writers, no locking needed) so it is not re-litigated during implementation or review.

STATUS: PASS
