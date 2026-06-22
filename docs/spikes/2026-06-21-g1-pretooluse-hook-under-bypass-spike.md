---
title: "G1 Spike — Does a PreToolUse hook fire under dangerouslySkipPermissions?"
date: 2026-06-21
type: spike
status: complete
verdict: GREEN — mechanism viable
traces_to:
  - docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md (Feed-Forward "least confident")
  - docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md (G1)
environment:
  claude_code_version: 2.1.173
  platform: darwin 25.4.0
---

# G1 Spike — PreToolUse hook firing above the permission bypass

## Question (the brainstorm's "least confident" / verify-first item)

The G1 firebreak intercepts RED actions with a **PreToolUse hook** while autopilot
runs under `dangerouslySkipPermissions: true` with `mode: "bypassPermissions"`
injected into every spawned worker. **If the bypass also short-circuits hooks, the
whole mechanism is dead** and must move to the agent-brief contract or a tool
wrapper. This spike verifies firing *before* any design work, per the plan's
verify-first gate.

## Method

Two independent checks. **(A) Documentation** — authoritative Claude Code docs via
the claude-code-guide agent. **(B) Empirical** — a fully isolated rig in
`/tmp/g1-spike/` (its own project dir + `.claude/settings.json`; the live sandbox
repo and global `~/.claude/` config were never touched).

The rig's PreToolUse hook matches `Bash`, appends `FIRED` to `hook-fired.log`, and
`exit 2` (deny). The headless prompt asks the agent to run a Bash command that
writes a *different* marker (`cmd-ran.log`). Three distinguishable outcomes:

| hook-fired.log | cmd-ran.log | Meaning |
|:-:|:-:|---|
| present | absent | hook fired **and blocked** ✅ (mechanism viable) |
| present | present | hook fired but did **not** block (need a different deny path) |
| absent | present | hook did **not** fire under bypass ❌ (mechanism must move) |

Two runs: `run.sh` (main session runs Bash) and `run2.sh` (a Task-spawned
general-purpose subagent runs Bash — the autopilot worker analog).

## Results

| Case | hook-fired.log | cmd-ran.log | Verdict |
|------|:-:|:-:|---|
| **Main session** under `--dangerously-skip-permissions` | `FIRED` | absent | fired + blocked ✅ |
| **Task-spawned subagent** under bypass | `FIRED` | absent | fired + blocked ✅ |

In both runs the agent itself reported: *"blocked by a PreToolUse hook … exited
with code 2, which denies the Bash call before execution."*

**Documentation (B) agrees and is explicit:** per the Claude Code hooks reference,
"`dangerouslySkipPermissions` … does not bypass PreToolUse hooks. Even when
permissions are bypassed, `PreToolUse` hooks still run and can block tool calls."
Hooks and the permission system are separate layers; a hook `exit 2` /
`permissionDecision: "deny"` blocks *before* permission rules are evaluated.

## Verdict — GREEN (mechanism viable)

A deterministic PreToolUse-hook denylist **can** intercept and defer RED actions
above the permission bypass, for both the main session and spawned subagents. The
firebreak proceeds with this mechanism; the brainstorm's fallbacks (agent-brief
contract, tool wrapper) are **not** needed.

## Residual — the one thing this spike did NOT cover

Autopilot workers spawn with `isolation: "worktree"` (a separate cwd), which the
empirical rig did not replicate. Docs are **silent** on worktree-subagent hook
inheritance specifically. This is a hook-config **placement** question, not a
viability question:

- **Global `~/.claude/settings.json` hooks are cwd-independent** → they fire for
  worktree subagents regardless of their working directory. This is the safe
  placement.
- **Project `.claude/settings.json` hooks** travel with the repo checkout; a
  worktree is a checkout of the same repo, so a *tracked* project hook is present
  in each worktree — but `settings.local.json` is typically gitignored and would
  NOT propagate.

→ Carried into the plan as **gating Step 0**: confirm hook firing inside a real
`isolation: "worktree"` autopilot-path spawn and lock the hook-placement decision
(global vs tracked project settings) before building the denylist.

## Reproduce

`/tmp/g1-spike/run.sh` and `/tmp/g1-spike/run2.sh` (rig is ephemeral under `/tmp`).
