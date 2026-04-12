---
title: "Error Injection Testing -- Swarm Pipeline Failure Paths"
date: 2026-04-12
status: complete
type: brainstorm
---

# Error Injection Testing

## What We're Building

A minimal Flask app (3 agents, ~8 files) where ONE agent is deliberately given wrong instructions to trigger a spec violation. The goal is not the app -- it's testing whether the verification pipeline (spec-contract-checker, smoke-test-runner, assembly-fix) detects and recovers from the error.

## Test Scenarios

### Scenario 1: Spec Violation (function name mismatch)
- The routes agent is told to call `get_all_items()` instead of the spec's `get_all_bookmarks()`
- Expected: spec-contract-checker catches the mismatch
- Recovery: assembly-fix agent corrects the function name

### Why This App

Minimal bookmark list app:
- 1 table (bookmarks: id, url, title)
- 3 functions (get_all, create, delete)
- 3 routes (list, create, delete)
- 1 template (list.html)
- No tags, no relationships, no complexity -- just enough to have a swarm

## What We're Testing

1. Does spec-contract-checker detect wrong function names?
2. Does assembly-fix correct the error?
3. Does the pipeline continue after fix?
4. Does smoke-test-runner verify the fix worked?

## Feed-Forward

- **Hardest decision:** What error to inject. Chose function name mismatch because it's the most common real-world swarm failure (from task-tracker-categories scalar return bug).
- **Rejected alternatives:** (1) Merge conflict injection -- hard to control with worktrees. (2) Syntax errors -- too easy to detect, doesn't test spec awareness. (3) Missing files -- caught by ownership gate, not the interesting failure path.
- **Least confident:** Whether assembly-fix can actually correct a function name mismatch from just the contract-check report. It's never been tested on a real failure -- all prior builds had 0 assembly fixes needed.
