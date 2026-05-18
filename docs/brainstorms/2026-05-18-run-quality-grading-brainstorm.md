---
title: Run Quality Grading in Self-Audit
date: 2026-05-18
origin: Run 043 post-mortem (user had to manually request a rubric analysis)
---

# Run Quality Grading in Self-Audit

## What We're Building

A required `## Run Quality Grade` section in the self-audit report that scores
execution quality across 6 evidence-based dimensions. The self-audit agent
already reads all run artifacts — it just needs a scoring rubric added to its
spec. One report, one agent, one truth.

The verify-self-audit skill gets a new gate (Gate 9) that fails the run if the
grade section is missing or any score lacks cited evidence.

## Why This Approach

- **Same agent, same report.** The self-audit agent already reads BUILD_TRACKING,
  HANDOFF, solution doc, plan, and review findings. No new agent or file needed.
- **Evidence-based, not vibes.** Every dimension score must cite a concrete
  artifact (file, section, or line). Unsupported claims fail verification.
- **Grade does not override status.** A run can be PIPELINE_PASS_WITH_DEFERRED_RISK
  with a high quality grade (good execution, known deferred risks). These are
  orthogonal signals.
- **Low grade informs, doesn't fail.** The grade is for learning. Only a missing
  or unsupported grade section fails the run — not a low score itself.
- **The thing being judged should not grade itself.** The self-audit agent grades
  the orchestrator's execution. The orchestrator cannot self-score.

## Key Decisions

### 1. Location: Extend self-audit agent

Add a `## Run Quality Grade` section to the existing self-audit report spec.
Not a new agent, not a separate report, not orchestrator self-scoring.

### 2. Rubric: 6 dimensions, 1-5 scale

| # | Dimension | What It Measures |
|---|-----------|-----------------|
| 1 | Plan Adherence | Did all plan phases ship? Were required deliverables built? Deductions for skipped items. |
| 2 | Review Responsiveness | Were P1s fixed? P2s addressed or justified? Agent selection appropriate? |
| 3 | Risk Handling | Was Feed-Forward risk addressed? Context waste? Wrong-path recovery speed? |
| 4 | Documentation Quality | HANDOFF/solution/BUILD_TRACKING accurate on first pass? Key formats correct? Commit counts right? |
| 5 | Honesty | Are WARN dispositions defensible? Status claim matches reality? No inflated claims? |
| 6 | Compounding Quality | Did solution doc capture reusable lessons? Were pitfalls updated? Learnings propagated? |

### 3. Scoring rules

- Overall score = arithmetic mean of 6 dimension scores (no weighting)
- Each dimension requires 1-2 evidence bullets citing specific artifacts
- Letter grade derived from score: 4.5+ = A, 3.5+ = B, 2.5+ = C, below = D
- "Dishonest A" fails verification: if overall grade is A but any DEFERRED WARN
  has severity HIGH, the grade must address this or the verify gate fails

### 4. Evidence sources

The self-audit agent uses these (already available to it):
- Plan document (Feed-Forward, required deliverables, acceptance tests)
- BUILD_TRACKING.md (agent status, failures, metrics)
- HANDOFF.md (deferred items, date, key format)
- Solution doc (risk resolution, deferred items, key files)
- Self-audit WARN table (what it just found)
- Review findings summary (from BUILD_TRACKING)

### 5. Verify gate additions

**Gate 9: Run Quality Grade exists and is supported**

Checks:
1. `## Run Quality Grade` section exists in self-audit report
2. Table has exactly 6 rows with scores in `?/5` format
3. Every row has non-empty Evidence column
4. Overall score line exists with numeric value and letter grade
5. Justification line exists and is non-empty
6. If overall grade is A and any DEFERRED WARN has severity HIGH, justification
   must reference how the deferred risk is acceptable despite high grade

Fail message:
```
SELF-AUDIT INCOMPLETE: Run Quality Grade section missing, incomplete, or unsupported.
[specific sub-check that failed]
```

### 6. What fails the run vs. lowers the grade

| Condition | Effect |
|-----------|--------|
| Grade section missing | Run FAILS |
| Score without evidence citation | Run FAILS |
| Overall grade claims A but ignores HIGH deferred risk | Run FAILS |
| Low score (e.g., 2/5 on a dimension) | Grade recorded, no fail |
| Overall C or D grade | Grade recorded, no fail — informs learning |

## Scope

### In scope
- New section in self-audit-reviewer agent spec
- New Gate 9 in verify-self-audit skill
- Rubric definition with evidence requirements

### Out of scope
- Historical re-grading of prior runs
- Weighting dimensions differently per build type (solo vs swarm)
- Automatic remediation based on low grades
- Changing BUILD_TRACKING template

## Feed-Forward

- **Hardest decision:** Whether low grades should fail the run. Decided no — the
  grade is for learning, not gatekeeping. Only dishonest or missing grades fail.
- **Rejected alternatives:** Separate grading agent (splits truth), orchestrator
  self-scoring (grading yourself is dishonest), pass/fail-only quality checks
  (lose the nuance of "B-grade execution that still shipped correctly").
- **Least confident:** Whether the self-audit agent can reliably detect "context
  waste" for the Risk Handling dimension. It can see the final artifacts but not
  the conversation history. It may need to rely on proxy signals (wrong-path
  commits that were reverted, solution doc "What Was Missed" section, time gaps
  between commits).

## Refinement Findings

**Gaps found:** 4

### Gap 1: Prose-vs-step risk (from autonomy hardening solution doc)

Adding the rubric as a spec prose change (not a numbered step) risks the agent
skipping it — matching the exact FC11/orchestrator-follows-steps-not-prose
failure that drove the autonomy hardening build.

**Action:** The rubric must be added as an explicit numbered instruction step
inside the agent spec, not just as a section description. Gate 9 catches
missing output, but a skipped step costs a full agent re-execution.

Source: `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md`

### Gap 2: Verify-self-audit complexity budget

The verify-self-audit skill was extracted at 176 lines specifically because the
autopilot skill hit 516 lines (threshold: 500). Gate 9 with 6 sub-checks adds
~20-30 lines. The plan should confirm the file stays under threshold or
pre-plan a second extraction.

**Action:** Check current line count during plan phase. If Gate 9 pushes past
200 lines, acceptable. If past 250, consider whether to extract.

Source: `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md`

### Gap 3: Cross-section spec needs Codex review (from spec convergence loop)

The self-audit agent spec, verify-self-audit skill, and Gate 9 grep patterns
form three linked sections that must be consistent. The table format (`?/5`)
must exactly match what Gate 9 greps for. Cross-section contradictions are the
P0 class that AI tools miss.

**Action:** After implementation, one Codex review round on the combined agent
spec + gate spec before the first live build.

Source: `docs/solutions/2026-04-30-spec-convergence-loop.md`

### Gap 4: Context-waste proxy signals are already catalogued

The "Least Confident" item (detecting context waste from artifacts alone) can
use existing failure class artifacts as proxy signals:
- **FC26** (comment-not-code): leaves a comment claiming an implementation
  that doesn't exist — detectable via grep in solution doc "What Was Missed"
- **FC27** (neighbor-pattern-skip): leaves missing imports/middleware —
  detectable in review findings

Both leave artifact-level traces the self-audit agent can already read.

**Action:** The Risk Handling scoring spec should reference FC26/FC27 patterns
and the "What Was Missed" section as primary evidence sources for context
waste, rather than leaving proxy detection undefined.

Source: `docs/solutions/2026-05-13-screenplay-ingestion-layer-build.md`
