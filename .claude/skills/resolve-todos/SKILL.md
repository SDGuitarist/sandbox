---
name: resolve-todos
description: Read all pending todos, prioritize by fix ordering rules, apply fixes incrementally, commit each batch, mark resolved. Use after a review phase creates todos.
argument-hint: "[optional: filter by priority, e.g. 'p1' or 'p1 p2']"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Resolve Todos

Automatically resolve all pending review todos. Reads `todos/`, prioritizes
using the fix ordering rules, applies fixes, commits incrementally, and marks
each todo as resolved.

## Step 1: Scan and Parse

Glob for `todos/*-pending-*.md`. Read each file and extract YAML frontmatter:
- `status` (only process `pending`)
- `priority` (p1, p2, p3)
- `issue_id`
- `dependencies` (issues that must be fixed first)
- `unblocks` (issues this fix would resolve or simplify)
- `tags`

If `$ARGUMENTS` contains a priority filter (e.g., "p1" or "p1 p2"), only
process todos matching those priorities. Otherwise, process all pending todos.

If no pending todos are found, output "No pending todos." and stop.

## Step 2: Prioritize

Sort todos using these rules (applied in this order):

1. **Cascade fixes first** -- if fixing issue A would automatically resolve
   issues B and C, A comes first regardless of priority. The issue that
   unblocks the most others wins.
2. **Respect dependencies** -- if B depends on A, A must come first even if
   B is higher priority.
3. **Within same priority, rank by blast radius** -- a fix affecting 5 files
   ranks above a fix affecting 1 file. A fix causing data loss ranks above
   a fix causing slow UI.
4. **Root causes before symptoms** -- if two findings describe the same
   underlying problem, fix the root cause first.

Output the fix order as a numbered table:

```
### Fix Order

| # | Todo | Priority | Why this order | Unblocks |
|---|------|----------|---------------|----------|
| 1 | 001 | P1 | Root cause, unblocks 002 | 002, 005 |
| 2 | ... | ... | ... | ... |
```

## Step 3: Batch by Proximity

Group adjacent todos in the fix order if they meet ALL of these criteria:
- Same priority level
- Affect the same file(s) or same codebase area
- No dependency between them
- Combined diff would be under ~100 lines

Label each batch (e.g., "Batch 1: security fixes in task-tracker").
Solo todos that don't fit a batch are their own batch of 1.

## Step 4: Fix Loop

For each batch, in fix order:

### 4a: Read Context

Read the todo(s) in this batch. Read all affected files listed in the todo's
"Technical Details" or "Affected files" section. Understand what needs to
change before touching anything.

### 4b: Apply Fix

Make the changes described in the todo. Follow the "Proposed Solutions" or
"Recommended Action" section. If multiple options exist, pick the one marked
as recommended. If none is marked, pick the simplest.

Rules:
- Make the minimum change needed. Do not refactor surrounding code.
- Do not add features, tests, or documentation beyond what the todo requires.
- If a fix requires reading files not mentioned in the todo, read them first.
- If a fix seems wrong or dangerous, skip it and report why.

### 4c: Commit

Stage only the files changed by this batch. Commit with this format:

```
fix: [short description] ([todo IDs])

[one-line summary of what changed and why]

Resolves todos [IDs].

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

### 4d: Mark Resolved

For each todo in this batch, update its file: change `status: pending` to
`status: resolved`. Do NOT commit the todo status changes yet -- they get
committed in Step 5.

### 4e: Circuit Breaker

After each batch, verify the fix didn't break anything obvious:
- If the todo mentions a test command, run it.
- If the fix modified Python files, check for syntax errors: `python -c "import ast; ast.parse(open('[file]').read())"`.
- If the fix modified HTML templates, check for unclosed tags in the diff.

If verification fails:
1. Revert the batch commit: `git revert HEAD --no-edit`
2. Mark the todo(s) as `status: blocked` instead of `resolved`
3. Report the failure
4. Continue to the next batch (do not stop the entire loop)

## Step 5: Commit Todo Status Updates

After all batches are processed, stage all modified todo files and commit:

```
chore: mark [N] review todos as resolved

[list of resolved todo IDs]

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

## Step 6: Report

Output a summary table:

```
### Todo Resolution Summary

| # | Todo | Priority | Status | Commit |
|---|------|----------|--------|--------|
| 1 | 001 | P1 | resolved | abc1234 |
| 2 | 003 | P1 | blocked | (reverted) |
| 3 | ... | ... | ... | ... |

Resolved: X/Y
Blocked: Z
```

If any todos were blocked, list the failure reason for each.
