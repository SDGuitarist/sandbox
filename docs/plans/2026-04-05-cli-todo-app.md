---
title: "CLI Todo App in Python"
date: 2026-04-05
status: ready
brainstorm: docs/brainstorms/2026-04-05-cli-todo-app-python.md
feed_forward:
  risk: "Storage path decision (~/.todos.json vs XDG-compliant path vs cwd) and whether sequential integer IDs are ergonomic enough"
  verify_first: true
---

# CLI Todo App in Python — Plan

## What exactly is changing?

Creating a new file `/workspace/todo.py` — a single-file Python CLI app with
four subcommands: `add`, `list`, `complete`, `delete`. Todos are persisted to
`~/.todos.json` (home directory). No other files are created except the JSON
data file at runtime.

## What must NOT change?

- No external dependencies — stdlib only (argparse, json, pathlib, datetime)
- No existing files in `/workspace` will be modified
- The JSON schema must remain stable: `{"todos": [{id, title, done, created_at}]}`

## How will we know it worked?

Manual smoke test after implementation:
1. `python todo.py add "Buy milk"` → prints "Added: [1] Buy milk"
2. `python todo.py list` → shows item with ○ marker
3. `python todo.py complete 1` → prints "Completed: [1] Buy milk"
4. `python todo.py list` → shows item with ✓ marker
5. `python todo.py delete 1` → prints "Deleted: [1] Buy milk"
6. `python todo.py list` → prints "No todos yet."
7. `python todo.py complete 99` → prints error, exits with code 1
8. `python todo.py delete 99` → prints error, exits with code 1
9. `python todo.py add ""` → prints error about empty title, exits with code 1

## What is the most likely way this plan is wrong?

The storage path `~/.todos.json` is hardcoded. If the user wants per-project
todos or a configurable path, this is wrong. Mitigated by: this is explicitly
a simple local app per the spec — one file, one store.

---

## Implementation Spec

### File: `/workspace/todo.py`

Single executable Python script. No package structure needed.

### Storage

- Path: `pathlib.Path.home() / ".todos.json"`
- Created automatically on first write if it doesn't exist
- Format:
  ```json
  {"todos": [{"id": 1, "title": "...", "done": false, "created_at": "ISO8601"}]}
  ```
- IDs: auto-increment from `max(existing ids) + 1`, starting at 1
- Read/write pattern: load entire file → mutate in memory → write entire file

### Commands

#### `add <title>`
- Validates title is non-empty (strip whitespace)
- Creates new todo: next id, title, done=false, created_at=now ISO8601
- Appends to todos list, saves file
- Prints: `Added: [1] Buy milk`

#### `list [--pending-only]`
- Loads todos
- If empty: prints "No todos yet."
- Otherwise prints each todo:
  - `✓ [1] Buy milk  (2026-04-05)` for done
  - `○ [2] Call dentist  (2026-04-05)` for pending
- `--pending-only` flag filters to done=false only

#### `complete <id>`
- Finds todo by id (integer)
- If not found: prints "Error: todo #N not found", exits 1
- If already done: idempotent, still prints "Completed: [N] title"
- Sets done=true, saves file
- Prints: `Completed: [1] Buy milk`

#### `delete <id>`
- Finds todo by id (integer)
- If not found: prints "Error: todo #N not found", exits 1
- Removes from list, saves file
- Prints: `Deleted: [1] Buy milk`

### Error handling

- JSON file corrupt: catch JSONDecodeError, print "Error: todos file is
  corrupted. Delete ~/.todos.json to reset.", exit 1
- File permission error: let Python's default IOError propagate (rare edge case)
- Invalid id argument (non-integer): argparse handles this via `type=int`

### Code structure (single file, ~120 lines)

```
load_todos()      → dict
save_todos(data)  → None
get_next_id(todos) → int
find_todo(todos, id) → todo | None

cmd_add(args)
cmd_list(args)
cmd_complete(args)
cmd_delete(args)

main()  → argparse setup + dispatch
```

## Plan Quality Gate

1. **What exactly is changing?** Single new file `todo.py`, no existing files touched.
2. **What must not change?** No deps, stable JSON schema, no existing workspace files.
3. **How will we know it worked?** 9-step manual smoke test above covers all commands + error cases.
4. **Most likely way this plan is wrong?** Hardcoded storage path — acceptable for the stated scope.

## Feed-Forward

- **Hardest decision:** `~/.todos.json` (global) vs cwd-local `todos.json`. Chose home-dir global so todos persist across directories. This is an opinionated choice.
- **Rejected alternatives:** Click/Typer (deps), package structure (overkill for 1 file), UUIDs for IDs (worse UX than integers), SQLite (overkill).
- **Least confident:** Whether argparse's default help text is good enough UX, or if users will be confused by the subcommand syntax. Could be addressed with good docstrings in the parser.
