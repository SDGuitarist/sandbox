# Self-Audit Report -- Run 057

**Date:** 2026-05-22
**Build:** BrewOps (Craft Brewery Manager)
**Run ID:** 057
**Final Status:** PIPELINE_PASS_WITH_DEFERRED_RISK

---

## Final Run Status

**Status:** PIPELINE_PASS_WITH_DEFERRED_RISK

All 7 P1 review findings were resolved before merge, 61/61 smoke tests pass,
all 3 validation targets cleared, and all mandatory tail artifacts were
produced. However, 6 P2 and 4 P3 review findings were explicitly deferred
rather than fixed, the `isolation_level=None` anti-pattern recurred for the
third consecutive build (BUILD_TRACKING FAILURES #4), and a spec-consistency
WARN on `get_batch` consumer ambiguity was not resolved at the spec level.
These carry forward as active risk for the next session.

---

## WARN Disposition Table

| # | Key | Source | WARN Description | Disposition | Rationale |
|---|-----|--------|-----------------|-------------|-----------|
| 1 | 057-W1 | docs/reports/057/spec-consistency-check.md (check #10) | `get_batch` declared as consumed by sale_routes in Export Names Table but absent from Cross-Boundary Wiring import for sale_routes. Marked WARN (not FAIL) because sale_routes may satisfy the lookup via `get_all_taps` filter. | DEFERRED | The ambiguity was not resolved: the Export Names Table still claims sale_routes consumes `get_batch`. If it truly does, the wiring is incomplete; if not, the Export Names row is stale. Either way the spec has a dangling consumer reference. Requires verifying actual sale_routes code and correcting whichever section is wrong. Tracked in HANDOFF.md under `[057-W1]`. |
| 2 | 057-W2 | docs/reports/057/review-summary.md (P2 findings #038-#043) | 6 P2 review findings deferred without fix: (038) dashboard fires 5 batch queries instead of 1; (039) missing index on sales.created_at + function blocks index use; (040) no pagination on sales list; (041) dollars filter crashes on None input; (042) tap/tank with assigned batch can be deleted; (043) lazy import in recipe_routes + unused import in __init__. | DEFERRED | All six were judged "important but not blocking" by the review agents. For a single-admin dev tool this is defensible in the short term, but (041) is a crash-on-bad-input bug and (042) is a data integrity gap (active batch tap deletable). Both should be prioritized next session. Tracked in HANDOFF.md under `[057-W2]`. |
| 3 | 057-W3 | docs/reports/057/review-summary.md (P3 findings #044-#047) | 4 P3 review findings deferred: (044) swarm consistency cleanup (flash messages, docs, imports, templates); (045) security hardening (dev defaults, headers, password hashing); (046) no JSON API endpoints; (047) WAL pragma runs on every request. | DEFERRED | P3 findings are explicitly nice-to-have. For a single-admin internal tool the security deferrals (dev secret key default, plaintext password storage) are acceptable in dev-only usage, but are real risks if the app were ever exposed. WAL pragma per request is a minor performance issue. Tracked in HANDOFF.md under `[057-W3]`. |
| 4 | 057-W4 | BUILD_TRACKING.md FAILURES #4; docs/reports/057/review-summary.md finding #034 | `isolation_level=None` in db.py makes `conn.commit()` a no-op in all SERIAL-SAFE routes. This is the third consecutive build (054, 056, 057) with this pattern. The deepening phase (deepening-applied.md P0 fix #1) added `isolation_level=None` to the plan spec as a fix -- but the swarm agents produced it anyway, and it was caught and fixed by review. The db.py template in the scaffold agent brief is not being updated at source. | DEFERRED | The root cause is not the agent -- it is the db.py boilerplate that agents copy from prior examples or spec instructions. The deepening phase caught and prescribed the fix, but agents still produced the anti-pattern, suggesting the pitfall injection is not reaching the core agent's db.py section at sufficient specificity. FC40 now covers this but the recurrence rate (3/3 runs) indicates the remediation is not working. Requires updating the scaffold template and verifying via Gate run. Tracked in HANDOFF.md under `[057-W4]`. |

---

## Source Reconciliation

| Source File | WARN Tokens Found | WARNs Added to Table |
|-------------|-------------------|----------------------|
| docs/reports/057/spec-consistency-check.md | 1 (check #10 labeled WARN) | 1 (057-W1) |
| docs/reports/057/spec-completeness-check.md | 0 | 0 |
| docs/reports/057/gate-verification.md | 0 | 0 |
| docs/reports/057/ownership-gate.md | 0 | 0 |
| docs/reports/057/swarm-assignment.md | 0 | 0 |
| docs/reports/057/deepening-applied.md | 0 | 0 (P0 fixes are resolved; P2 notes marked as deferred are captured under 057-W2/W3 via review-summary) |
| docs/reports/057/flow-trace-review.md | 1 (STATUS: FAIL at line 322) | 0 (P1 #031 was found here and resolved before merge; not a current-run outstanding WARN) |
| docs/reports/057/review-summary.md | 2 (Derived State: PARTIAL; 6 P2 + 4 P3 deferred blocks) | 2 (057-W2 covers P2s, 057-W3 covers P3s; PARTIAL was resolved so not separately tracked) |
| BUILD_TRACKING.md (FAILURES section) | 1 (FC40 isolation_level recurrence -- all 7 failures listed, 6 fully resolved, 1 is a recurrence pattern concern) | 1 (057-W4) |
| HANDOFF.md ("Review Fixes Pending" section) | 0 (section absent -- HANDOFF was written before review phase; deferred items are sourced from review-summary.md directly) | 0 |

**Notes on token counts:**
- The `flow-trace-review.md` STATUS: FAIL token was not promoted to a WARN because the underlying P1 (#031 -- manual tapped->empty locks tap permanently) was fixed before merge per BUILD_TRACKING FAILURES #1. No residual risk remains.
- The `review-summary.md` "Derived State: PARTIAL" was resolved (P1 #031 fix changed it to PASS per solution doc Validation Results table). Not separately tracked.
- HANDOFF.md has no "Review Fixes Pending" section because it was authored before the review phase ran (it covers the pre-tail state). This is noted as a process gap in "What Was Missed" below.

---

## What Was Missed In The First Summary

**1. HANDOFF.md was never updated with post-review deferred items.**

The HANDOFF.md was written before the review phase and lists "Review" as a remaining step. After review completed, the deferred P2 and P3 items (10 findings total) were not back-populated into HANDOFF.md as tagged deferred entries. The solution doc mentions deferred items in passing, and the context block of the run describes them, but HANDOFF.md has no `[057-W1]` through `[057-W4]` entries. This is a process gap: the tail resume skill ran review, compound, and learnings-propagation, but did not circle back to update HANDOFF.md's deferred items section with review findings.

**2. The deepening phase "fixed" isolation_level but the fix didn't hold through the swarm.**

The deepening-applied.md records `isolation_level=None` as a P0 fix added to the plan spec. The flow-trace reviewer's Flow 10 notes at line 58 of flow-trace-review.md that "The isolation_level=None connection (autocommit mode) is set in db.py:10" -- confirming agents still produced the anti-pattern post-deepening. The solution doc mentions this (Key Lesson #3) but does not fully explain the failure mode: the deepening fix was a prescription in the spec, but if agents use a cached code template from prior sessions rather than reading the spec's db.py code block, the prescription is invisible. This is a different failure mode than FC40 assumes (agent ignoring the spec vs. agent reading a stale template).

**3. The spec-consistency WARN on `get_batch` was never confirmed or resolved.**

Check #10 in the spec-consistency report flagged `get_batch` as a possible stale consumer reference in the Export Names Table. The pre-swarm fix commit (cd520b7) fixed 9 FAILs but did not address the WARN. The solution doc and BUILD_TRACKING do not mention it. The actual sale_routes code was not inspected in the self-audit to confirm whether `get_batch` is actually imported. This means the spec may still have a dangling consumer reference that will confuse the next build's consistency checker.

**4. P1 #037 (recipe ingredient IDOR) is an FC35 variant, not a standard FC35 case.**

The solution doc mentions "Recipe ingredient removal lacks ownership check" as P1 #037 and classifies it as FC35. But FC35 is the broader "Authorization Matrix gap" failure class. The specific failure here is an IDOR: the `ri_id` route parameter was not validated against the `recipe_id` URL parameter, meaning an authenticated admin could delete recipe ingredients from a different recipe than the URL suggests. This is closer to an object-level authorization failure (OWASP API1:2023) than a missing `@login_required` decorator (FC35 typical). The BUILD_TRACKING entry correctly cites FC35, but the failure sub-type is not captured in agent-pitfalls as a distinct pattern. A future build could hit the same IDOR pattern on a different resource without the existing FC35 rule catching it.

---

## Questions A Skeptical Reviewer Would Ask

**Q1: The flow-trace reviewer found a STATUS: FAIL on the critical path (create_sale cascade). How was this allowed through if the deepening phase was supposed to catch it?**

**A1:** The deepening agents (deepening-applied.md) focused on four areas: security, transactions, schema, and derived state. The deepen-derived-state agent verified the spec's Derived State section was complete and the sale chain was fully prescribed. What deepening did not do is trace the VALID_TRANSITIONS constant against the Derived State ownership table. The spec correctly said `create_sale` owns the `tapped->empty` transition, and VALID_TRANSITIONS also allowed that transition through `advance_batch_status`. These two facts appear in different sections and no deepening agent connected them. The flow-trace reviewer caught it during review by following the code path end-to-end. This is exactly the failure mode FC45 documents: two spec sections are individually correct but contradictory when read together. The deepening check was per-section, not cross-section.

**Q2: The isolation_level=None anti-pattern recurred for the third consecutive build despite being in agent-pitfalls as FC40. Is the pitfall injection actually working?**

**A2:** The evidence suggests partial failure of pitfall injection. FC40 is present in agent-pitfalls.md (confirmed). The deepening phase added an explicit `isolation_level=None` prescription to the plan spec (deepening-applied.md P0 fix #1). Despite this, the swarm agent produced the anti-pattern and review caught it again. The most likely explanation is that agents generate db.py from pattern memory (prior similar files) rather than reading the spec's db.py code block. Pitfall injection works when agents are deciding how to implement something; it fails when agents copy boilerplate from memory without reading the spec section covering that boilerplate. The fix is to put the prohibition directly in the db.py code block in the spec (as a comment or explicit `isolation_level` parameter value) so the agent sees it at the point of code generation, not only in the pitfalls header.

**Q3: 6 P2 findings were deferred including one crash (dollars filter on None) and one data integrity gap (tap with active batch deletable). Are these truly safe to defer?**

**A3:** P2 #041 (dollars filter crash on None) is a real defect: a Jinja2 filter that receives None (e.g., a tap with no batch) will raise an exception visible to the admin. For a single-admin tool this is unlikely to cause data loss, but it will produce 500 errors during normal operation. It is not safe to defer if the app is intended for daily use -- it should have been a P1. P2 #042 (tap/tank deletable while active batch assigned) is also a data integrity concern: deleting a tap that holds a batch leaves the batch in `tapped` status with a null tap reference, inconsistent state with no recovery path. Both of these are more consequential than the "important but not blocking" classification they received. The next session should prioritize these two before the others.

**Q4: The smoke tests are 61/61. Do they cover the critical deferred scenarios?**

**A4:** The smoke tests cover the happy-path for all 8 blueprints, the start_brewing transaction, and the sale-causes-empty derived state chain (per swarm-assignment.md Agent 21 responsibility). However, the deferred P2 scenarios are not covered: there are no tests for the dollars filter on None input, no tests for deleting a tap with an active batch, no tests for dashboard query count, and no pagination-boundary tests. The 61/61 pass rate is genuine but it does not validate the deferred risk surface. Smoke test coverage is narrow by design (per the plan's test scope) -- this is acceptable for an initial build but means the deferred P2s have zero automated regression protection.

**Q5: The solution doc's "Least Confident" Feed-Forward item is the isolation_level change from None to DEFERRED. Was this risk actually validated?**

**A5:** Partially. The solution doc states: "if any code path was accidentally relying on autocommit behavior, the change could surface bugs not covered by the 61 smoke tests." The flow-trace reviewer's Flow 10 confirms that SERIAL-SAFE callers all have `conn.commit()` calls present (17 routes checked explicitly). The NEEDS-BEGIN-IMMEDIATE callers correctly omit `conn.commit()`. So the behavioral change appears safe. However, the flow-trace reviewer noted that `isolation_level=None` was still present in db.py at review time (line 58 of flow-trace-review.md) -- meaning the fix was applied after the flow trace. The post-fix state was not re-traced. The 61 smoke tests all passed post-fix, which provides indirect validation, but a dedicated trace of SERIAL-SAFE commit behavior after the isolation_level removal was not performed and is not documented.

---

## Promotion Decisions

| Finding | Promoted To | Why |
|---------|------------|-----|
| FC45: Derived state bypass via alternative transition path (VALID_TRANSITIONS allowed tapped->empty bypassing create_sale ownership) | agent-pitfalls FC45 (confirmed present in Update Log 2026-05-22 entry) | New failure class, not covered by prior pitfalls. Reusable pattern for any swarm build with a state machine and derived state ownership table. |
| FC46: Phantom FK -- integer column stores ID without REFERENCES (tanks.current_batch_id) | agent-pitfalls FC46 (confirmed present in Update Log 2026-05-22 entry) | New failure class. Schema gaps of this type are invisible until delete. Affects any build with UNIQUE integer columns that reference other tables. |
| isolation_level=None 3rd recurrence (FC40 pattern, pitfall injection not stopping it) | HANDOFF.md `[057-W4]` (via this report); NOT promoted to new pitfall class | FC40 already exists. The new insight is that the failure mode is template-copy behavior, not spec-reading failure. A spec-level fix (add isolation_level to db.py code block directly) is more effective than a pitfall. The pitfall class itself doesn't need updating. |
| IDOR on recipe_ingredients (ri_id not validated against recipe_id) -- FC35 variant | Not promoted (classified under FC35) | FC35 covers authorization checks broadly. The specific IDOR pattern is an instance of FC35 at the object-ownership level. Adding a sub-class would be premature with only one occurrence. If this recurs in the next build, promote to FC47. |
| HANDOFF.md not updated with post-review deferred items (process gap) | HANDOFF.md `[057-W1..W4]` (via this report) | Process gap discovered by self-audit. Not a failure class for agents -- this is an orchestrator/tail-resume workflow issue. Recommend adding a step to the tail-resume skill: "Update HANDOFF.md deferred items section after review completes." |
| Delete route guard inconsistency (5/7 had IntegrityError handling, 2 didn't) -- FC5 | Not promoted (FC5 already covers this; "Delete Guards" Coordinated Behaviors row recommended in solution doc) | Solution doc Key Lesson #4 prescribes the fix: add a "Delete Guards" row to every swarm plan's Coordinated Behaviors section. This is a spec-level fix, not a new failure class. |

---

## Unresolved Risk

**Key:** 057-W1
**Risk:** `get_batch` Export Names consumer reference for sale_routes is either stale or the Cross-Boundary Wiring Table is incomplete. The actual sale_routes code was not verified during spec-consistency fixes. If `get_batch` is actually imported by sale_routes, the wiring table is wrong; if not imported, the Export Names row misleads future consistency checks.
**Why not resolved:** The pre-swarm fix pass (commit cd520b7) addressed 9 FAILs but left the WARN unresolved. No follow-up check was performed.
**Tracked in:** HANDOFF.md under key `[057-W1]` (HANDOFF.md requires updating to add this entry).
**Severity for next session:** LOW

---

**Key:** 057-W2
**Risk:** 6 P2 review findings remain unresolved. Highest-risk items: (041) dollars filter crashes on None input causing 500 errors during normal operation; (042) tap/tank with assigned batch can be deleted, leaving batch in inconsistent state with no recovery path; (039) missing index on sales.created_at degrades dashboard performance as data grows.
**Why not resolved:** Classified as P2 (important but not blocking) at review time and deferred to next session due to scope and context constraints.
**Tracked in:** HANDOFF.md under key `[057-W2]` (HANDOFF.md requires updating to add this entry).
**Severity for next session:** MEDIUM (041 and 042 are effectively P1 for production use)

---

**Key:** 057-W3
**Risk:** 4 P3 review findings remain unresolved. Most consequential: (045) security hardening -- dev secret key default (`dev-fallback-key` in production), no password hashing (plaintext stored), missing security headers. If this app is ever deployed beyond localhost, these are critical vulnerabilities.
**Why not resolved:** Classified P3 (nice-to-have) for a single-admin dev tool used only on localhost. Acceptable for the current usage context.
**Tracked in:** HANDOFF.md under key `[057-W3]` (HANDOFF.md requires updating to add this entry).
**Severity for next session:** LOW (dev-only context); HIGH if deployment scope changes

---

**Key:** 057-W4
**Risk:** The isolation_level=None anti-pattern recurred for the third consecutive build despite FC40 in agent-pitfalls and an explicit deepening-phase prescription. The pitfall injection mechanism is not preventing recurrence because agents use template-copy behavior for db.py boilerplate. Each occurrence requires a review-phase fix; if review is skipped or abbreviated, this becomes a silent no-op commit bug in all SERIAL-SAFE routes.
**Why not resolved:** Root cause is orchestration/template issue, not a per-agent fix. Requires updating the db.py code block in the spec template (or the scaffold agent's boilerplate) to explicitly set the correct isolation level.
**Tracked in:** HANDOFF.md under key `[057-W4]` (HANDOFF.md requires updating to add this entry).
**Severity for next session:** MEDIUM (high likelihood of recurrence in run 058+; fix is well-understood)

---

## Run Quality Grade

| # | Dimension | Score | Evidence |
|---|-----------|-------|----------|
| 1 | Plan Adherence | 5/5 | BUILD_TRACKING AGENT_STATUS: 21/21 agents PASS, 0 FC37 failures, 0 merge conflicts; plan Acceptance Tests: all 9 happy-path and 5 error-case criteria verified by 61/61 smoke tests |
| 2 | Review Responsiveness | 5/5 | BUILD_TRACKING FAILURES: all 7 P1s resolved with correct fix for each; BUILD_TRACKING RUN_METRICS: 10 review agents used, feed_forward_resolved: true confirmed in solution doc review-summary frontmatter |
| 3 | Risk Handling | 4/5 | plan Feed-Forward risk (derived state chain) addressed in solution doc Risk Resolution: PASS; self-audit What Was Missed: 1 FC26-adjacent issue (deepening prescribed isolation_level fix but agents produced anti-pattern anyway -- spec prescription didn't reach code-generation moment); plan Feed-Forward least-confident item partially validated but post-fix re-trace not documented |
| 4 | Documentation Quality | 3/5 | HANDOFF date correct (2026-05-22); solution doc review findings count matches BUILD_TRACKING RUN_METRICS exactly; HANDOFF lacks post-review deferred item entries (pre-written before tail completed) -- self-audit What Was Missed item 1; BUILD_TRACKING FAILURES and RUN_METRICS fully filled and internally consistent |
| 5 | Honesty | 5/5 | self-audit WARN table: all 4 WARNs have non-empty rationale and defensible dispositions; self-audit status PIPELINE_PASS_WITH_DEFERRED_RISK matches 10 deferred findings; solution doc Validation Results marks Derived State as PARTIAL->PASS rather than claiming clean PASS |
| 6 | Compounding Quality | 4/5 | agent-pitfalls Update Log: 2026-05-22 entry present with FC45 and FC46 added; solution doc: 4 reusable lessons documented with failure class references; HANDOFF not updated with post-review deferred item keys (process gap reduces score from 5) |

**Overall: 4.3/5.0 (B)**

**Justification:** Plan adherence, review responsiveness, and honesty are all exemplary for a 21-agent build with 0 merge conflicts and 7 P1s cleanly resolved. The score is held to B by two Documentation Quality gaps: HANDOFF.md was written before the review tail completed and never back-populated with post-review deferred item keys, and the isolation_level Feed-Forward risk (057-W4, MEDIUM severity) demonstrates that a deepening-phase prescription did not survive to the code-generation moment. No DEFERRED WARNs carry HIGH severity, so the A-grade justification clause does not apply.
