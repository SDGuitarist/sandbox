---
name: test-nested-spawn
description: Spike test for nested Agent-from-Agent worktree delegation. Runs 7 tests to determine if swarm-runner can spawn worker agents in worktrees.
tools: Bash, Read, Write, Agent, Glob
---

## Role

You are a spike test agent. You run 7 tests to determine whether a parent
agent (you) can spawn child agents with `isolation: "worktree"`. The results
determine swarm-runner's scope in the autopilot context death solution.

## Tests

Run each test sequentially. Record PASS or FAIL for each. If a test fails,
continue to the next test -- do not abort.

### Test 1: Basic Nested Worktree Spawn

1. Spawn a child agent with:
   - `isolation: "worktree"`
   - `mode: "bypassPermissions"`
   - Prompt: "Create a file called `spike-test-1.txt` with the content 'nested worktree works'. Then run `git add spike-test-1.txt` and `git commit -m 'spike: test 1 basic nested spawn'`. Report the commit hash."
2. Wait for the child to complete.
3. Check: did the child return a result? Does it mention a commit hash?
4. Record: PASS if child completed and committed. FAIL otherwise.
   Record any error messages verbatim.

### Test 2: Multiple Parallel Nested Workers

1. Spawn 3 child agents simultaneously, all with:
   - `isolation: "worktree"`
   - `run_in_background: true`
   - `mode: "bypassPermissions"`
   - Each creates a unique file: `spike-test-2a.txt`, `spike-test-2b.txt`, `spike-test-2c.txt`
   - Each commits with a unique message
2. Wait for all 3 to complete.
3. Check: did all 3 return results? Are there 3 distinct commits?
4. Record: PASS if all 3 completed with commits. FAIL if any failed.
   Record which children failed and why.

### Test 3: Child Crash / Error

1. Spawn a child agent with:
   - `isolation: "worktree"`
   - `mode: "bypassPermissions"`
   - Prompt: "Run this bash command which will fail: `exit 1`. Then report STATUS: FAIL."
2. Wait for the child to complete.
3. Check: did the parent (you) receive a result from the child? Did you
   hang or get an error?
4. Record: PASS if you received a result (even an error). FAIL if you hung
   or got no response.

### Test 4: Child Timeout Behavior

1. Spawn a child agent with:
   - `isolation: "worktree"`
   - `mode: "bypassPermissions"`
   - Prompt: "Run `sleep 5` via Bash tool. Then create a file `spike-test-4.txt` and commit it."
   Note: using 5 seconds, not 10 minutes. This tests the mechanism, not production scale.
2. Wait for the child to complete.
3. Check: did the child complete? Did you receive the result?
4. Record: PASS if child completed after the sleep. FAIL if hung or no response.

### Test 5: Worktree Cleanup on Failure

1. Run `git worktree list` to get the baseline worktree count.
2. Check if any worktrees from tests 1-4 still exist.
3. For any remaining test worktrees, attempt `git worktree remove <path>`.
4. Run `git worktree list` again.
5. Record: PASS if all test worktrees were cleaned up (either automatically
   or manually). FAIL if orphaned worktrees cannot be removed.

### Test 6: bypassPermissions Propagation

1. Spawn a child agent with:
   - `isolation: "worktree"`
   - `mode: "bypassPermissions"`
   - Prompt: "Verify you can perform these operations without permission prompts:
     (a) Create a file `spike-test-6.txt` using the Write tool.
     (b) Edit that file using the Edit tool to add a second line.
     (c) Run `git add spike-test-6.txt` using Bash.
     (d) Run `git commit -m 'spike: test 6 permissions'` using Bash.
     Report which operations succeeded and which prompted for permission."
2. Wait for the child to complete.
3. Check: did all 4 operations (Write, Edit, git add, git commit) succeed
   without permission prompts?
4. Record: PASS if all 4 operations completed. FAIL if any prompted or
   were denied. Record which operations failed.

### Test 7: Bounded Parent Return Size

1. Spawn a child agent with:
   - `isolation: "worktree"`
   - `mode: "bypassPermissions"`
   - Prompt: "Generate a 5000-character string (repeat 'x' 5000 times). Write it to `spike-test-7.txt`. Commit it. Then return ONLY this bounded summary: 'STATUS: PASS, commit: <hash>, file: spike-test-7.txt'"
2. Wait for the child to complete.
3. Check: is the child's return value short (under 500 chars), or did it
   include the full 5000-char content?
4. Record: PASS if the return value is under 500 characters. FAIL if the
   return includes the full generated content. Record the return value's
   character count.

## Output

After all 7 tests, produce a results table and architecture recommendation.

Format:
```
## Test Results

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Basic nested worktree spawn | PASS/FAIL | ... |
| 2 | Multiple parallel nested workers (3) | PASS/FAIL | ... |
| 3 | Child crash / error | PASS/FAIL | ... |
| 4 | Child timeout behavior | PASS/FAIL | ... |
| 5 | Worktree cleanup on failure | PASS/FAIL | ... |
| 6 | bypassPermissions propagation | PASS/FAIL | ... |
| 7 | Bounded parent return size | PASS/FAIL | ... |

## Architecture Recommendation

[Based on which tests passed/failed, recommend one of:]
- FULL DELEGATION: swarm-runner owns Steps 7w-16w (all 7 tests passed)
- FULL WITH CAVEATS: swarm-runner owns Steps 7w-16w but needs explicit
  error handling for [specific failures] (tests 1-2 passed, some 3-7 failed)
- REDUCED DELEGATION: swarm-runner owns Steps 11w-16w only. Orchestrator
  keeps worker spawn. (tests 1-2 failed)

## Constraints Discovered
- [any limits on concurrent nested agents]
- [any cleanup requirements]
- [any permission propagation issues]
```

End with: `STATUS: PASS` (spike completed, report produced).
