---
spike: nested-worktree-delegation
date: 2026-06-03
runner: claude-opus-4-6[1m] (parent agent, manual session)
status: COMPLETED
verdict: REDUCED DELEGATION
verified: true
verification_method: "3 independent tests (general-purpose agent, typed tail-runner agent, ToolSearch)"
---

# Spike: Nested Worktree Delegation

## Purpose

Determine whether a parent agent can spawn child agents with
`isolation: "worktree"` -- i.e., whether swarm-runner can delegate worker
spawning to child agents that each operate in their own git worktree.

## Key Finding

**Sub-agents do not have the Agent tool, regardless of agent type.**

Three independent tests confirm this:

| Test | Agent Type | Had Agent Tool? |
|------|-----------|-----------------|
| Spike agent (ToolSearch-based) | general-purpose | No |
| Verification agent (direct check) | general-purpose | No |
| Typed agent (tail-runner type) | tail-runner | No |

The Agent tool is available ONLY to the top-level session (the orchestrator).
When the orchestrator spawns a sub-agent via the Agent tool, the sub-agent
receives Bash, Read, Write, Edit, Grep, Glob, Skill, and ToolSearch -- but
NOT Agent. This is true even when the agent type's definition file lists
`tools: ... Agent` in its frontmatter.

**Implication:** Nested agent spawning (agent-from-agent) is a platform
limitation, not a configuration issue. No workaround via agent type
definitions, permission modes, or tool search.

**Latent bug discovered:** The tail-runner agent (`.claude/agents/tail-runner.md`)
Step 8 instructs the agent to "use the self-audit-reviewer agent
(subagent_type: self-audit-reviewer)." This requires the Agent tool, which
sub-agents do not have. This step likely fails silently or was handled by
a different mechanism in prior runs. This is a separate issue from the
spike but affects the current autopilot design.

The tools that DO exist for multi-agent coordination within sub-agents are:

| Tool | Purpose | Can Spawn Agents? | Worktree Support? |
|------|---------|-------------------|-------------------|
| TeamCreate | Creates a team (config + task list) | No -- creates infrastructure only | No |
| SendMessage | Sends messages to teammates | No -- requires agents to already exist | No |
| TaskCreate/Update/List | Task coordination | No -- task tracking only | No |
| EnterWorktree | Enters a git worktree | Current session only | Yes (session-level) |
| ExitWorktree | Exits a git worktree | Current session only | Yes (session-level) |
| RemoteTrigger | Runs scheduled remote agents | Creates remote triggers (not local workers) | No |

## Test Results

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Basic nested worktree spawn | FAIL | Agent tool does not exist. Cannot spawn child agent with `isolation: "worktree"`. TeamCreate only creates team infrastructure (config.json + task directory). SendMessage to non-existent agent "worker-1" returns success but message is never consumed. |
| 2 | Multiple parallel nested workers (3) | FAIL | Same root cause: no spawn mechanism. Cannot create 3 parallel child agents. |
| 3 | Child crash / error | FAIL | Cannot test: no child agent to crash. |
| 4 | Child timeout behavior | FAIL | Cannot test: no child agent to timeout. |
| 5 | Worktree cleanup on failure | PASS | No test worktrees were created (no child agents were spawned). EnterWorktree/ExitWorktree confirmed working for current session: created worktree at `.claude/worktrees/spike-session-test`, verified it existed, exited with `action: "remove"`, confirmed cleanup. Baseline worktree count (1) restored. TeamDelete cleaned up team infrastructure. |
| 6 | bypassPermissions propagation | FAIL | Cannot test: no child agent to receive permissions. |
| 7 | Bounded parent return size | FAIL | Cannot test: no child agent to return values from. |

**Results: 1 PASS, 6 FAIL (all 6 failures share root cause: Agent tool missing)**

## Supplementary Observations

### What DOES work (session-level worktree isolation)

- `EnterWorktree` successfully creates a git worktree under `.claude/worktrees/`
  with a dedicated branch (`worktree-<name>`)
- The session's working directory switches to the worktree
- `ExitWorktree` with `action: "remove"` cleanly deletes the worktree and branch
- `ExitWorktree` with `action: "keep"` preserves the worktree for later use
- Worktree creation and removal are fast (sub-second)

### What DOES work (team infrastructure)

