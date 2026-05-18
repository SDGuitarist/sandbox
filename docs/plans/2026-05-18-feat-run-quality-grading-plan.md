---
title: "feat: Run Quality Grading in Self-Audit"
type: feat
status: active
date: 2026-05-18
deepened: 2026-05-18
codex_review: pending
origin: docs/brainstorms/2026-05-18-run-quality-grading-brainstorm.md
swarm: false
feed_forward:
  risk: "Whether self-audit agent can detect context waste from artifacts alone"
  verify_first: false
---

# feat: Run Quality Grading in Self-Audit

## Enhancement Summary

**Deepened on:** 2026-05-18
**Revised:** 2026-05-18 R1 (gate numbering, contract scope, evidence format, constraints)
**Revised:** 2026-05-18 R2 (verify-skill body refs, Gate 7c format enforcement, dishonest-A contract level, context-efficiency scoring)
**Research agents used:** agent-spec-patterns, grep-pattern-validation, existing-score-patterns

### Key Improvements
1. **Step numbering:** Step 5 (integer only). Current Step 5 becomes Step 6.
2. **Grep patterns:** Case-sensitive exact string match, consistent with all existing gates.
3. **Evidence format:** `<ARTIFACT> <detail>` entries separated by `; `. Gate 7c validates both keyword presence AND detail text.
4. **Gate count:** All "8" references in verify-self-audit, autopilot skill, and self-audit-reviewer updated to "9".
5. **Dishonest-A is contract-level:** Added to CLAUDE.md Escalation Rules (same class as "claims PIPELINE_PASS with deferred risks").
6. **Context-efficiency scoring operationalized:** Concrete deduction table for Risk Handling dimension.

### Gate Numbering (resolved)

The verify-self-audit file has 6 gate headings (Gate 1–Gate 6). The
description says "8 hard gates" because sub-checks within Gates 2 and 6
are counted individually. The new gate is **Gate 7** (the 7th heading).
After this change: description says "9 hard gates", body says "Run all 9
checks", output says "All 9 gates passed." The brainstorm's "Gate 9" was
description-count-based; the plan uses heading numbers.

## Overview

Add a mandatory `## Run Quality Grade` section to the self-audit report. The
self-audit agent scores execution quality across 6 evidence-based dimensions.
A new verify gate fails the run if the grade is missing, unscored, or
unsupported by artifact citations.

## Problem Statement

The self-audit currently checks artifact completeness (pass/fail gates) but
not execution quality. Run 043 passed all 8 verify gates with a B-grade
execution (15% context wasted on wrong feature, skipped a plan-required test,
sloppy compound phase). The user had to manually request a rubric analysis.
This should be automatic.

## Proposed Solution

Four files modified. No new files, no new agents, no code.

1. **self-audit-reviewer.md** — add Step 5 (Score Run Quality). Renumber
   current Step 5 → Step 6. (Brainstorm Gap 1: must be a numbered step.)
2. **verify-self-audit SKILL.md** — add Gate 7 (Run Quality Grade). Update
   ALL "8" references to "9" (frontmatter, body intro, gates preamble, output).
3. **CLAUDE.md** — update Required Artifacts item 5 AND Escalation Rules to
   reflect run-quality grading as a mandatory element and dishonest-A as a
   contract-level failure.
4. **autopilot SKILL.md** — update the one "8 hard gates" reference in the
   Shared Tail to "9 hard gates".

## Constraints (What Must Not Change)

- **Existing gate behavior.** Gates 1–6 are unchanged. No re-numbering, no
  modification of existing fail messages.
- **Self-audit report structure.** All existing sections remain mandatory and
  unchanged. Run Quality Grade is additive.
- **Pipeline status semantics.** PIPELINE_PASS / PIPELINE_PASS_WITH_DEFERRED_RISK /
  PIPELINE_FAIL definitions are unchanged. The grade does not influence status.
- **Agent tool access.** Self-audit agent keeps Read, Write, Grep, Glob.
- **BUILD_TRACKING template.** Not modified. The grade lives in the self-audit
  report only.
- **Autopilot skill flow.** Not modified beyond the description string. It
  already calls self-audit-reviewer then verify-self-audit.
