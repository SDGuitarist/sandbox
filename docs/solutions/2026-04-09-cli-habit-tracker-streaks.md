---
title: "CLI Habit Tracker with Streaks"
date: 2026-04-09
category: logic-errors
tags: [python, cli, argparse, json, streaks, date-math, deduplication]
module: habit-tracker
symptom: "Streak computation returns wrong count when completions list has duplicate dates"
root_cause: "Streak functions used list comprehension instead of set comprehension, allowing duplicate dates to break consecutive-day counting"
---

# CLI Habit Tracker with Streaks

## Problem

Building a CLI habit tracker that computes streaks (consecutive days of
completion). The streak algorithm must handle: empty completions, single-day
streaks, gaps in completion, and the edge case of duplicate dates in the
JSON data file.

## Investigation

Extended the todo.py pattern (argparse + JSON + home-dir storage) with two
new concepts: date-based completions and streak computation.

The initial implementation used `sorted([date.fromisoformat(d) for d in completions])`
which preserves duplicates. If the JSON file is hand-edited or written by
another tool with duplicate dates, the streak count breaks because
`date - date == timedelta(0)`, not `timedelta(days=1)`.

## Root Cause

List comprehension `[...]` preserves duplicates. Two identical dates in the
sorted list create a gap of 0 days, which breaks the consecutive-day check
and resets the streak counter.

## Solution

Use set comprehension `{...}` before sorting to deduplicate dates:

```python
def compute_streak(completions):
    if not completions:
        return 0
    dates = sorted({date.fromisoformat(d) for d in completions}, reverse=True)
    today = date.today()
    if dates[0] != today and dates[0] != today - timedelta(days=1):
        return 0
    streak = 1
    for i in range(1, len(dates)):
        if dates[i - 1] - dates[i] == timedelta(days=1):
            streak += 1
        else:
            break
    return streak
```

Same fix for `compute_longest_streak` -- use `{...}` instead of `[...]`.

## Key Lessons

1. **Computed > stored for derived values.** Storing a `streak: 5` counter
   requires updating on every log AND every missed day. Computing from
   completions list is always correct and never stale.

2. **Deduplicate before date math.** Any time you sort dates for consecutive-day
   counting, use `set()` first. Duplicates create zero-day gaps that break
   streak logic.

3. **Guard empty lists before `max()`.** Same lesson as todo app -- always
   check `if not items` before calling `max()`.

4. **Idempotent operations prevent data issues.** `cmd_log` checks if today's
   date is already in completions before appending. This prevents duplicates
   at the source, but the dedup in streak computation is a safety net for
   hand-edited JSON.

## Prevention

- Always use set comprehension when deduplication matters
- Test streak functions with duplicate dates in the input
- Keep idempotent guards at the write point (cmd_log) AND the read point
  (streak computation)

## Related

- `docs/solutions/2026-04-05-cli-todo-app-python.md` -- predecessor pattern
  (argparse + JSON + empty-list guard)
