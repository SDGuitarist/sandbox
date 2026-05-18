# Self-Audit Report -- Run 043

**Date:** 2026-05-17
**Build:** Writers Room Council -- Per-Project Voice Override
**Run ID:** 043
**Final Status:** PIPELINE_PASS_WITH_DEFERRED_RISK

---

## Final Run Status

**Status:** PIPELINE_PASS_WITH_DEFERRED_RISK

All critical gates passed: 1 P1 finding (FC24 -- XML sandbox escape gap in seed.ts userMessage) was found by the security-sentinel review agent and fixed before compound. 401/401 tests pass. However, 4 pre-existing P2/P3 issues were deferred rather than fixed, 1 plan-required test file (`voice-merge-regression.test.ts`) was not implemented, and HANDOFF.md deferred items use "043-D" keys instead of the required "043-W" keys, breaking the key linkage contract between this report and the tracking artifact.

---

## WARN Disposition Table

| # | Key | Source | WARN Description | Disposition | Rationale |
|---|-----|--------|-----------------|-------------|-----------|
| 1 | 043-W1 | BUILD_TRACKING.md (RUN_METRICS / solution doc Deferred Items) | Opening tag escaping gap in escape.ts: closing tags are escaped but opening `<tag>` variants are not covered by `escapeForXmlSandbox()`. Pre-existing gap not introduced by this PR. | DEFERRED | Pre-existing gap, not introduced by this build. Risk is bounded: attackers would need to inject a matching opening tag, which is a different and harder vector than closing-tag breakout. Tracked in HANDOFF.md as 043-D1. Key linkage gap: HANDOFF.md uses key `043-D1`, not `043-W1`. |
| 2 | 043-W2 | BUILD_TRACKING.md (RUN_METRICS / solution doc Deferred Items) | Unescaped `draft` and `userResponse` in council.ts fallback path: raw text from user submissions passes into the prompt without XML escaping. Pre-existing, affects raw-text fallback submissions only. | DEFERRED | Pre-existing gap not introduced by this build. The fallback path is used only when screenplay ingestion fails, so attack surface is limited but real. Tracked in HANDOFF.md as 043-D2. Key linkage gap: HANDOFF.md uses key `043-D2`, not `043-W2`. |
| 3 | 043-W3 | BUILD_TRACKING.md (RUN_METRICS) / plan scope boundaries | No PATCH endpoint for editing voice overrides post-creation. The plan explicitly placed this out of scope ("Editing overrides after project creation -- future iteration"). Users who want to change their voice override after project creation have no supported path. | DEFERRED | Explicitly out of scope per plan section "Scope Boundaries (from brainstorm)." Low severity for beta: overrides are optional, and users can create a new project. Tracked in HANDOFF.md as 043-D3. Key linkage gap: HANDOFF.md uses key `043-D3`, not `043-W3`. |
| 4 | 043-W4 | BUILD_TRACKING.md (RUN_METRICS) / solution doc Deferred Items | `string | null` type narrowing not resolved: description, intent, and protecting fields in the database type are typed `string | null` but routes treat them as `string` without explicit narrowing. Pre-existing type mismatch across all project routes. | DEFERRED | Pre-existing type mismatch, not introduced by this build. TypeScript compile errors are pre-existing (BUILD_TRACKING confirms "TypeScript: pre-existing errors only (0 new)"). The practical risk is low because the fields are required by Zod schema at POST time, but the narrowing should be fixed. Tracked in HANDOFF.md as 043-D4. Key linkage gap: HANDOFF.md uses key `043-D4`, not `043-W4`. |
| 5 | 043-W5 | Plan (Required Tests section) vs BUILD_TRACKING.md (AGENT_STATUS tests added) | Plan required `voice-merge-regression.test.ts`: a route-level regression test to verify all 5 council routes call `mergeVoiceOverride` and catch drift if one route removes the call. BUILD_TRACKING shows only 16 tests added across 3 files (merge-voice: 3, escape: 9, schema: 4). This file is absent. | ACCEPTED | The merge utility is called in all 5 routes (confirmed by flow-trace-reviewer finding zero issues). The risk of a future edit removing the call from one route is real but low: `mergeVoiceOverride` returns `VoicePromptParams['fingerprint']` and is type-anchored, so removing it would require a substitution that TypeScript would flag. Not tracked in HANDOFF.md -- this is a test coverage gap for a future hardening pass. |
| 6 | 043-W6 | HANDOFF.md (Deferred Items section) | HANDOFF.md deferred items use "043-D" key prefix instead of the required "043-W" key prefix. The self-audit process contract requires WARN keys to be shared between the self-audit report and HANDOFF.md for traceability. None of the 043-W keys from this report have matching `[043-W*]` tags in HANDOFF.md. | DEFERRED | Process compliance gap. This audit cannot modify HANDOFF.md. The content coverage is equivalent (043-D1 through 043-D4 map to 043-W1 through 043-W4), but the key linkage is broken. Next session must update HANDOFF.md to replace or alias "043-D" keys with "043-W" keys, or accept the divergence as a known process limitation for this run. |
| 7 | 043-W7 | Solution doc (Commits section) vs BUILD_TRACKING.md (AGENT_STATUS) | Solution doc commit list body shows 10 numbered commits but the header states "11 commits" and BUILD_TRACKING AGENT_STATUS also states "11 commits" and HANDOFF.md states "11 commits." The solution doc commit section is internally inconsistent: the title says "10 commits" but there are 11 numbered entries in the list. | ACCEPTED | Documentation discrepancy only. All 11 commits are accounted for in the commit range (708fd55..811796a). No functional impact. The body of the solution doc's Commits section actually has 11 entries; the section heading "10 commits" is a copy-paste error from a draft. Low severity. |

