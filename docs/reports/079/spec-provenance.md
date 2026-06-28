STATUS: PROVENANCE_REPAIRED -- spec-committed-to-base

# Spec-Provenance Gate (9w.9.5) — run 079

**Spec:** docs/plans/2026-06-26-g1-g3-live-validation-run-brief.md
**Default branch (worktree base):** master / origin/master
**Original (orchestrator feature) branch:** feat/g1-g3-live-validation

## Why a repair was needed
The 9w.5 consistency gate found 2 cross-section contradictions in the brief.
The fix was committed on the feature branch (`b75a049`, spec-only). That made
the feature-branch spec diverge from origin/master (which workers root on under
baseRef=fresh) → the gated spec ≠ the spec workers would read = FC52 drift.

## Detect (pre-repair)
- BASEREF-FRESH pre-check: `git rev-parse master origin/master` EQUAL (8d581d5) ✓
- Detector verdict: `STATUS: PROVENANCE_DRIFT`
  - pre-repair default(origin/master) blob = `964295825d9408b04f0b27364f69440e6e7e8462`
  - pre-repair original(feat) blob       = `bcfcd5d78b068f13db5693da821e502012e32d36`

## Repair (PRIMARY — deterministic, self-verifying)
Cherry-picked the isolated spec-only commit `b75a049` onto master
(→ `39cbe4f`) and pushed to origin/master (`8d581d5..39cbe4f`). The converged
spec now lives at the worktree base. (Injection FALLBACK was NOT used — the
cherry-pick applied cleanly.)

## Re-verify (the proof)
Re-ran `tools/check_spec_provenance.py`:
- `STATUS: PROVENANCE_OK`
- post-repair default(origin/master) blob = `bcfcd5d78b068f13db5693da821e502012e32d36`
- post-repair original(feat) blob         = `bcfcd5d78b068f13db5693da821e502012e32d36`
- blobs identical → every worker worktree reads the EXACT gated spec.

## Cleanup disposition
The spec-only repair commit on master (`39cbe4f`) is the **intentional repaired
base, carried forward** — the brief contradiction fix is a legitimate permanent
correction to a master-resident doc, not a throwaway side effect. It is NOT
reverted. (If the run had aborted before spawn, this would still be a valid
standalone doc fix.)

STATUS: PROVENANCE_REPAIRED -- spec-committed-to-base
