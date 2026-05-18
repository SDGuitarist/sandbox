---
name: verify-self-audit
description: Verification gate for self-audit reports. 9 hard gates covering report existence, WARN key format, disposition validity, deferred-item tracking, source reconciliation, honest status claims, section completeness, and run quality grading. Called by the autopilot skill after the self-audit-reviewer agent runs.
argument-hint: "<run-id> <reports-dir>"
allowed-tools: Read Grep Glob
---

# Verify Self-Audit

This skill runs 9 hard gates on a self-audit report. It is called by
the autopilot skill as a single step to keep the autopilot under its
complexity budget.

## Inputs

You receive two arguments:
1. **run-id** -- the 3-digit run identifier (e.g., `043`)
2. **reports-dir** -- path to `docs/reports/<run-id>/`

Derive these paths:
- Self-audit report: `<reports-dir>/self-audit.md`
- HANDOFF: `HANDOFF.md` (project root)

## Gates

Run all 9 checks in order. If ANY check fails, output the FAIL message
and stop. Do NOT continue to subsequent checks after a failure.

### Gate 1: Report Exists

Read `<reports-dir>/self-audit.md`.

If the file does not exist, FAIL with:
```
SELF-AUDIT MISSING: <reports-dir>/self-audit.md not found. Re-run the self-audit-reviewer agent.
```

### Gate 2: All WARNs Disposed with Valid Keys

Read the WARN Disposition Table in the self-audit report.

If the table says "No WARNs found across all gate reports," this gate passes
automatically.

For every row, validate all three fields:

**Key format:** Must be exactly `<run-id>-W<N>` where `<run-id>` matches the
run-id argument and `<N>` is a sequential integer starting at 1 with no
zero-padding (e.g., `043-W1`, `043-W2`, NOT `043-W01` or `043-w1` or
`43-W1`). Keys must be sequential with no gaps.

If a key is malformed, FAIL with:
```
SELF-AUDIT MALFORMED KEY: '[key]' does not match required format <run-id>-W<N>. Fix the key format.
```

**Disposition:** Must be exactly one of: `ACCEPTED`, `PROMOTED`, `DEFERRED`.
Any other value (blank, misspelled, lowercase) fails.

If a disposition is invalid, FAIL with:
```
SELF-AUDIT INVALID DISPOSITION: WARN [key] has disposition '[value]'. Must be exactly ACCEPTED, PROMOTED, or DEFERRED.
```

**Rationale:** Must be non-empty.

If a rationale is blank, FAIL with:
```
SELF-AUDIT INCOMPLETE: WARN [key] has no rationale.
```

### Gate 3: Deferred Items Tracked by Key

For every WARN row with Disposition "DEFERRED", extract the Key value
(e.g., `043-W2`).

Read `HANDOFF.md`. Grep for the exact Key string.

If the Key is not found anywhere in HANDOFF.md, FAIL with:
```
SELF-AUDIT INCONSISTENCY: WARN key '[key]' is DEFERRED but not found in HANDOFF.md. Add '[key] <description>' to HANDOFF.md or change the disposition.
```

### Gate 4: WARN Completeness (Source Reconciliation)

Read the Source Reconciliation table in the self-audit report.

Then list every file in `<reports-dir>/` using Glob (`<reports-dir>/*`).
Exclude `self-audit.md` itself from this check (it cannot reconcile itself).

For every OTHER file in the directory, verify it appears as a row in the
Source Reconciliation table.

Also verify that both `BUILD_TRACKING.md` and `HANDOFF.md` appear as rows.

If any report file is missing from the table, FAIL with:
```
SELF-AUDIT INCOMPLETE: Report file '[filename]' exists in <reports-dir>/ but is not listed in Source Reconciliation. The agent missed a source.
```

If BUILD_TRACKING.md is missing from the table, FAIL with:
```
SELF-AUDIT INCOMPLETE: BUILD_TRACKING.md is not listed in Source Reconciliation.
```

If HANDOFF.md is missing from the table, FAIL with:
```
SELF-AUDIT INCOMPLETE: HANDOFF.md is not listed in Source Reconciliation.
```

### Gate 5: Honest Status Claim

**If Final Status is `PIPELINE_PASS`:**
- The WARN Disposition Table must have zero rows with Disposition "DEFERRED"
- The "Unresolved Risk" section must be absent or empty

If either condition is violated, FAIL with:
```
SELF-AUDIT DISHONESTY: Final Status is PIPELINE_PASS but deferred items or unresolved risks exist. Change status to PIPELINE_PASS_WITH_DEFERRED_RISK.
```

**If Final Status is `PIPELINE_PASS_WITH_DEFERRED_RISK`:**
- The `## Unresolved Risk` section must exist and contain at least one risk
  entry (a line starting with `- **Key:**` or `- **Risk:**`)

If the section is missing or empty, FAIL with:
```
SELF-AUDIT INCOMPLETE: Final Status is PIPELINE_PASS_WITH_DEFERRED_RISK but the Unresolved Risk section is missing or empty. Add the deferred risks or change status to PIPELINE_PASS.
```

### Gate 6: Report Sections Complete

Verify the self-audit report contains substantive content in its mandatory
analysis sections. These checks ensure the agent did not rubber-stamp them.

**What Was Missed:** The `## What Was Missed In The First Summary` section
must exist. It must contain at least one line of content below the heading
(the line "First summary was complete -- no omissions found." counts as
content -- the point is that the section was not skipped entirely).

If the section is missing or empty, FAIL with:
```
SELF-AUDIT INCOMPLETE: "What Was Missed In The First Summary" section is missing or empty.
```

**Skeptical Questions:** The `## Questions A Skeptical Reviewer Would Ask`
section must contain at least 3 question-answer pairs. Check for the
presence of `**Q1:**`, `**Q2:**`, and `**Q3:**` (or equivalent `Q1:`,
`Q2:`, `Q3:` markers).

If fewer than 3 are found, FAIL with:
```
SELF-AUDIT INCOMPLETE: Fewer than 3 skeptical reviewer questions found. The report contract requires at least 3.
```

**Promotion Decisions:** The `## Promotion Decisions` section must contain
a markdown table with at least one data row (beyond the header and separator
rows). A row with "Not promoted" in the Promoted To column counts.

If the section is missing or has no data rows, FAIL with:
```
SELF-AUDIT INCOMPLETE: Promotion Decisions table has no rows. At least one finding must be evaluated.
```

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

## Output

If all 9 gates pass, output:
```
SELF-AUDIT VERIFIED: All 9 gates passed for run <run-id>.
STATUS: PASS
```

If any gate fails, output the specific FAIL message and:
```
STATUS: FAIL
```