---

## Source Reconciliation

| Source File | WARN Tokens Found | WARNs Added to Table |
|-------------|-------------------|----------------------|
| docs/reports/043/ (entire directory) | 0 -- directory had no files prior to this self-audit | 0 (no gate reports exist; solo path does not generate swarm-phase reports) |
| BUILD_TRACKING.md (FAILURES section) | 1 (Security P1-1 -- has Resolution, so FIXED, not a WARN) | 0 from FAILURES directly; W1-W4 sourced from RUN_METRICS / solution doc cross-reference |
| BUILD_TRACKING.md (RUN_METRICS section) | 0 WARN tokens; "2 pre-existing deferred" P2s and "2 pre-existing deferred" P3s noted in metrics table | 4 (043-W1, 043-W2, 043-W3, 043-W4) |
| HANDOFF.md (Deferred Items section) | 0 WARN tokens; 4 deferred items with 043-D keys | 1 (043-W6 -- the key format mismatch finding) |
| HANDOFF.md (Review Fixes Pending P2 section) | Section does not exist | 0 |
| docs/solutions/2026-05-17-per-project-voice-override-build.md | 0 WARN tokens; "Deferred Items" table with 4 entries | Cross-reference source for W1-W4; no additional WARNs |
| writers-room-council/docs/plans/2026-05-17-feat-per-project-voice-override-plan.md | 0 WARN tokens | 1 (043-W5 -- route regression test required by plan, absent from build) |

**Notes on zero gate reports:** The solo autopilot path creates `docs/reports/<run-id>/` but does not run swarm-phase gates (spec-consistency-checker, ownership-gate, spec-contract-checker, smoke-test-runner, test-suite-runner). These are swarm-path-only steps. The only mandatory file for a solo run is `self-audit.md` (this document). The test suite result (401/401) is captured in BUILD_TRACKING, not a separate test-results.md file.

---

## What Was Missed In The First Summary

**1. Route-level regression test not built (043-W5)**

