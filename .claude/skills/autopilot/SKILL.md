---
name: autopilot
description: Full autonomous compound engineering loop with swarm support. Reads plan frontmatter to branch between solo and swarm paths. Use to build apps end-to-end unattended.
argument-hint: "[app description]"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, Agent
---

# Autopilot

Run the full compound engineering pipeline unattended. After planning and
deepening, read the plan's YAML frontmatter. If `swarm: true`, take the swarm
path (parallel agents + assembly verification). Otherwise, take the solo path.

## Steps

Execute these steps in order. Do not stop between steps.

### Step 1: Start Ralph Loop

Run `/ralph-loop:ralph-loop "finish all slash commands" --completion-promise "DONE"`

### Step 2: Compound Start

Run `/compound-start $ARGUMENTS`

### Step 3: Brainstorm

Run `/workflows:brainstorm $ARGUMENTS`

### Step 4: Brainstorm Refinement

Use the **brainstorm-refinement** agent. Pass the path to the brainstorm doc
just created in `docs/brainstorms/`. Read its output and check for STATUS: PASS.

### Step 5: Plan

Run `/workflows:plan $ARGUMENTS`

### Step 6: Deepen Plan

Run `/compound-engineering:deepen-plan`

After deepening completes, read the plan document in `docs/plans/`. Extract the
`swarm:` field from its YAML frontmatter.

---

## Branch Point

Read the plan's YAML frontmatter. Check the `swarm:` field.

- If `swarm: false` or `swarm:` is missing -> follow **Solo Path** below
- If `swarm: true` -> follow **Swarm Path** below

---

## Solo Path

### Step 7s: Work

Run `/workflows:work`

### Step 8s: Review

Run `/workflows:review`

### Step 9s: Resolve TODOs

Run `/compound-engineering:resolve_todo_parallel`

### Step 10s: Compound + Learnings

Run `/workflows:compound`
Run `/update-learnings`

### Step 11s: Done

Output `<promise>DONE</promise>` -- all phases complete.

---

## Swarm Path

> **TODO:** Wire swarm steps in Phase 3 (parallel agents + assembly) and
> Phase 4 (verification agents). For now, fall back to solo path if swarm
> is detected.

If `swarm: true` is detected but the swarm path is not yet wired, output:

```
WARNING: swarm: true detected but swarm path is not yet implemented.
Falling back to solo path.
```

Then follow the Solo Path above.