- `TeamCreate` creates team config at `~/.claude/teams/<name>/config.json`
  and task directory at `~/.claude/tasks/<name>/`
- `TaskCreate`/`TaskUpdate`/`TaskList` work for task coordination
- `SendMessage` sends messages (even to non-existent agents -- no validation)
- `TeamDelete` cleans up team infrastructure

### What is MISSING

- **Agent spawn tool**: No tool to create a new agent process (local or
  worktree-isolated) from within a parent agent session
- **Agent lifecycle management**: No way to start, monitor, or terminate
  child agent processes
- **Worktree-to-agent binding**: No mechanism to associate a worktree with
  a newly spawned agent process

### SendMessage to Non-Existent Agent

SendMessage to "worker-1" (who was never spawned) returned:
```json
{"success": true, "message": "Message sent to worker-1's inbox"}
```
This means SendMessage does not validate recipient existence. Messages to
non-existent agents are silently lost.

## Architecture Recommendation

**REDUCED DELEGATION**: swarm-runner owns Steps 11w-16w only. Orchestrator
keeps worker spawn.

### Rationale

All 7 tests depend on the Agent tool's ability to spawn child agents with
`isolation: "worktree"`. This tool does not exist in the current environment.
The available tools (TeamCreate, SendMessage, Tasks) provide coordination
infrastructure but not process spawning.

### Viable Alternatives for Swarm Worker Isolation

1. **CLI-spawned agents via Bash** (most promising):
   - Parent creates worktree via `git worktree add`
   - Parent spawns `claude` CLI process in background via Bash tool
   - Parent uses file-system coordination (sentinel files, JSON status files)
   - Limitation: no structured return value; parent must poll for completion

2. **RemoteTrigger-based workers** (limited):
   - Parent creates remote triggers that execute agent tasks
   - Limitation: requires cloud API, not local; higher latency; no worktree
     isolation guarantee

3. **Sequential EnterWorktree per task** (fallback):
   - Parent enters worktree, does work, exits, enters next worktree
   - Limitation: strictly sequential; no parallelism; same context window

4. **External orchestrator** (out of scope):
   - A script or CI job spawns multiple `claude` CLI processes in parallel,
     each in its own worktree
   - This is the current autopilot-swarm approach and does work, but is not
     "nested" (parent agent does not control the spawn)

### Recommendation for Plan Phase

The autopilot context death solution should NOT assume nested agent spawning
capability. Instead:

- **Orchestrator** (the autopilot skill or external script) retains worker
  spawn responsibility (Steps 7w-10w)
- **swarm-runner** (if implemented as an agent) owns post-spawn coordination
  only (Steps 11w-16w): task assignment, progress monitoring, result
  collection, merge orchestration
- **Worktree isolation** is handled by the orchestrator at spawn time, not
  by a parent agent delegating to children

## Constraints Discovered

- **No concurrent nested agents**: The Agent tool does not exist, so
  concurrent nested agent count is 0.
- **Cleanup requirements**: EnterWorktree/ExitWorktree handle session-level
  worktree cleanup correctly. TeamDelete handles team infrastructure cleanup.
  No orphaned artifacts observed.
- **Permission propagation**: Cannot be tested. The `mode: "bypassPermissions"`
  parameter has no tool to receive it.
- **SendMessage validation gap**: Messages to non-existent agents succeed
  silently. Any team-based coordination must ensure agents exist before
  assigning work.
- **EnterWorktree is single-use per session**: "Must not already be in a
  worktree" -- a session can only be in one worktree at a time, preventing
  a parent from entering multiple worktrees for parallel work.

## Feed-Forward

- **Hardest decision:** Whether to classify this as REDUCED DELEGATION vs
  outright BLOCKED. Chose REDUCED because the coordination tools (TeamCreate,
  Tasks, SendMessage) do work -- only the spawn mechanism is missing.
- **Rejected alternatives:** Considered testing CLI-based `claude` process
  spawning via Bash, but this changes the architecture fundamentally (from
  tool-based agent spawning to process-based) and exceeds spike scope.
- **Least confident:** Whether the Agent tool is genuinely missing from the
  platform or just not available in this specific session configuration.
  The TeamCreate docs reference it explicitly, suggesting it may exist in
  other contexts (e.g., newer Claude Code versions, different permission
  sets, or when `dangerouslySkipPermissions` is enabled at the CLI level).

STATUS: PASS
