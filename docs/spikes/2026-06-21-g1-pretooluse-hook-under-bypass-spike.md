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

---

# Step 0 — Gating Spike Results (2026-06-22) — ✅ PASS

Run on `feat/g1-risk-tiered-firebreak` (off master `fb0d7a1`). Closes the residual
above: confirms a session/global-level PreToolUse hook governs the **real**
`isolation:"worktree"` + `bypassPermissions` worker path, and validates the
identity contract + fast-path shape the plan depends on.

## Method (extends the prior rig)

Isolated git repo at `/tmp/g1-step0/` (own commit history so worktrees can spawn).
The throwaway hook was loaded via **`claude -p --settings /tmp/g1-step0/fb-settings.json
--dangerously-skip-permissions`** — a **session-level** hook, cwd-independent, the same
property as global `~/.claude/settings.json` placement — so the **real `~/.claude`
global config was never modified.** The hook (`fb-hook.py`) logs the **full raw
PreToolUse stdin** (to observe which identity fields actually exist — not assume them)
and `exit 2` denies any command/path carrying a sentinel token (`STEP0_DENYME` /
`STEP0_CONTROL_PLANE`). Four staged headless runs; ground truth = `hook-events.log`,
not the agents' narration.

## Results

### Check 1 — hook governs the real worker path (F1 real-spawn probe) ✅

| Stage | Actor | Action | Hook fired? | Blocked? |
|------|-------|--------|:----------:|:--------:|
| 1 | orchestrator (main session, bypass) | `echo STEP0_DENYME_main` (Bash) | yes | **yes** (`exit 2`) |
| 2 | **`isolation:"worktree"` + bypass subagent** | `echo STEP0_DENYME_worker` (Bash) | yes | **yes** |
| 2 | same worker | Write → `STEP0_CONTROL_PLANE.json` | yes | **yes** (file verified ABSENT afterward) |

The Stage-2 worker ran in a genuinely separate worktree
(`cwd: /private/tmp/g1-step0/.claude/worktrees/agent-a4eb300104213d807`). Both a
denylisted **Bash** command and a **control-plane Write** were denied pre-execution —
the F1 probe (denylisted cmd AND control-plane write both denied) **passes for the
actual worker path**. → **Hook placement locked: global `~/.claude/settings.json`
(session-level), matcher `Bash|mcp__*|Write|Edit`.** No fallback (agent-brief / tool
wrapper) needed.

### Check 2 — identity contract, all four roles (F5/F8) ✅

Observed PreToolUse stdin per role:

| Role | `agent_id` | `agent_type` | how spawned |
|------|-----------|-------------|-------------|
| orchestrator | **absent** | **absent** | top-level `claude -p` |
| worker | `a4eb3001…` (present) | `general-purpose` | Task, `isolation:"worktree"` |
| swarm-runner | `ad062…` (present) | **`swarm-runner`** | Task, `subagent_type` (via `--agents`) |
| tail-runner | `ad515…` (present) | **`tail-runner`** | Task, `subagent_type` (via `--agents`) |

All four are **present, distinct, and harness-stamped**: custom named subagents
surface their **type name** as `agent_type`, and the orchestrator has neither field.
This is what the trusted-identity allowlist keys on (orchestrator = no `agent_id`;
trusted = `agent_type ∈ {swarm-runner, tail-runner}`; worker = anything else).
**Framing honored:** this is an empirical **harness-contract** confirmation (the
harness sets `agent_type` from the spawn; a worker cannot choose its own type without
going through a governed Agent tool call) — **NOT** cryptographic unforgeability, per
F8. The plan's blanket-deny fallback remains the stated mitigation if the contract
ever fails. Also present on every event: `permission_mode: "bypassPermissions"`.

### Check 3 — fast-path gate shape (R6) + F13 forward-on-suspicion ✅ (with one Phase-1 constraint)

Hook command `bash /tmp/g1-step0/firebreak-gate.sh` (a **single** command — no
`&&`/`;`, no `python3 -c`) is **legal under bypass and blocks correctly**. With the
gate matching only envelope-safe markers (RED tokens / control-plane paths /
`$(` / backtick / `${`):

| Command | Forwarded to python? | Outcome |
|---------|:--------------------:|---------|
| `echo hello_green_gate` (GREEN) | **no** (fast-path `exit 0`) | ran |
| `echo X$(printf Y)` (F13 `$(` opacity) | **yes** | forwarded, allowed (no RED token) |
| `echo STEP0_DENYME_gate` (RED) | **yes** | forwarded + **blocked** |

**Phase-1 constraint surfaced (valuable):** a first naive gate also matched `{`/`\`
against the **raw JSON stdin** — but a JSON envelope **always** contains `{`, so the
fast-path collapsed (python cold-started on *every* call, defeating R6's 7–12 min/run
saving). **Resolution for Phase 1:** the cheap entry gate must restrict its grep to
**envelope-safe markers** (RED tokens, control-plane paths, `$(`/backtick/`${`);
**brace/backslash command-word obfuscation (`c{u,}rl`, `\cu\rl`) must be detected in
the python classifier after the command value is isolated**, NOT by grepping raw
JSON. (Adjusts the plan's gate description at "Phase 1 — firebreak-gate.sh" / the F13
gate-forwarding line.)

## Verdict — Step 0 PASS

All three gating assertions hold for the real worker path. Cleared to build Phase 1
(classifier + hook + sentinel + fast-path + control-plane), carrying the one
brace/backslash gate constraint above. Rig is ephemeral under `/tmp/g1-step0/`
(`run-stage1.sh`…`run-stage4.sh`, `fb-hook.py`, `fb-settings*.json`,
`firebreak-gate.sh`); real `~/.claude/settings.json` was never modified.