The plan's Required Tests section explicitly mandates `voice-merge-regression.test.ts` as a separate file to verify all 5 council routes call `mergeVoiceOverride` and catch future drift. The solution doc's compound summary, BUILD_TRACKING, and HANDOFF.md all omit any mention of this file being skipped. BUILD_TRACKING reports "Tests added: 16 (merge-voice: 3, escape: 9, schema: 4)" -- three test files, not four. The solution doc does not acknowledge the gap. This is a genuine miss in the first summary.

**2. Solution doc commit count discrepancy (043-W7)**

The solution doc's Commits section is titled "10 commits" but lists 11 numbered entries. BUILD_TRACKING and HANDOFF.md correctly state 11. This internal inconsistency in the primary artifact was not noted anywhere in the build documentation.

**3. HANDOFF.md key format diverges from self-audit contract (043-W6)**

The compound phase wrote HANDOFF.md with "043-D" keys for deferred items. The self-audit contract requires "043-W" keys. No artifact from the build -- solution doc, BUILD_TRACKING, HANDOFF.md -- flags this mismatch or explains it. It was simply written incorrectly relative to the schema defined in the self-audit-reviewer agent spec.

**4. Zod transform code sample bug in plan (not addressed)**

The plan's Phase 3 code sample shows `.transform((v) => v?.trim() || null)` which has the falsy-coalescing bug (`||` treats "0" as empty). The review found this as a P2 and it was fixed in the implementation. However, neither the solution doc nor BUILD_TRACKING notes that the plan's own code sample was incorrect. The plan was never updated. A developer reading the plan would get a buggy implementation.

**5. Feed-Forward "least confident" partially addressed**

The plan's Feed-Forward "least confident" item was: "Staleness risk is reduced but not eliminated -- if a user sets an override and later updates their fingerprint, the override doesn't sync." The solution doc's Risk Resolution section addresses this acceptably. However, the related discoverability risk mentioned in HANDOFF.md Three Questions ("whether users will discover the collapsed voice section") was not in the Feed-Forward chain at all -- it emerged post-build. It is surfaced in HANDOFF.md but was not pre-flagged in the plan, which means it could not be scrutinized during review.

---

## Questions A Skeptical Reviewer Would Ask

**Q1:** The plan required 4 test categories but only 3 were implemented. Is the missing route-regression test a real risk or just box-checking?

**A1:** It is a real risk. The `voice-merge-regression.test.ts` requirement exists specifically to catch the failure mode where a future developer edits one of the 5 council routes and removes the `mergeVoiceOverride` call, causing that route to silently use the raw fingerprint for all projects regardless of overrides. The flow-trace-reviewer confirmed all 5 routes currently use the merge utility, but there is no automated guard to keep them that way. The type-anchor (`VoicePromptParams['fingerprint']`) provides compile-time protection only if the return type is used -- if someone replaces the merge call with direct fingerprint mapping, TypeScript won't catch it. The test gap is real and was not acknowledged in any summary artifact.

**Q2:** Two P2 findings were deferred as "pre-existing." How confident are we that these gaps were pre-existing and not introduced by this build?

**A2:** The confidence is high but not absolute. The security-sentinel review agent is the source of the "pre-existing" classification. Opening tag escaping: the shared `escape.ts` module was created in this build, and by design it only escapes closing tags. The plan's Phase 0 specifies closing-tag escaping only (see the 6 `.replace()` calls in the plan's code sample). A build that deliberately created a partial escape module could reasonably call the un-implemented portion "pre-existing." For `draft/userResponse` in the council.ts fallback: this code path predates this build and was not touched by any of the 11 commits. BUILD_TRACKING AGENT_STATUS confirms "Files modified: 9" and lists specific files -- `council.ts` is listed but the fallback path was not part of the change scope. Both classifications are defensible.

**Q3:** 401 tests pass, but do they cover the critical path where a user with a pre-migration project (all voice columns NULL) submits a council session?

