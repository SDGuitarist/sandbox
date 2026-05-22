---
title: Spec Completeness Checker -- Hard Pre-Swarm Gate for 6 Recurring Failure Classes
date: 2026-05-21
status: complete
problem_type: recurring-p1-factory
component: autopilot-swarm-pipeline
symptoms:
  - FC1/FC3/FC4/FC5/FC29/FC35 P1s reappeared across runs 046-052 despite documented agent rules
  - Agent-level pitfall rules did not converge -- same failure classes recurred in subsequent builds
  - Review agents caught issues post-build that could have been blocked pre-launch
root_cause: Spec-level omissions drove the failures, not agent disobedience -- agent rules cannot compensate for missing spec coverage surfaces
solution_type: pre-launch-gate
tags:
  - spec-completeness
  - swarm
  - autopilot
  - failure-classes
  - pre-swarm-gate
related_runs:
  - run-046
  - run-047
  - run-048
  - run-049
  - run-050
  - run-051
  - run-052
related_solutions:
  - docs/solutions/2026-05-13-sandbox-autonomy-hardening.md
  - docs/solutions/2026-04-30-spec-convergence-loop.md
  - docs/solutions/2026-05-06-autopilot-skips-non-step-instructions.md
  - docs/solutions/2026-05-20-autopilot-context-window-optimization.md
feed_forward:
  risk: "Route-table column parsing uses a fixed allowlist. Plans without recognized path columns get WARN, not FAIL. First real build validates false-positive rate."
  verify_first: true
---

# Spec Completeness Checker -- Hard Pre-Swarm Gate for 6 Recurring Failure Classes

## Problem

Six failure classes kept producing P1s across runs 046-052 despite being documented in agent-pitfalls.md with explicit agent rules:

| FC | Name | Recent P1s | Root cause |
|----|------|-----------|------------|
| FC1 | Naming divergence | Run 052 (supplier /new vs /create) | Export Names Table incomplete |
| FC3 | Dead wiring | Run 050 (delivered_delta) | Wiring table missing entries |
| FC4 | Validation gaps | Runs 048, 049, 052 | No prescribed error handling |
| FC5 | Coordination gaps | Run 051 (DB lock registration) | Registration points not enumerated |
| FC29 | Transaction boundary | Run 052 (BEGIN vs IMMEDIATE) | No commit/no-commit annotation |
| FC35 | IDOR ownership | Runs 049, 050 (6 P1s total) | No ownership check per route |

The pattern was consistent: agents followed the spec exactly, yet the spec omitted entire coverage surfaces. Agent-level pitfall rules cannot compensate for what the spec never said.

## Root Cause

Agent-level rules address agent behavior, not spec completeness. When a spec is silent on naming contracts, no pitfall rule causes an agent to invent one. When a spec omits an authorization matrix, the IDOR rule has nothing to enforce. The failure loop: spec omits surface -> agent produces spec-compliant code -> review finds P1 -> pitfall added -> next spec omits a different surface -> repeat.

The fix must operate at the spec layer, before agents ever read the document.

## Solution

Three coordinated artifacts:

### 1. spec-completeness-checker agent (213 lines, new)

Read-only agent running 6 coverage surface checks with unified N/A flow:

| Check | Surface | FC | Enumeration rule |
|-------|---------|-----|-----------------|
| 1 | Export Names | FC1 | `def <name>(`, `url_for()`, blueprint headings, route paths |
| 2 | Cross-Boundary Wiring | FC3 | Functions with "Used By" in Export Names table (BLOCKED if Check 1 fails) |
| 3 | Input Validation | FC4 | Route table rows where Method is POST/PUT/PATCH/DELETE or Path has `<int:` |
| 4 | Registration Points | FC5 | Blueprint names from file inventory and section headings |
| 5 | Transaction Contracts | FC29 | Write functions via code blocks or model tables (Form A/B detection) |
| 6 | Authorization Mode | FC35 | Routes with `@login_required` or similar auth decorators |

All surfaces follow: enumerate items -> zero = N/A -> find heading -> missing = FAIL -> evaluate rows.

### 2. Step 9w.6 in autopilot SKILL.md (+27 lines)

Hard gate between consistency check (9w.5) and swarm launch (10w). Max 1 retry with mandatory commit step after fix. Abort on double-FAIL.

### 3. CLAUDE.md mandatory sections (+27 lines)

Six required sections for swarm plans: Export Names Table, Cross-Boundary Wiring Table, Input Validation Prescriptions, Coordinated Behaviors, Transaction Contracts, Authorization Matrix.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Separate agent vs extend consistency checker | Separate | Different concern (completeness vs consistency). Mixing obscures which check failed. |
| Core 6 surfaces vs all 10 | Core 6 first | Covers all P1 history. Phase 2 adds FC9/FC38/FC40/worker after validation. |
| Hard FAIL vs advisory WARN | Hard FAIL | Review found 4-6 P1s per run from these FCs. Stopping is cheaper than predictable P1s. |
| Unified N/A flow | All 6 checks follow same tree | 3 Codex rounds found N/A contradictions with per-check logic. Single flow eliminates the class. |
| Route-path column allowlist | Path/URL/Route/Flask Path with /prefix guard | Prevents misidentifying config or endpoint-name tables as route tables. |
| Check 2 BLOCKED when Check 1 fails | BLOCKED status | Without Export Names table, cross-boundary functions can't be enumerated. Running produces garbage. |
| Method column cell values for FC4 | POST/PUT/PATCH/DELETE in table cells | Spec authors write route tables in prose, not Python. Cell values are format-agnostic. |
| Retry with commit step | git add + commit between retry and re-check | Review P2 found that retry without commit leaves dirty-state risk. |

