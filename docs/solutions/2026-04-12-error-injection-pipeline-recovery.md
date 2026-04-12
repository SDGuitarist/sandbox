---
title: "Error Injection Testing -- Pipeline Recovery Validated"
date: 2026-04-12
category: integration-issues
tags: [error-injection, assembly-fix, spec-contract-checker, pipeline-recovery, swarm]
module: error-test-app
symptom: "Untested assumption: verification pipeline recovers from spec violations"
root_cause: "All 8 prior builds had 0-2 minor post-assembly fixes. The contract-check → assembly-fix → re-verify cycle had never been exercised with a real spec violation."
---

# Error Injection Testing -- Pipeline Recovery Validated

## Problem

The swarm pipeline has a 3-stage verification system (contract check → assembly-fix → smoke test) that was designed to catch and recover from agent errors. But in 8 builds, it was never truly tested -- all builds succeeded with at most minor tweaks. The failure recovery path was untested infrastructure.

## Test Design

Built a minimal Flask bookmark app with 3 agents. Deliberately instructed the routes agent to use WRONG function names:
- `get_all_items` instead of `get_all_bookmarks`
- `add_item` instead of `create_bookmark`  
- `remove_item` instead of `delete_bookmark`

This simulates the most common real swarm failure: agents inventing names instead of following the spec.

## Results

| Step | Expected | Actual | Status |
|------|----------|--------|--------|
| Spec contract check | Detect mismatches | Found 6/6 mismatches | PASS |
| Assembly-fix | Correct routes.py | Fixed all 4 lines | PASS |
| Smoke test | App works after fix | All routes 200 | PASS |

### What the Contract Checker Found

15 total checks: 9 PASS, 6 FAIL. All failures in routes.py -- correctly identified the import line and 3 call sites. The report included exact line numbers and the correct function names from the spec.

### What Assembly-Fix Did

Read the contract check report. Made 4 edits to routes.py (import line + 3 call sites). Did NOT touch models.py (which was correct). Committed the fix in one pass.

## Risk Resolution

**Flagged risk:** Whether assembly-fix can correct a spec violation from a contract-check report alone.

**What happened:** It worked perfectly. The contract-check report provided enough information (wrong name, correct name, line number) for assembly-fix to make targeted corrections without understanding the broader app logic.

**Lesson:** The contract-check → assembly-fix pipeline works when the contract-check report includes: (1) the specific file and line, (2) what's wrong, (3) what the spec says it should be. The assembly-fix agent doesn't need to understand the app -- it just applies the diff between actual and spec.

## Key Insight

The verification pipeline is a safety net, not a quality tool. It catches mechanical errors (wrong names, missing imports, type mismatches) but NOT design errors (wrong algorithm, missing edge cases, bad UX). The pipeline works because spec violations are the most common swarm failure mode, and they have unambiguous fixes.

## Review Summary (Post-Fix)

4-agent review (security, architecture, pattern, simplicity) on the post-fix code:
- **P1: 1** (hardcoded secret key) — won't fix, test harness
- **P2: 7** (XSS, debug mode, input limits, relative paths, type hints, init_db, style) — won't fix, all production concerns irrelevant to test harness
- **P3: 8** (cosmetic: PEP 8, imports, blueprint name, HTML boilerplate, unpinned deps, no auth, template inheritance, flash messages) — won't fix

**Zero code changes applied.** All findings are production concerns that don't apply to a pipeline test harness. The assembly-fix agent produced clean, spec-compliant code with no residual error injection artifacts.

## Stats

- **Agents:** 3 (1 with injected error)
- **Injected errors:** 6 (1 import line + 3 call sites x 2 = wrong import + wrong usage)
- **Contract check findings:** 6/6 detected
- **Assembly-fix attempts:** 1 (succeeded on first try)
- **Smoke test after fix:** All pass
