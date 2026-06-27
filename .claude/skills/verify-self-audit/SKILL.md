---
name: verify-self-audit
description: Verification gate for self-audit reports. 8 hard gates covering report existence, WARN key format, disposition validity, deferred-item tracking, source reconciliation, honest status claims, section completeness, run quality grading, and disconfirmer-finding enforcement. Called by the autopilot skill after the self-audit-reviewer agent runs.
argument-hint: "<run-id> <reports-dir>"
allowed-tools: Read Grep Glob
---

# Verify Self-Audit

This skill runs 8 hard gates on a self-audit report. It is called by
the autopilot skill as a single step to keep the autopilot under its
complexity budget.

## Inputs

You receive two arguments:
1. **run-id** -- the 3-digit run identifier (e.g., `043`)
2. **reports-dir** -- path to `docs/reports/<run-id>/`

Derive these paths:
- Self-audit report: `<reports-dir>/self-audit.md`
- Disconfirmer report: `<reports-dir>/disconfirmer.md`
- HANDOFF: `HANDOFF.md` (project root)

## Gates

Run all 8 checks in order. If ANY check fails, output the FAIL message
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

### Gate 8: Disconfirmer Findings Enforced

The disconfirmer (an Opus agent) runs BEFORE the self-audit and writes
`<reports-dir>/disconfirmer.md`. The skeptic is **mandatory**: this gate is
**fail-CLOSED** and **literal-token deterministic** (mirroring Gate 7f). A
missing, mismatched, or malformed disconfirmer report is a FAIL -- never a silent
pass, and never read as "zero findings."

**8a. Exists, identity, parseable (fail-closed):**

Glob `<reports-dir>/disconfirmer.md`. It MUST exist.

Read it and verify ALL of:
1. Its header contains the literal line `**Run ID:** <run-id>` where `<run-id>`
   matches the run-id argument exactly.
2. It is in EXACTLY ONE of two well-formed states. First define a **finding row**
   precisely (this is the only thing that counts as a finding — prose does not):

   > A *finding row* is a markdown table row whose FIRST cell, after trimming the
   > surrounding spaces, is exactly `D<N>` — the literal letter `D` followed by a
   > positive integer with **no leading zero** (`D1`, `D2`, `D10`; NEVER `D0`,
   > `D01`, `D 1`, `D1.1`, or a bare `D3` mentioned in prose). The grep-safe anchor
   > for a finding row is the regex `^\|\s*D[1-9][0-9]*\s*\|`.

   The two accepted states are:
   - **FINDINGS state:** one or more finding rows match the anchor above, AND the
     canonical sentinel line is ABSENT.
   - **CONCUR state:** the canonical sentinel line `No disconfirmer findings.` is
     present verbatim on its own line, AND there are ZERO finding rows.

Any other shape FAILs fail-closed. This explicitly includes: a header-only or
truncated write (no finding rows AND no sentinel); prose that mentions a `D<n>` but
has no matching anchored table row; a malformed table (a `D`-prefixed first cell that
is not `D[1-9][0-9]*`, e.g. `D01` / `D 1` / `D1.1`); and BOTH the sentinel line and
one or more finding rows present at once (ambiguous → malformed). A malformed write
is NEVER read as "zero findings."

If the file is missing, the Run ID line is absent/mismatched, or it is not in exactly
one of the two well-formed states, FAIL with:
```
SELF-AUDIT INCOMPLETE: disconfirmer.md missing, run-id mismatched, or unparseable (must be EITHER >=1 anchored `| D<N> |` finding row [D<N> = no leading zero] with NO sentinel, OR the verbatim `No disconfirmer findings.` sentinel with ZERO finding rows). The disconfirmer is mandatory and fail-closed.
```

If the CONCUR state holds (sentinel present, zero finding rows), Gate 8 passes (a
clean CONCUR); skip 8c.

**8c. Per-finding bijection + dismissal token (EXACT one-to-one):**

The mapping between disconfirmer findings and self-audit WARN rows must be a strict
**bijection**: each `D<n>` finding maps to exactly one WARN row, and each
disconfirmer-sourced WARN row carries exactly one finding. `contains` matching is
NOT sufficient (it lets a merged row satisfy several findings and lets `#D1` match
inside `#D10`). Enforce all four checks:

**1. Grep-safe, whole-cell token.** A WARN row "cites `D<n>`" if and only if its
`Source` cell, after trimming surrounding spaces, **equals exactly** the single
token `disconfirmer.md#D<n>` — the entire cell is that token and nothing else.
(Whole-cell equality, not substring `contains`. This is what prevents `D1` from
matching inside `D10`: `disconfirmer.md#D1` ≠ `disconfirmer.md#D10` as whole cells.)

**2. No merged rows.** No WARN row's `Source` cell may contain more than one
`disconfirmer.md#D` occurrence. A single row that cites two findings is rejected —
each finding needs its own row. If any Source cell holds ≥2 `disconfirmer.md#D`
tokens, FAIL with:
```
SELF-AUDIT INCONSISTENCY: a self-audit WARN Source cell cites more than one disconfirmer finding. Each disconfirmer finding needs its OWN WARN row (one Source cell = exactly one `disconfirmer.md#D<n>`).
```

**3. Surjective + injective + count parity.** For EVERY `D<n>` finding row in
`disconfirmer.md`, there must be **exactly one** WARN row whose `Source` cell equals
`disconfirmer.md#D<n>` (per check 1):
- Zero matching rows (dropped finding) → FAIL with:
  ```
  SELF-AUDIT INCONSISTENCY: disconfirmer finding D<n> has no WARN row whose Source cell is exactly 'disconfirmer.md#D<n>'. Every disconfirmer finding must be ingested as its own WARN.
  ```
- Two or more matching rows (duplicated finding) → FAIL with:
  ```
  SELF-AUDIT INCONSISTENCY: disconfirmer finding D<n> matches more than one WARN row. Each finding must map to exactly one WARN.
  ```
- A `disconfirmer.md#D<k>` Source cell that references no existing `D<k>` finding row
  (phantom citation) → FAIL with:
  ```
  SELF-AUDIT INCONSISTENCY: a self-audit WARN Source cites 'disconfirmer.md#D<k>' but disconfirmer.md has no D<k> finding row. Source must reference an existing finding.
  ```
The count of disconfirmer-sourced WARN rows MUST equal the number of `D<n>` finding
rows; checks 2+3 together guarantee it.

**4. Dismissal token (grep-safe).** For each disconfirmer WARN disposed `ACCEPTED`
(the "dismiss" set — `ACCEPTED` = real-but-tolerated), its `Rationale` cell MUST
contain the literal token `#D<n>` **immediately followed by a non-digit boundary**
(end of cell, whitespace, or punctuation) so `#D1` is not satisfied by `#D10`.
Presence check only — this gate never judges justification *quality*; Gate 2 already
owns disposition-enum and non-empty-rationale validation. If missing, FAIL with:
```
SELF-AUDIT INCONSISTENCY: disconfirmer WARN for D<n> is ACCEPTED but its Rationale lacks the literal '#D<n>' token (with a non-digit boundary). An accepted (dismissed) disconfirmer finding must cite its D# in the rationale.
```

## Output

If all 8 gates pass, output:
```
SELF-AUDIT VERIFIED: All 8 gates passed for run <run-id>.
STATUS: PASS
```

If any gate fails, output the specific FAIL message and:
```
STATUS: FAIL
```
