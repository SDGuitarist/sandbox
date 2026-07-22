STATUS: PROVENANCE_REPAIRED -- spec-committed-to-base

## Channel: cherry-pick / fast-forward (PRIMARY, self-verifying)

Workers root on origin/master under baseRef=fresh (empirically confirmed — probe agentId
a9a6b379f9e7da48e reported worktree HEAD == origin/master d42e015). The converged spec lived only
on feat/082-swarmlimit-spec, ABSENT on origin/master → PROVENANCE_DRIFT at baseline.

**Pre-repair blob SHAs (detector, exit 3):**
- default (origin/master) = ABSENT
- original (feat/082-swarmlimit-spec) = 936b8551712bfed812bf8e8847fc060fa5d7648e

**Repair:** origin/master is a strict ancestor of feat and feat is 0 behind → `git push origin
feat/082-swarmlimit-spec:master` is a clean FAST-FORWARD (d42e015..8b66e50, no force). This puts the
exact converged spec on the worker base. Alex explicitly approved master pushes for this run's
wave mechanic.

**Re-verify (detector, exit 0) — PROVENANCE_OK:**
- default (origin/master) = 936b8551712bfed812bf8e8847fc060fa5d7648e
- original (feat/082-swarmlimit-spec) = 936b8551712bfed812bf8e8847fc060fa5d7648e  (IDENTICAL)

This re-run IS the proof that all Wave-0 worktrees will read the converged spec.

## Wave mechanic (carried forward)

origin/master will be fast-forwarded to feat after EACH wave's merge (feat only ever advances;
master follows feat), so Wave N+1 workers see Wave N's merged code (FC52). All pushes are
fast-forwards — no history rewrite, append-only.

## Cleanup disposition

The FF push is the INTENTIONAL repaired base carried into the run (not reverted on success). On a
teardown/abort decision about origin/master, see the tail; the throwaway swarmlimit/ code is inert
namespaced clutter (FC59).

## Benign warning

The detector prints `local master (0746eba) != origin/master (8b66e50)` — this is PRE-EXISTING local
master cruft unrelated to this run. The authoritative comparison (origin/master vs feat, the real
worker base) is PROVENANCE_OK. Local master is never consumed by workers (baseRef=fresh uses
origin/master). Left untouched to avoid an unrequested destructive local-branch reset.
