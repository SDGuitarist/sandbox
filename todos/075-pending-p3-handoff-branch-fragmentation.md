---
status: pending
priority: p3
issue_id: "075"
tags: [handoff, docs, branch-hygiene, p1p2, p3]
dependencies: []
unblocks: []
sub_priority: 1
---

# HANDOFF.md is fragmented across feature branches (p1p2 vs p3)

## Problem Statement

The authoritative, current project HANDOFF.md lives on `feat/p1p2-unattended-swarm-wave-barrier`
(the P1/P2 wave-barrier work, tip `9f91e0c`). The `feat/p3-harvest-and-darkness-tools` branch
(tip `840772f`) still carries the OLDER FC68-era HANDOFF.md — because P3 branched off
`4da3eff` before the p1p2 HANDOFF updates and was never rebased onto them.

This is **branch state, not a regression** — each branch is internally consistent and both are
pushed/green. But whichever branch merges to `master` first will bring its own HANDOFF version,
and the second merge will conflict on HANDOFF.md (or silently overwrite the other's state).
Left unreconciled, `master` could end up with a stale or partial project handoff.

## Findings

- `feat/p1p2-...` HANDOFF header: "§1 verifier CODE-review **GO**" (current authoritative state).
- `feat/p3-...` HANDOFF header: "FC68 / 083-W6 RESOLVED … merge-to-master decision pending"
  (the pre-p1p2 snapshot).
- Neither branch is merged to master yet; both merges are deferred to a human per CLAUDE.md
  §3.5 (unattended default-branch push policy).
- Surfaced 2026-07-23 while preparing the P3 Codex review handoff.

## Proposed Solutions

At master-merge time, produce a SINGLE authoritative HANDOFF.md on `master` rather than letting
either branch's copy win by merge order:

1. Merge the two feature branches to `master` in whatever order is decided (each is an
   independent, reviewed unit).
2. On the SECOND merge, resolve the HANDOFF.md conflict deliberately: regenerate HANDOFF.md
   from the fully-merged `master` state so it reflects BOTH P1/P2 (verifier GO, 40/40) AND P3
   (harvest gate + darkness fix), plus their Deferred Items and next-session prompt.
3. Verify no P1/P2 or P3 state (Codex verdicts, suite counts, deferred items) was dropped.

Do NOT rebase p3 onto p1p2 now just to sync HANDOFF — that rewrites a pushed branch for a
cosmetic doc and buys nothing while both branches are still awaiting review/merge.

## Recommended Timing

**Do this AT the master-merge of the LAST of {p1p2, p3} — not before.** Rationale:
- Both branches are still evolving independently (p1p2 GO'd; p3 awaiting Codex review). Any
  earlier reconciliation would be re-touched by the next change and wasted.
- The merge is the natural, unavoidable point where HANDOFF.md conflicts surface anyway, so
  reconciling there is zero extra branch churn.
- It is NOT on the P4 critical path and need not block anything before the merges. If P3 comes
  back NO-GO, ignore this until P3 is fixed and re-approved.

## Acceptance Criteria

- [ ] After both feature branches are merged, `master`'s HANDOFF.md carries a single, current
      project state covering BOTH P1/P2 and P3 (no stale FC68-only header).
- [ ] Deferred Items on `master` include the union of both branches' open items (no drops).
- [ ] The next-session prompt on `master` reflects the post-merge state (P4 gating status).
