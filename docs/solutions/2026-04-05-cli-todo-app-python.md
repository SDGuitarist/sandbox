---
title: "Python CLI Todo App with argparse + JSON"
date: 2026-04-05
tags: [python, cli, argparse, json, local-storage]
status: solved
---

# Python CLI Todo App with argparse + JSON

## Problem Solved

Building a single-file Python CLI app with CRUD commands (add, list, complete,
delete) persisted to a local JSON file, with no external dependencies.

## Solution

Single file `todo.py` using:
- `argparse` for subcommands (zero deps)
- `json` + `pathlib` for storage at `~/.todos.json`
- `datetime` for timestamps
- Auto-incrementing integer IDs via `max(ids) + 1`

## Key Decisions

### argparse over Click/Typer
For a 4-command app with no deps requirement, argparse is sufficient. The
boilerplate is manageable (~120 lines total). Use Click when you have 10+
commands or need validation decorators.

### Home-dir storage (`~/.todos.json`) over cwd
Todos persist across working directories. The tradeoff is no per-project
isolation — acceptable for a personal todo tool.

### Integer IDs over UUIDs
Users type IDs directly (`todo.py complete 3`). Short integers are far more
ergonomic than UUIDs for this use case.

## Patterns That Worked

```python
# Clean subcommand dispatch pattern
p_add.set_defaults(func=cmd_add)
args = parser.parse_args()
args.func(args)  # dispatch without if/elif chain
```

```python
# Safe get_next_id — always guard empty list before max()
def get_next_id(todos):
    if not todos:
        return 1
    return max(t["id"] for t in todos) + 1
```

## Risk Resolution

- **Flagged risk:** Storage path decision and argparse UX quality
- **What happened:** `~/.todos.json` works well; argparse with module-level
  docstring examples covers the UX gap adequately
- **Lesson:** For simple local-file CLIs, hardcoded home-dir path is fine —
  only add configurability if there's a concrete use case for it

## What NOT to Do

- Don't add file locking for a single-user personal tool — over-engineering
- Don't use UUIDs for user-facing IDs on small local datasets
- Don't split into a package unless you have 3+ modules with meaningful separation
