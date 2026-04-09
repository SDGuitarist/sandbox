---
title: "feat: CLI Habit Tracker with Streaks"
type: feat
status: active
date: 2026-04-08
origin: docs/brainstorms/2026-04-08-cli-habit-tracker-brainstorm.md
swarm: false
feed_forward:
  risk: "Whether the stats command adds enough value to justify a 5th command, or if streak info in list output is sufficient"
  verify_first: true
---

# feat: CLI Habit Tracker with Streaks

A single-file Python CLI tool for tracking daily habits and computing streaks.
Follows the exact pattern established by `todo.py` in this repo.

## Enhancement Summary

**Deepened on:** 2026-04-09
**Agents used:** code-simplicity-reviewer, pattern-recognition-specialist, spec-flow-analyzer

### Key Improvements
1. Added missing error cases: `log`/`stats` on bad ID, empty name, corrupted JSON
2. Specified `compute_longest_streak` algorithm (was left vague)
3. Added `JSONDecodeError` handling to match `todo.py` pattern

## What Is Changing

One new file: `habit-tracker/habit_tracker.py`

Five subcommands: `add`, `log`, `list`, `delete`, `stats`

Storage: `~/.habit_tracker.json` (created on first `add`)

## What Must Not Change

- No modifications to any existing sandbox files
- No external dependencies (stdlib only)
- No package structure -- single file

## Acceptance Criteria

- [ ] `python habit_tracker.py add "Exercise"` creates a habit with integer ID
- [ ] `python habit_tracker.py log 1` marks habit 1 done for today (idempotent)
- [ ] `python habit_tracker.py list` shows all habits with today's status and current streak
- [ ] `python habit_tracker.py delete 1` removes a habit
- [ ] `python habit_tracker.py stats 1` shows current streak, longest streak, total completions
- [ ] First `add` on empty/missing file creates `~/.habit_tracker.json` without error
- [ ] Streak computation is correct: consecutive days backward from today/yesterday
- [ ] Logging same habit twice on same day is a no-op (deduplicated)
- [ ] Deleting non-existent ID prints error and exits with code 1
- [ ] Logging non-existent ID prints error and exits with code 1
- [ ] Adding empty name prints error and exits with code 1
- [ ] Listing with no habits prints "No habits yet."
- [ ] Corrupted JSON file prints error and exits with code 1

## How We Will Know It Worked

Run these commands in sequence:
```bash
python habit_tracker.py add "Exercise"
python habit_tracker.py add "Read"
python habit_tracker.py log 1
python habit_tracker.py log 1      # idempotent, no duplicate
python habit_tracker.py list       # shows Exercise with streak 1, Read with streak 0
python habit_tracker.py stats 1    # current: 1, longest: 1, total: 1
python habit_tracker.py delete 2
python habit_tracker.py list       # only Exercise remains
python habit_tracker.py delete 99  # error, exit 1
```

## Most Likely Way This Plan Is Wrong

The `stats` command may be unnecessary scope. The brainstorm flagged this as
"least confident." Resolution: include it -- it is ~15 lines of code, computes
from the same completions list, and exercises the streak algorithm more
thoroughly for testing purposes. If it feels wrong during implementation, drop
it and fold streak info into `list` output only.

## Implementation

### File Structure

```
habit-tracker/
  habit_tracker.py
```

### Data Model (see brainstorm: JSON Schema section)

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

### Key Implementation Details

**From brainstorm + refinement findings:**

1. **ID generation** -- `max(h["id"] for h in habits) + 1` with empty-list
   guard: `return 1 if not habits else max(...) + 1`
   (see refinement finding #1)

2. **Argparse dispatch** -- `set_defaults(func=cmd_add)` / `args.func(args)`
   pattern, not if/elif chain
   (see refinement finding #2)

3. **No file locking** -- single-user tool, no concurrent writers
   (see refinement finding #3)

4. **Streak computation** -- sort `completions` as dates descending. Start from
   most recent. If most recent is today or yesterday, begin counting. Walk
   backward: each date must be exactly 1 day before the previous. Stop at
   first gap. Empty completions returns 0. `compute_longest_streak` uses the
   same walk but checks every contiguous run and returns the max.

7. **JSONDecodeError handling** -- wrap `json.load()` in try/except, print
   error message with path, `sys.exit(1)`. Same pattern as `todo.py:27-29`.

8. **Error on bad ID** -- `log` and `stats` commands must also error + exit 1
   on non-existent ID (same as `delete`).

5. **Storage path** -- `Path.home() / ".habit_tracker.json"`

6. **Idempotent logging** -- check if today's date is already in completions
   before appending

### Functions

```
main()                          # argparse setup + dispatch
load_data() -> dict             # read JSON, return empty structure if missing
save_data(data: dict)           # write JSON
get_next_id(habits: list) -> int  # with empty-list guard
compute_streak(completions: list[str]) -> int  # current streak
compute_longest_streak(completions: list[str]) -> int  # all-time best
cmd_add(args)                   # create habit
cmd_log(args)                   # mark done today
cmd_list(args)                  # show all with status + streak
cmd_delete(args)                # remove habit
cmd_stats(args)                 # detailed streak info
```

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-04-08-cli-habit-tracker-brainstorm.md](docs/brainstorms/2026-04-08-cli-habit-tracker-brainstorm.md)
  Key decisions carried forward: argparse (zero deps), computed streaks, integer IDs, `~/.habit_tracker.json`, idempotent logging
- **Prior art:** `todo.py` in this repo -- identical pattern
- **Solution doc:** `docs/solutions/2026-04-05-cli-todo-app-python.md` -- empty-list guard, dispatch pattern, no-locking rationale

## Feed-Forward

- **Hardest decision:** Whether to include `stats` command. Included it -- low
  cost, better test coverage of streak algorithm.
- **Rejected alternatives:** Dropping `stats` (loses test surface), storing
  streaks instead of computing (stale data risk, per brainstorm).
- **Least confident:** Streak edge case when user logs after midnight but
  considers it "yesterday's" habit. Using system local date -- documented as
  acceptable in brainstorm. Not adding timezone configurability.
