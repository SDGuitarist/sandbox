# Codex Handoff — Brainstorm Review (Autopilot Orchestration Hardening)

**Phase:** brainstorm → plan (review the brainstorm *before* two plans are written)
**Created:** 2026-06-06

---

## Copy-paste prompt for Codex

```
Read these files first for project context:
  - CLAUDE.md                  (repo operating contract: autonomy classes, forbidden
                                actions, mandatory spec-coverage sections, escalation rules)
  - docs/plans/HANDOFF-orchestration-hardening-planning.md   (planning handoff: locked
                                decisions, the one open decision, files likely in scope)
  - docs/brainstorms/2026-06-06-autopilot-orchestration-hardening-brainstorm.md   (THE
                                ARTIFACT UNDER REVIEW)

Context: this brainstorm came out of the Run 068 (Gig Outcome Tracker) 12-agent swarm
retrospective. It proposes 4 orchestration-layer hardening changes, packaged as two plans
(A = reliability fixes 1–2, B = gate/spec changes 3–4). No plans exist yet. Your job is to
review the BRAINSTORM for soundness so the two plans get built on solid ground — NOT to
review code or plans.

Review the brainstorm for:

1. Gaps — anything missing from the 4 items that will bite during planning or
   implementation. Especially: are there orchestration failure modes adjacent to these
   that should be in scope?

2. Wrong assumptions — does the brainstorm assume something untrue about how the autopilot
   pipeline works? Verify against CLAUDE.md (Required Artifacts, Escalation Rules, the 6
   mandatory spec-coverage sections).

3. The crux of item 1 (disk-verify delegated STATUS) — the "false-PASS hole." The proposed
   authority hierarchy is: on-disk artifact STATUS = source of truth; wire STATUS = hint;
   artifact missing/unreadable/stale = genuine FAIL. Is this airtight? Specifically:
     - How should "stale" be defined so it can't be gamed — run-id match? timestamp newer
       than run start? Both? What if the artifact exists from a *prior* run with a PASS?
     - Does "agent forgot to echo its contract (real run → PASS)" vs "work genuinely
       incomplete (real FAIL)" actually separate cleanly on disk, or is there a case where
       a forgotten contract AND incomplete work look identical?

4. The TAIL_SYNC_POINT footgun — Step 18w logic is duplicated between
   `.claude/skills/autopilot/SKILL.md` and `.claude/agents/tail-runner.md`. Item 1 must be
   mirrored in both. Is a "remember to edit both" note enough, or should the brainstorm
   call for de-duplicating the logic? Flag the drift risk.

5. The open verification decision (carried into Plan A): these fixes prevent failures that
   don't occur on a normal run (forgotten Output Contract; mid-spawn context death).
   Recommend: build small failure-injection harnesses (inject a missing/stale STATUS
   artifact; simulate a lost roster) vs. accept best-effort with a documented manual repro?
   This shapes Plan A's EARS acceptance tests, so a clear recommendation matters.

6. Item 3 re-promotion criteria (spec-eval → advisory). The bar is "recall + precision":
   over ≥N advisory runs, re-promote to blocking only if it flagged ≥1 real defect the
   structural gates missed AND kept FP rate ≤~10%. N and the exact FP number are left for
   Plan B. Is recall+precision the right shape? Is the "advisory window never closes / gate
   languishes forever" risk (Least Confident item) adequately mitigated by the running-tally
   artifact idea, or does it need a hard sunset/forcing function?

7. Item 4 (read-path / no-record 7th spec surface). Is BLOCKING correct here (the
   brainstorm argues yes because section-existence is deterministic, 100% precision, unlike
   the spec-eval judge)? Any reason a deterministic existence check could still false-FAIL
   a legitimate spec?

8. Packaging — is the two-plan split (A ships first) right, or do any item-1↔item-4 /
   item-2↔item-3 dependencies argue for resequencing? Is deferring per-agent spec slices
   the right call?

9. Feed-Forward — is the "Least confident" item (advisory window may never close) the
   actual biggest risk, or is something else (e.g. the item-1 false-PASS hole) a larger
   unaddressed risk that should be elevated?

Output: findings ordered by severity (P0/P1/P2), each tagged to the item number it
affects, plus an updated Claude Code planning prompt if the brainstorm needs changes
before the two plans are written. If the brainstorm is sound as-is, say so explicitly and
list the 2–3 things the plans must get right.
```

---

## Notes for the human routing this to Codex

- This is a **brainstorm** review, not a plan/code review — there are no plans yet. The
  goal is to harden the decisions before two plans get generated, consistent with the Spec
  Convergence Loop philosophy (fresh-context external eyes before downstream work).
- The two highest-value things to get a second opinion on: **item 1's false-PASS hole**
  (the only change that touches the run's terminal pass/fail gate) and the **open
  verification decision** (harness vs manual repro) — both directly shape Plan A.
- After Codex returns findings, fold them into the brainstorm (or note them as resolved),
  then proceed to the plan flow (plan → deepen → self-review → Codex handoff) per the
  planning HANDOFF's next-session prompt.
```
