# Proposal: Orchestrator Decision-Log Artifact (M35)

**Status:** PROPOSED (run-070 meta-analysis, Bucket 4, 2026-06-08). Parked — a new
SKILL artifact is a structural change to a live skill; mint it only when validated
(corpus mine or one deliberate trial), per the Bucket-2/3 calibration discipline.

## Problem

The autopilot SKILL specifies ~70% of what the orchestrator does. The other ~30% is
**orchestrator judgment** — unspecified by the checklist and, today, **unlogged**.
Run 070 alone had ~7 load-bearing deviations that changed the run's shape and left no
reasoning trail:

1. entry-point skip
2. run-id override
3. 9w.5 fix-and-retry vs abort
4. pre-flight `master` merge (to restore the O3 invariant)
5. keep-5 / delete-28 ghost-file nuance
6. split spawn
7. mid-swarm stale-spec proceed-vs-abort decision (the FC52 near-miss)

Each was a real fork where the orchestrator chose a path. The self-audit records
*outcomes*; nothing records the *reasoning*. When a run goes wrong (or nearly does, as
#7 did), the most important forensic data — *why* the orchestrator chose as it did — is
gone. "Autopilot" is a capable agent following a thick checklist and improvising the
rest; the improvisation is invisible.

## Proposal

A lightweight **decision-log** artifact at `docs/reports/<run-id>/decision-log.md`.
The orchestrator appends one entry per load-bearing deviation — a point where it
departed from the literal SKILL step or made a non-obvious judgment call:

```markdown
### [Step] <where> — <one-line decision>
- **Chose:** <what>
- **Over:** <the alternative(s) rejected>
- **Because:** <reasoning — the load-bearing part>
- **Reversible?:** <yes/no + how>
```

Reasoning, not just outcomes. The bar is "would a reviewer be surprised, or want to
know why?" — not every step, only the forks.

## Why parked, not drained into the live SKILL now

- Making it a **mandatory** artifact means a new tail gate (like the other required
  artifacts) — a coordinated live change on n=1 evidence.
- The right validation is cheap: run it as an **opt-in** on the next one or two builds
  (orchestrator keeps the log voluntarily), see whether the entries earn their cost,
  then decide whether to make it mandatory.

## Connection to other patterns

- Directly serves **M6b** (the missing "validity-affecting" escalation tier): decision
  #7 was exactly a "proceed vs abort on an anomaly that compromises the meaning of the
  result" call — the decision-log is where that tier's reasoning would live.
- Feeds the **meta-analysis phase** (M-meta / M36): the meta-analysis currently has to
  *reconstruct* deviations from artifacts; a decision-log hands it the forks directly.
- Relates to `[[workflow_lessons]]` memory.

Cross-refs: `docs/reports/070/meta-analysis.md` (M35, M6b),
`docs/governance/validation-validity-governance.md`,
`docs/latent-risks-and-mitigations.md`.