- **Scoring scale boundaries.** Low grades (C, D) inform learning but do not
  fail the run. Only missing, unscored, or dishonest grades fail.

## Implementation Plan

### Phase 1: Modify self-audit-reviewer.md

**File:** `.claude/agents/self-audit-reviewer.md`

Insert Step 5 after Step 4 (Write the Report). Renumber current Step 5
(Validate Your Own Report) to Step 6. MUST be a separate numbered step (FC11).

**Add after the report template (line ~189), before current Step 5:**

```markdown
### Step 5: Score Run Quality

After writing all sections above, add a `## Run Quality Grade` section at
the end of the report (before Step 6 validation). This section is MANDATORY.

Score each of these 6 dimensions from 1-5. For each score, cite 1-2 specific
artifacts as evidence using the format below. Do not score from memory — grep
or read the artifact to verify.

| # | Dimension | What to Check | Evidence Source |
|---|-----------|---------------|----------------|
| 1 | Plan Adherence | Did all plan phases ship? Were required deliverables built? Deductions for skipped items. | Plan doc vs BUILD_TRACKING |
| 2 | Review Responsiveness | Were P1s fixed? P2s addressed or justified? Was agent selection appropriate? | BUILD_TRACKING FAILURES + RUN_METRICS |
| 3 | Risk Handling | Was Feed-Forward risk addressed? Were wrong-path recoveries fast? Check "What Was Missed" for FC26/FC27 proxy signals (see scoring guide below). | Plan Feed-Forward + solution doc Risk Resolution + "What Was Missed" section |
| 4 | Documentation Quality | Were HANDOFF/solution/BUILD_TRACKING accurate on first pass? Key formats correct? Counts correct? | Cross-compare artifacts for internal consistency |
| 5 | Honesty | Are WARN dispositions defensible? Does status claim match reality? No inflated claims? | WARN Disposition Table + Unresolved Risk section |
| 6 | Compounding Quality | Did solution doc capture reusable lessons? Were pitfalls updated? Learnings propagated? | Solution doc + agent-pitfalls Update Log + HANDOFF |

**Scoring scale:**
- 5 = Exemplary (zero issues, proactive beyond requirements)
- 4 = Strong (minor issues only, all requirements met)
- 3 = Adequate (some gaps but nothing critical missed)
- 2 = Below standard (significant gaps, required corrections)
- 1 = Poor (major failures, multiple requirements missed)

**Risk Handling scoring guide (dimension 3):**

This dimension detects context waste and wrong-path recovery from artifacts.
Apply these deductions:

| Signal | Where to Find It | Deduction |
|--------|------------------|-----------|
| "What Was Missed" lists items the orchestrator failed to surface | This report, "What Was Missed" section | -1 per substantive miss |
| FC26 pattern: comment/doc claims implementation that code doesn't have | Solution doc or review findings referencing FC26 | -1 per instance |
| FC27 pattern: new code skips patterns present in neighboring files | Review findings referencing FC27 | -1 per instance |
| Feed-Forward "least confident" item not addressed in solution doc | Plan Feed-Forward vs solution doc Risk Resolution | -1 |
| Feed-Forward risk addressed but conclusion contradicts evidence | Plan vs solution doc vs review findings | -2 |

Start at 5 and subtract. Floor is 1.

**Evidence format (machine-checkable — Gate 7 validates this):**

Each Evidence cell must contain one or more artifact references in this
exact format: `<ARTIFACT> <detail-text>`, separated by `; ` when multiple.

Rules:
- Each reference MUST start with a recognized artifact keyword: BUILD_TRACKING,
  HANDOFF, plan, solution doc, self-audit, or agent-pitfalls
- Each reference MUST have detail text after the keyword (not just the keyword alone)
- Multiple references are separated by `; ` (semicolon space)

Valid: `BUILD_TRACKING FAILURES: 1 P1 fixed; plan Required Tests: 4 of 4 built`
Invalid: `BUILD_TRACKING; plan` (keywords only, no detail)
Invalid: `the tests all passed` (no artifact keyword)

**Output format (exact shape — Gate 7 greps for these markers):**

## Run Quality Grade