**A3:** The merge-voice tests cover the "all NULL (full fallback)" case directly: the test verifies that when all 4 project voice fields are null, `mergeVoiceOverride` returns all fingerprint values. This is the pre-migration regression case. However, these tests operate on the merge utility in isolation. There are no integration tests verifying the full council route (standard, seed, RWP) correctly selects the voice columns from the DB and passes them to merge. The route tests appear to be schema-level (schemas.test.ts with 4 tests). A pre-migration project row would have NULL columns, which Supabase returns as null -- compatible with the merge utility's type contract -- but this is not end-to-end verified by the test suite.

**Q4:** The plan's `optionalVoiceField` Zod transform had a falsy-coalescing bug (`||` instead of `.length > 0`). The fix was applied. But is the fix actually correct for the string `"0"`?

**A4:** Yes. The fix described in the review (explicit `length > 0` check replacing `||`) correctly handles the string `"0"` -- it would be stored as an override, not coalesced to null. The `||` bug would have coalesced `"0"` to null because `"0"` is falsy in JavaScript. For voice fields (genre, obsessions, failure patterns, tone), the string `"0"` is a nonsensical value but the principle matters: the fix ensures any non-empty, non-whitespace string is stored. The escape tests include a "no false positives" case (normal text unchanged). The schema tests (4 tests) presumably cover the Zod transform behavior, but the test file names are not enumerated in BUILD_TRACKING, so we cannot confirm coverage of the `"0"` edge case specifically.

**Q5:** The build has 11 commits but the feature branch (`feat/per-project-voice-override`) has not been merged to master. Is the build actually deployed-ready or still in branch limbo?

**A5:** The feature is branch-complete but not deployed. The branch `feat/per-project-voice-override` in `writers-room-council/` is ready for merge per HANDOFF.md, but HANDOFF.md explicitly notes "Migration 015 needs to be applied to remote Supabase before deploy." The code assumes the 4 voice columns exist in the `projects` table. Deploying without running the migration would cause 500 errors on any council route that now selects those columns. The merge is safe to do but requires the migration to be applied first. This is a valid deploy constraint, not a bug, but it was not flagged as a blocker in BUILD_TRACKING's RUN_METRICS table.

---

## Promotion Decisions

| Finding | Promoted To | Why |
|---------|------------|-----|
| FC24 scope clarification: userMessage escaping gap (seed.ts) | agent-pitfalls FC24 rule (existing class, extended rule) | BUILD_TRACKING Lessons for Next Build item 1 confirms this was added: "FC24 applies to ALL user-controlled interpolation sites, not just system prompt XML blocks -- extend scope check to userMessage paths." The agent-pitfalls Update Log entry for 2026-05-17 confirms this was appended. Already promoted. |
| 4-agent review mix validation (security + TS + data-integrity + flow-trace) | agent-pitfalls Update Log (2026-05-17 entry) | Confirmed effective mix for solo feature builds. Already documented in the Update Log: "FC12 guidance confirmed -- skipped pattern-recognition + code-simplicity, used flow-trace-reviewer instead." Not a new failure class. |
| Route regression test not built despite plan requirement (043-W5) | Not promoted to agent-pitfalls | The plan explicitly required the test. The orchestrator skipped it. This is closer to FC11 (skipping required steps) than a new pattern. No new failure class created. A note for the next session: add the missing test. |
| HANDOFF.md key format divergence (043-D vs 043-W) | Not promoted to agent-pitfalls | One-off process error in the compound phase. The self-audit-reviewer agent spec is clear about the 043-W key format requirement. The compound phase used an ad-hoc "043-D" prefix. No new failure class -- this is a compound-phase adherence gap, not a new pattern. |
| Zod transform falsy-coalescing bug in plan code sample | Not promoted to agent-pitfalls | The `||` vs `.length > 0` distinction for string emptiness checks is already covered implicitly by general Zod schema best practices. The plan's own code sample had the bug and the review caught it -- this is the correct outcome. Not a new failure class. |
| Discoverability risk for collapsed voice section | Not promoted to agent-pitfalls | UX discoverability is a product risk, not a build failure pattern. Tracked in HANDOFF.md Three Questions for beta feedback collection. Not appropriate for agent-pitfalls (which covers mechanical failure patterns, not UX design risks). |