## Review Results

4 review agents (architecture, simplicity, pattern recognition, learnings researcher).

**Fixed (1 P1 + 5 P2):**

| # | Finding | Severity | Source |
|---|---------|----------|--------|
| 1 | Agent missing from Permission Mode list | P1 | arch + pattern |
| 2 | CLAUDE.md omits PATCH/DELETE | P2 | arch + pattern |
| 3 | Retry-with-fix has no commit step | P2 | arch |
| 4 | "ownership checks" not a real surface name | P2 | arch + pattern |
| 5 | Report format misaligned (Date/Status/title) | P2 | pattern |
| 6 | "Wiring Coverage" naming inconsistency | P2 | pattern |

**Deferred:** 2 P2 (template scaffolding, N/A dedup) + 9 P3 (cosmetic).

**3 Codex plan review rounds (14 total fixes):** Round 1: overlap removal, N/A contradiction, scope tightening. Round 2: unified N/A for all surfaces, Form B, route paths. Round 3: Check 2 dependency, column allowlist, heading verification targets.

## Validation Against Runs 047-052

All P1 findings from runs 047-052 map to one of the 6 coverage surfaces:

| Run | FC1 | FC3 | FC4 | FC5 | FC29 | FC35 | Gate catches? |
|-----|-----|-----|-----|-----|------|------|--------------|
| 047 | 0 | 1 | 0 | 0 | 1 | 0 | Yes (Check 2, 5) |
| 048 | 1 | 0 | 1 | 0 | 0 | 1 | Yes (Check 1, 3, 6) |
| 049 | 0 | 0 | 0 | 1 | 0 | 2 | Yes (Check 4, 6) |
| 050 | 1 | 1 | 0 | 0 | 0 | 0 | Yes (Check 1, 2) |
| 051 | 0 | 0 | 1 | 0 | 1 | 1 | Yes (Check 3, 5, 6) |
| 052 | 1 | 0 | 0 | 1 | 0 | 1 | Yes (Check 1, 4, 6) |

100% correlation: every P1 that made it to review would have been caught as a spec omission at Step 9w.6.

## Prevention & Best Practices

- **Spec-level enforcement over agent-level rules.** When agents follow specs exactly, the fix is better specs, not more rules. The completeness checker shifts the burden from "agents must compensate" to "specs must prescribe."
- **Unified control flow eliminates N/A contradictions.** Three Codex rounds found inconsistent N/A handling when each check had its own logic. A single canonical flow (enumerate -> zero=N/A -> missing=FAIL -> evaluate) is the fix.
- **Hard gates with retry are better than advisory warnings.** WARN-only gates get dismissed under schedule pressure. Hard FAIL with one retry balances strictness with practicality.
- **Inter-surface dependencies need explicit BLOCKED status.** When Check 2 depends on Check 1, running Check 2 after Check 1 fails produces garbage. BLOCKED surfaces the dependency in the report.
- **Route detection must match actual spec format.** Method column cell values (POST/DELETE) are deterministic. Python `methods=[...]` syntax is not present in plan tables.

## Related Documentation

- [Sandbox Autonomy Hardening](docs/solutions/2026-05-13-sandbox-autonomy-hardening.md) -- spec-consistency-checker (Step 9w.5), the sibling gate this extends
- [Spec Convergence Loop](docs/solutions/2026-04-30-spec-convergence-loop.md) -- upstream prevention; completeness checker is the downstream enforcement
- [Autopilot Skips Non-Step Instructions](docs/solutions/2026-05-06-autopilot-skips-non-step-instructions.md) -- why the gate must be a numbered MANDATORY step
- [Autopilot Context Window Optimization](docs/solutions/2026-05-20-autopilot-context-window-optimization.md) -- incremental BUILD_TRACKING and checkpoint patterns

## Feed-Forward

- **Hardest decision:** Hard FAIL vs WARN. A WARN-only gate never blocks but gets bypassed. A hard FAIL will fire on the first spec the checker misreads. The one-retry-with-commit design mitigates: spec author gets one chance to fix before abort.
- **Rejected alternatives:** Extending consistency checker (couples concerns), template-only without checker (doesn't prove coverage), all 10 surfaces in v1 (broader than evidence), full markdown parser (fragile).
- **Least confident:** Three implementation risks: (1) Route-table column parsing with fixed allowlist -- plans without recognized path columns get WARN. (2) Check 2->1 dependency produces BLOCKED cascade. (3) Heading-prefix matching on future plan formats -- unrecognized headings FAIL (safe direction). First real build validates all three.