| # | Dimension | Score | Evidence |
|---|-----------|-------|----------|
| 1 | Plan Adherence | X/5 | BUILD_TRACKING AGENT_STATUS: all phases shipped; plan Acceptance Tests: 6 of 7 verified |
| 2 | Review Responsiveness | X/5 | BUILD_TRACKING FAILURES: 1 P1 fixed; BUILD_TRACKING RUN_METRICS: 0 P2 deferred |
| 3 | Risk Handling | X/5 | plan Feed-Forward: risk addressed in solution doc Risk Resolution; self-audit What Was Missed: no FC26/FC27 signals |
| 4 | Documentation Quality | X/5 | HANDOFF date correct; solution doc commit count matches BUILD_TRACKING |
| 5 | Honesty | X/5 | self-audit WARN table: all dispositions justified; status matches deferred count |
| 6 | Compounding Quality | X/5 | agent-pitfalls Update Log: entry present; solution doc: reusable pattern documented |

**Overall: X.X/5.0 ([A/B/C/D])**

**Justification:** [2-3 sentences citing the strongest and weakest dimensions
with specific artifact references. If the overall grade is A and any DEFERRED
WARNs have severity HIGH, this line MUST contain the literal string `HIGH`
and EVERY such WARN's key (e.g., `043-W2`, `043-W5`). Gate 7f checks each
DEFERRED+HIGH WARN independently and fails on the first missing key.
Example: "Despite 043-W2 and 043-W5 carrying HIGH severity, the grade is
justified because..."]

**Letter grade thresholds:** 4.5+ = A, 3.5+ = B, 2.5+ = C, below 2.5 = D

**Integrity rule:** If the overall grade is A, Gate 7f iterates over every
DEFERRED WARN with HIGH severity. For each one, the Justification line MUST
contain both: (a) the literal string `HIGH` and (b) that WARN's specific key.
Gate 7f fails on the first WARN whose key is missing from the Justification.
A justification that addresses some risks but omits a key will fail.
```

**Renumber current Step 5 → Step 6 (Validate Your Own Report).** Add check #9:

```markdown
9. The Run Quality Grade section passes all of these (mirroring Gate 7):
   a. Section heading `## Run Quality Grade` exists
   b. Table has exactly 6 data rows, each with a score in N/5 format
      where N is 1-5
   c. Each Evidence cell contains one or more `; `-separated segments.
      Every segment starts with a recognized artifact keyword
      (BUILD_TRACKING, HANDOFF, plan, solution doc, self-audit, or
      agent-pitfalls) followed by non-whitespace detail text
   d. An `**Overall:` line exists with a numeric score and letter grade
      `(A)`, `(B)`, `(C)`, or `(D)`
   e. A `**Justification:**` line exists with non-empty content
   f. If the Overall line contains `(A)`, for EVERY DEFERRED WARN
      with severity HIGH, the Justification line contains both the
      literal string `HIGH` and that WARN's specific key. Check each
      DEFERRED+HIGH WARN independently.
```

### Phase 2: Modify verify-self-audit SKILL.md

**File:** `.claude/skills/verify-self-audit/SKILL.md`

**2a. Update frontmatter description** (line 3) — change "8 hard gates" to
"9 hard gates" and append "and run quality grading":
```
description: Verification gate for self-audit reports. 9 hard gates covering report existence, WARN key format, disposition validity, deferred-item tracking, source reconciliation, honest status claims, section completeness, and run quality grading. Called by the autopilot skill after the self-audit-reviewer agent runs.
```

**2b. Update body intro** (line 10) — change "8 hard gates" to "9 hard gates":
```
This skill runs 9 hard gates on a self-audit report.
```

**2c. Update gates preamble** (line 26) — change "Run all 8 checks" to
"Run all 9 checks":
```
Run all 9 checks in order. If ANY check fails, output the FAIL message
```

**2d. Add Gate 7 after Gate 6** (before the Output section, around line 163):

```markdown
### Gate 7: Run Quality Grade

Verify the self-audit report contains a complete, evidence-supported
run quality grade.

**7a. Section exists:** Grep for `## Run Quality Grade` in the self-audit
report.

If missing, FAIL with:
```
SELF-AUDIT INCOMPLETE: Run Quality Grade section is missing. The self-audit agent must score all 6 dimensions.
```

**7b. Table completeness:** The grade table must have exactly 6 data rows
(beyond header and separator). Each row must contain a score in the format
`N/5` where N is 1-5.

If fewer than 6 scored rows, FAIL with:
```
SELF-AUDIT INCOMPLETE: Run Quality Grade table has fewer than 6 scored dimensions. All 6 are required.
```

**7c. Evidence well-formed and artifact-backed:** For each of the 6 data rows,
extract the Evidence column (4th column). Validate:

1. Cell is non-empty
2. Cell contains at least one recognized artifact keyword: BUILD_TRACKING,
   HANDOFF, plan, solution doc, self-audit, or agent-pitfalls
3. Each artifact keyword is followed by at least one non-whitespace character
   of detail text (not just the keyword alone)
4. If cell contains `; ` (semicolon-space), each segment before/after the
   delimiter must independently satisfy rules 2 and 3

If any evidence cell fails validation, FAIL with:
```
SELF-AUDIT INCOMPLETE: Run Quality Grade dimension [N] has malformed evidence. Each reference must be '<ARTIFACT> <detail>' separated by '; '. Got: '[cell content]'.
```

**7d. Overall score exists:** Grep for a line starting with `**Overall:`
followed by a numeric score (e.g., `3.5/5.0`) and a letter grade in
parentheses `(A)`, `(B)`, `(C)`, or `(D)`.

If missing, FAIL with:
```
SELF-AUDIT INCOMPLETE: Run Quality Grade is missing the Overall score line.
```

**7e. Justification exists:** Grep for `**Justification:**` followed by
non-empty content on the same or next line.

If missing or empty, FAIL with:
```
SELF-AUDIT INCOMPLETE: Run Quality Grade justification is missing or empty.
```

**7f. Dishonest-A check:** If the Overall line contains `(A)`, collect every
row in the WARN Disposition Table with Disposition "DEFERRED" whose
corresponding Unresolved Risk entry's "Severity for next session" line
contains `HIGH`.

For EACH such DEFERRED+HIGH WARN (evaluated independently):
1. The Justification line MUST contain the literal string `HIGH`
2. The Justification line MUST contain that WARN's specific key (e.g., `043-W2`)

Fail on the FIRST WARN whose key is missing. If multiple DEFERRED+HIGH
WARNs exist, every key must appear in the Justification.

If either token is missing for any WARN, FAIL with:
```
SELF-AUDIT DISHONESTY: Overall grade is A but WARN [key] is DEFERRED with HIGH severity. Justification must contain both 'HIGH' and '[key]'. Missing: [which token(s)].
```
```

**2e. Update Output section** (around line 167) — change "8" to "9":
```markdown
If all 9 gates pass, output:
```
SELF-AUDIT VERIFIED: All 9 gates passed for run <run-id>.
STATUS: PASS
```
```

### Phase 3: Modify CLAUDE.md

**File:** `CLAUDE.md` (project root)

**3a. Update Required Artifacts item 5** (line ~40):

Current:
```
5. **Self-audit report** -- Written by the self-audit-reviewer agent to `docs/reports/<run-id>/self-audit.md`. Must include: final run status, WARN disposition table (every WARN disposed), "What Was Missed" analysis, skeptical reviewer Q&A, and promotion decisions. Every DEFERRED disposition must have a matching HANDOFF.md entry.
```

Updated:
```
5. **Self-audit report** -- Written by the self-audit-reviewer agent to `docs/reports/<run-id>/self-audit.md`. Must include: final run status, WARN disposition table (every WARN disposed), "What Was Missed" analysis, skeptical reviewer Q&A, promotion decisions, and Run Quality Grade (6 dimensions scored 1-5 with artifact-backed evidence). Every DEFERRED disposition must have a matching HANDOFF.md entry.
```

**3b. Update Escalation Rules** (line ~56) — add dishonest-A rule:

Current:
```
- If the self-audit report has undisposed WARNs or claims PIPELINE_PASS with deferred risks, fail the run.
```

Updated:
```
- If the self-audit report has undisposed WARNs or claims PIPELINE_PASS with deferred risks, fail the run.
- If the self-audit report claims an A quality grade while DEFERRED WARNs carry HIGH severity, the justification must contain `HIGH` and every such WARN's key. Gate 7f checks each DEFERRED+HIGH WARN independently and fails on the first missing key.
```

### Phase 4: Modify autopilot SKILL.md

**File:** `.claude/skills/autopilot/SKILL.md`

**Update the Shared Tail verify-self-audit description** (line ~489):

Current:
```
This helper skill runs 8 hard gates on the self-audit report: report exists,
```

Updated:
```
This helper skill runs 9 hard gates on the self-audit report: report exists,
```

### Phase 5: Complexity Check

After all edits, verify line counts:
- `wc -l .claude/agents/self-audit-reviewer.md` — expect ~295 lines (was 216, adding ~80)
- `wc -l .claude/skills/verify-self-audit/SKILL.md` — expect ~240 lines (was 177, adding ~65)

Both well under the 500-line extraction threshold.

### Phase 6: Codex Review (post-implementation, pre-first-live-build)

Per spec convergence loop (brainstorm Gap 3):

**Review scope:** The exact markdown format in Step 5 of the agent spec MUST
match the grep patterns in Gate 7 of the verify skill, and CLAUDE.md must
accurately reflect the enforcement level.

**Specific cross-section checks:**
- `## Run Quality Grade` heading: Step 5 outputs it, Gate 7a greps for it
- `N/5` score format: Step 5 uses `X/5`, Gate 7b validates `N/5` where N is 1-5
- Evidence format: Step 5 prescribes `<ARTIFACT> <detail>` with `; ` delimiter;
  Gate 7c validates keyword + detail + delimiter structure
- `**Overall:` line: Step 5 and Gate 7d use this exact marker
- `**Justification:**` marker: Step 5 and Gate 7e use this exact string
- `(A)` detection: Gate 7f checks for `(A)` in the Overall line
- Dishonest-A token rule (plurality): Step 5 says Justification MUST contain
  `HIGH` and EVERY DEFERRED+HIGH WARN key. Gate 7f iterates each such WARN
  independently and fails on the first missing key. Step 6 check 9f mirrors.
  CLAUDE.md says "must contain `HIGH` and every such WARN's key."

**Handoff prompt for Codex:**
```
Review these four files for cross-section consistency:
1. .claude/agents/self-audit-reviewer.md (Step 5 output format + Step 6 check #9)
2. .claude/skills/verify-self-audit/SKILL.md (Gate 7 sub-checks 7a-7f + all "9" refs)
3. CLAUDE.md (Required Artifacts item 5 + Escalation Rules)
4. .claude/skills/autopilot/SKILL.md (Shared Tail "9 hard gates" reference)

Check: Does Gate 7 correctly validate everything Step 5 produces? Does
Step 6 check #9 match Gate 7's expectations? Do CLAUDE.md's Required
Artifacts and Escalation Rules match the enforcement level in Gate 7f?
Is every "8 hard gates" reference updated to "9"? Flag any format string
that could drift between files.
```

## Acceptance Tests

### Happy Path
- WHEN a self-audit agent runs after this change THE SYSTEM SHALL produce a `## Run Quality Grade` section with 6 scored dimensions and artifact-backed evidence
- WHEN all 6 dimensions have scores and well-formed evidence THE SYSTEM SHALL pass Gate 7
- WHEN the overall grade is B with no HIGH deferred items THE SYSTEM SHALL pass the dishonest-A check trivially

### Error Cases
- WHEN the Run Quality Grade section is missing THE SYSTEM SHALL fail Gate 7a
- WHEN a dimension's evidence is a bare keyword without detail THE SYSTEM SHALL fail Gate 7c with "malformed evidence"
- WHEN a dimension's evidence contains text but no recognized artifact keyword THE SYSTEM SHALL fail Gate 7c
- WHEN evidence has `; ` delimiter but a segment after it lacks a keyword THE SYSTEM SHALL fail Gate 7c
- WHEN the overall grade is A and a DEFERRED WARN has HIGH severity and the justification contains `HIGH` but omits the WARN key THE SYSTEM SHALL fail Gate 7f with "Missing: [key]"
- WHEN the overall grade is A and a DEFERRED WARN has HIGH severity and the justification contains the WARN key but omits `HIGH` THE SYSTEM SHALL fail Gate 7f with "Missing: HIGH"
- WHEN the overall grade is A and a DEFERRED WARN has HIGH severity and the justification contains both `HIGH` and the WARN key THE SYSTEM SHALL pass Gate 7f
- WHEN the overall grade is A and two DEFERRED WARNs (043-W2, 043-W5) have HIGH severity and the justification contains `HIGH` and `043-W2` but omits `043-W5` THE SYSTEM SHALL fail Gate 7f with "Missing: 043-W5"
- WHEN the overall grade is A and two DEFERRED WARNs (043-W2, 043-W5) have HIGH severity and the justification contains `HIGH` and both `043-W2` and `043-W5` THE SYSTEM SHALL pass Gate 7f
- WHEN the overall score line is missing THE SYSTEM SHALL fail Gate 7d

### Verification Commands
- `grep "## Run Quality Grade" docs/reports/<run-id>/self-audit.md` — section exists
- `grep -c "/5" docs/reports/<run-id>/self-audit.md` — at least 6 score entries
- `grep "\\*\\*Overall:" docs/reports/<run-id>/self-audit.md` — overall score present
- `grep "\\*\\*Justification:" docs/reports/<run-id>/self-audit.md` — justification present
- `wc -l .claude/agents/self-audit-reviewer.md` — under 300 lines
- `wc -l .claude/skills/verify-self-audit/SKILL.md` — under 250 lines
- `grep -c "9 hard gates\|All 9 gates\|all 9 checks" .claude/skills/verify-self-audit/SKILL.md` — should be 4
- `grep "9 hard gates" .claude/skills/autopilot/SKILL.md` — updated reference

## Dependencies & Risks

- **No code changes.** All four files are markdown specs/contracts.
- **No migration.** Changes take effect on the next autopilot run.
- **Cross-section format drift** is the main risk (see Phase 6 Codex review).
- **Gate 7c complexity.** The evidence format validation (keyword + detail +
  delimiter) is the most complex sub-check. If the agent produces slightly
  different formatting, Gate 7c could false-reject. The example evidence
  strings in Step 5 mitigate this.
- **Complexity budget.** Both files stay well under 500-line threshold.

## Sources & References

### Origin
- **Brainstorm:** [docs/brainstorms/2026-05-18-run-quality-grading-brainstorm.md](../brainstorms/2026-05-18-run-quality-grading-brainstorm.md) — Key decisions: extend self-audit (not new agent), 6 dimensions, evidence-required, low grade informs but doesn't fail. Note: brainstorm uses "Gate 9" (description-count); plan uses "Gate 7" (heading number).

### Institutional Learnings
- FC11: mandatory actions must be numbered steps, not prose (from `docs/solutions/2026-05-06-autopilot-skips-non-step-instructions.md`)
- Cross-section format drift is the P0 class (from `docs/solutions/2026-04-30-spec-convergence-loop.md`)
- Extraction threshold is 500 lines (from `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md`)
- FC26/FC27 as proxy signals for context waste (from `docs/solutions/2026-05-13-screenplay-ingestion-layer-build.md`)

### Internal References
- `.claude/agents/self-audit-reviewer.md` — current 216 lines, 5 steps → 6 steps
- `.claude/skills/verify-self-audit/SKILL.md` — current 177 lines, 6 gate headings → 7
- `CLAUDE.md` — Required Artifacts item 5 + Escalation Rules
- `.claude/skills/autopilot/SKILL.md` — Shared Tail "hard gates" reference

## Feed-Forward

- **Hardest decision:** Whether dishonest-A is a contract-level failure or just
  a verification warning. Decided: contract-level. It's the same class as
  "claims PIPELINE_PASS with deferred risks" (already in Escalation Rules).
  Both are dishonest status claims. Added to CLAUDE.md Escalation Rules.
- **Rejected alternatives:** Separate grading agent (splits truth), orchestrator
  self-scoring (dishonest), pass/fail-only quality checks (loses nuance),
  dishonest-A as warning-only (inconsistent with existing escalation rules).
- **Least confident:** Whether Gate 7c's evidence format validation is the right
  strictness level. It checks keyword + detail + delimiter. The agent may
  produce valid evidence in a slightly different format (e.g., using `,`
  instead of `; `). The Step 5 template with example strings should prevent
  this, but the first live build will be the real test. If Gate 7c false-rejects,
  loosen the delimiter check first (accept both `; ` and `, `).