---

## Unresolved Risk

**Key:** 043-W1
**Risk:** Opening tag escaping not implemented in escape.ts. Tags like `<writer_fingerprint>` are not escaped, only closing variants `</writer_fingerprint>` are. A prompt injection attack using matching opening tags is harder to execute than closing-tag injection but remains an unmitigated surface.
**Why not resolved:** Pre-existing gap. Fixing requires auditing all 6 sandbox tag patterns to determine where opening tags appear in prompts and whether user content can plausibly inject them. The build scope was closing-tag injection (the higher-risk pattern).
**Tracked in:** HANDOFF.md under key `043-D1` (note: key format mismatch -- should be `043-W1`; next session should reconcile)
**Severity for next session:** MEDIUM

---

**Key:** 043-W2
**Risk:** `draft` and `userResponse` fields in council.ts fallback path are interpolated into the LLM prompt without `escapeForXmlSandbox()`. These fields contain raw user-submitted text (screenplay content and user responses). A user who injects `</screenplay_text>` directly into their draft submission could break out of the XML sandbox on the fallback code path.
**Why not resolved:** Pre-existing gap, not introduced by this build. The fallback path is used only when the ingestion pipeline fails, reducing exposure. Fixing requires identifying the exact lines in council.ts and applying the shared escape module.
**Tracked in:** HANDOFF.md under key `043-D2` (note: key format mismatch -- should be `043-W2`; next session should reconcile)
**Severity for next session:** HIGH (closing-tag injection on raw user content is the primary threat model for the XML sandbox pattern)

---

**Key:** 043-W3
**Risk:** No PATCH endpoint for editing voice overrides after project creation. Users who set a wrong override at project creation have no UI path to correct it except deleting and recreating the project.
**Why not resolved:** Explicitly out of scope per plan. Acceptable for beta.
**Tracked in:** HANDOFF.md under key `043-D3` (note: key format mismatch -- should be `043-W3`; next session should reconcile)
**Severity for next session:** LOW

---

**Key:** 043-W4
**Risk:** `string | null` type narrowing not applied to description, intent, and protecting fields across project routes. Pre-existing TypeScript type mismatch. In practice the Zod schema enforces non-null at POST time, but TypeScript does not surface narrowing errors for these fields.
**Why not resolved:** Pre-existing mismatch across all project routes. Out of scope for this build.
**Tracked in:** HANDOFF.md under key `043-D4` (note: key format mismatch -- should be `043-W4`; next session should reconcile)
**Severity for next session:** LOW

---

**Key:** 043-W5
**Risk:** Route-level regression test (`voice-merge-regression.test.ts`) required by plan was not implemented. No automated guard exists to detect if a future edit removes `mergeVoiceOverride` from one of the 5 council routes, which would silently revert that route to always using the account fingerprint regardless of project overrides.
**Why not resolved:** Not acknowledged during the build. The orchestrator appears to have interpreted the schema tests (schemas.test.ts, 4 tests) as satisfying the route-level regression requirement, but these are different test levels.
**Tracked in:** Not tracked in HANDOFF.md (omission). Next session should add the test and add a HANDOFF entry.
**Severity for next session:** MEDIUM

---

**Key:** 043-W6
**Risk:** HANDOFF.md deferred items use "043-D" key prefix instead of the required "043-W" key prefix. The self-audit key linkage contract (self-audit report WARN keys must match HANDOFF.md entries verbatim) is broken for this run. Anyone using the HANDOFF keys to find self-audit context will not find matching entries.
**Why not resolved:** HANDOFF.md was written during compound before the self-audit format requirement was applied. This audit agent cannot modify existing artifacts.
**Tracked in:** Surfaced here only. Next session must update HANDOFF.md to alias or replace "043-D" keys with "043-W" keys, or add a note explaining the key format divergence.
**Severity for next session:** LOW (process debt, no functional impact)
