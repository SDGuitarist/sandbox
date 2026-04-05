---
title: "CLI Todo App in Python"
date: 2026-04-05
status: complete
origin: "conversation"
---

# CLI Todo App in Python — Brainstorm

## Problem
Developers and power users often want a simple, fast way to manage a personal
todo list from the terminal — without switching to a browser, opening a GUI,
or relying on cloud sync. A local-first CLI todo app stores state in a plain
JSON file and offers four essential commands: add, list, complete, delete.

## Context
- No existing codebase — greenfield project in `/workspace`
- Must run on Python 3.8+ (wide compatibility)
- Storage: a single `todos.json` file in the current working directory (or a
  fixed path like `~/.todos.json` — to decide)
- No external services, no database, no auth
- Four commands required: `add`, `list`, `complete`, `delete`
- Todos need at minimum: id, title, done status, created_at timestamp

## JSON Schema

```json
{
  "todos": [
    {
      "id": 1,
      "title": "Buy groceries",
      "done": false,
      "created_at": "2026-04-05T10:00:00"
    }
  ]
}
```

IDs are auto-incrementing integers. The file is created on first `add` if it
doesn't exist.

## Options

### Option A: argparse (stdlib)
Built into Python, no install required. Uses subparsers for subcommands.
- **Pros:** Zero dependencies, works in any Python env, familiar to Python devs
- **Cons:** Verbose boilerplate for subcommands, help text is less polished,
  error messages are terse

### Option B: Click (third-party)
Decorator-based CLI library. Very popular, clean API.
- **Pros:** Cleaner code, excellent help formatting, easy input validation,
  large community
- **Cons:** Requires `pip install click`, adds a dependency

### Option C: Typer (third-party, type-hint driven)
Built on Click, uses Python type annotations to define CLI args.
- **Pros:** Minimal code, modern Python feel, auto-generates help
- **Cons:** Newer, smaller community; requires both `typer` and `click`

## Tradeoffs
The key tension is **zero dependencies vs. developer ergonomics**. Since this
is a simple 4-command app:
- argparse is sufficient and keeps the project self-contained
- Click adds one dependency but produces noticeably cleaner code and better UX
- Typer adds two dependencies for marginal gain over Click at this scale

For a beginner-friendly, easy-to-read codebase with no surprising install
requirements: **argparse wins** for a truly standalone script, but **Click**
wins if we want the code to be readable and the UX to be polished.

## Decision
**Use `argparse` (stdlib only).** Rationale:
- Zero dependencies — `python todo.py add "Buy milk"` just works
- Beginner developer context means less cognitive overhead from external libs
- Four commands is simple enough that argparse boilerplate is manageable
- Can always migrate to Click later with minimal effort

Storage path: `~/.todos.json` (home directory) so todos persist across
working directories. This is more useful than cwd-local storage.

## Open Questions
1. Should IDs be sequential integers or UUIDs? → Integers (easier for users to
   type `todo.py complete 3`)
2. What happens on `complete` for an already-completed item? → Idempotent,
   no error
3. What happens on `delete` for a non-existent ID? → Print clear error, exit 1
4. Should `list` show completed todos? → Yes, with visual distinction (✓ vs ○),
   plus an optional `--pending-only` flag
5. Single file `todo.py` or a package? → Single file for simplicity

## Feed-Forward
- **Hardest decision:** Whether to use argparse (zero deps) vs Click (better UX).
  Chose argparse to keep it truly self-contained and beginner-friendly.
- **Rejected alternatives:** Click (one dep, cleaner but unnecessary at this
  scale); Typer (two deps, overkill); cwd-local JSON file (less useful than
  home-directory storage).
- **Least confident:** Whether `~/.todos.json` is the right storage path or if
  the user would prefer configurable location or XDG-compliant path
  (`~/.local/share/todo/todos.json`). Plan phase should decide and lock this in.
