STATUS: PASS (with observability nuances recorded)

# Spike 0b — TaskStop observability (plan §0.0b)

## Procedure
- Spawned a background worker Agent (`swarm-SPIKE0B-live`, agentId `a8d8b57b6dd2bb38f`)
  running `ping -c 180 127.0.0.1` in the FOREGROUND (keeps the agent's turn alive ~180s).
- Confirmed it was genuinely running (`status: running`, actively in the ping Bash call).
- Called `TaskStop` on its task_id.
- Confirmed termination: `TaskStop` returned success ("Successfully stopped task"), and a
  `killed` status + task-notification `<status>killed</status>` followed immediately.

## Verdict
**PASS** — `TaskStop` reliably terminates a genuinely-running worker Agent, and termination is
observable near-immediately as `killed`. The §3.1 "prove zero live workers" gate is VIABLE via
`TaskStop` + the killed/completion signal.

## Observability nuances (feed into §3.1 design)
1. **`TaskList` does NOT track background Agents.** A `TaskList` call returned "No tasks found"
   while a background agent was live. => §3.1 must prove liveness via each recorded task_id
   (`TaskStop` + its return/notification), NOT by enumerating `TaskList`. The plan's §3.1/§5
   name-prefix enumeration must therefore be built on the recorded roster task_ids, and the
   harness's own completion notifications — not on `TaskList`.
2. **An agent can self-COMPLETE while leaving an orphaned background child.** First attempt:
   a worker told to `sleep 200` chose to background it (foreground sleep is blocked) and the
   AGENT then returned `completed` at ~12s while the child bash `sleep` kept running detached.
   => "agent completed" is the terminal signal for the AGENT, but a completed agent may leave a
   detached background shell. For the wave loop this is low-risk (the child dies with the agent's
   context and is not a worker branch author), but §3.1 should note that "terminal" refers to the
   Agent task, and prove-zero-live is about Agent tasks, not arbitrary detached shells.
3. **Do NOT call `TaskOutput` on a local_agent task for status** — it returns the full JSONL
   transcript (huge). Use the `TaskStop` return value + the completion/killed task-notification.

## Accepted-rule alignment
The plan's fail-closed rule ("always abort on timeout when termination cannot be proven") remains
correct; 0b shows termination CAN be proven for a live agent, so the common path is not
always-abort — it aborts only when a `TaskStop` cannot confirm a `killed`/terminal transition.

## §3.1 orphaned-detached-child policy alignment (rev5, Codex Finding 2)
Nuance (2) above (a completed Agent can leave an orphaned detached background child) is now given
an EXPLICIT policy in plan §3.1 rather than left as an observation:
- Orphaned detached child shells are OUT of scope for the "prove zero live" gate (which proves the
  Agent TASK is terminal). Rationale: (i) assembly cherry-picks from each worker's COMMITTED
  branch head, never a live worktree, so a post-terminal writer cannot change the assembled INPUT
  unless it makes a git COMMIT; (ii) a detached child's tool calls are invisible to the PreToolUse
  firebreak — the pre-existing declared F6 residual, which this plan neither expands nor fixes.
- CONTAINMENT for the one assembly-corrupting case (a post-terminal COMMIT advancing a worker
  branch): §3.1 records `terminal_head_sha` at the terminal instant and re-reads the live branch
  head before assembly AND before cleanup; a mismatch ⇒ ABORT. The same equality is enforced by
  the authoritative verifier (plan §7 `verify_wave --wave K` reject-set).
This is a documented residual + a cheap deterministic containment, not a design change — 0b's
recorded evidence is fully consistent with the §3.1 policy.
