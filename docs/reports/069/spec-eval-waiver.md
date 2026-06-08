STATUS: WAIVED_BY_HUMAN
gate: spec-eval-gate (Step 9w.8)
gate_result: FAIL (111/155 HIGH-confidence claims passed; 44 failed)
waived_by: Alex Guillen (human operator)
waived_on: 2026-06-07
authorization: Explicit — operator selected "WAIVE" at the Stage-2 spec-eval
  decision gate after reviewing the full 44-failure artifact analysis and a
  manual Codex second opinion.
report: docs/reports/069/spec-eval-1780877897/spec-eval-gate.json

## Why this waiver is legitimate (not a gate bypass)

The gate genuinely returned FAIL, but every one of the 44 residual failures is
a single-shot-agent / harness artifact, NOT a spec defect. Breakdown of all 44:

- **18 — empty evidence:** the harness's single-shot test agent produced no
  scorable code at all for the claim.
- **15 — truncated / "not an actual implementation":** test-agent output cut
  off mid-file (1024-ish token truncation), or the agent emitted a
  meta-analyzer instead of an implementation.
- **11 — divergent one-shot implementations.** Read individually, none is a
  spec gap. Several are spec-COMPLIANT behavior the scorer misjudged:
  - `build_projection_at` using a `:memory:` throwaway connection — explicitly
    ALLOWED by §8.1 exception (b).
  - `reap_stale_runs` present in BOTH replay and ingest routes — matches §3.2 B′.
  - `generate_source.py` with `seed=42` + the 4 failure injections present —
    matches §4.3.
  The remainder are the test agent inventing structures the spec forbids:
  a `/live/users` GET/POST/PUT/DELETE CRUD route (spec: live.db is RO, no
  route), a `User.save()` / `User.get_by_id()` ORM layer (spec uses functional
  model modules), a `ValidationModels` singleton (spec: functional
  `record_determinism`), and cosmetic return-type annotation drift
  (`dict[str, object]` vs spec signature). All are the agent's free choices
  under no file-ownership constraint, not spec ambiguity.

The spec-eval harness tests a single-shot, UNCONSTRAINED generator on isolated
claims. Its failures have low predictive value for the real swarm: file-scoped
workers receive the full spec + exact Export Names + Cross-Boundary Wiring +
file ownership + agent-pitfalls injection. The harness also blew its own cost
cap ($2.859 vs $1.00 budget), a reliability signal of its own.

## The spec PASSED the binding structural gates

These are the gates that actually validate swarm-buildability:
- spec-consistency-check.md: PASS (47 checks: 45 PASS, 2 LOW WARN, 0 FAIL;
  full Export↔Wiring bidirectional coverage).
- spec-completeness-check.md: PASS (all 6 mandatory surfaces; login_required
  wiring + POST /auth/logout validation rows added and re-verified).

Plus the spec is FROZEN after: 11-agent deepening → 7-round Codex convergence →
human grill-me pass → 2-round manual Codex binding review (both GO, P1/P2 fixed)
→ human zero-P0 (docs/reports/069/binding-review-verdict.md).

## Two independent reviews agree to WAIVE

1. Build-session human analysis of all 44 failures (classified above).
2. Manual Codex second opinion, which sampled 11 failures directly from
   spec-eval-gate.json across all three classes (tbl-043/047/062, tbl-021,
   tbl-024/030/058, prose-015/025/046/085) and concluded "no spec changes
   needed."

## Why NOT tighten the spec

Editing 44 claims in the frozen, binding-reviewed spec would risk reopening the
cross-section contradiction class the binding review just cleared, and the
failures are artifacts so tightening would not flip them. HANDOFF directive:
STOP if the run heads into planning / overwriting the converged spec.

## Effect on resume

The Step 10w precondition ("spec-eval-*/spec-eval-verification.md contains
STATUS: PASS") is satisfied-by-waiver. The orchestrator proceeds from
Step 9w.9 (ghost-file cleanup) → Step 10w (spawn). This file is NOT a
fabricated PASS — the gate genuinely returned FAIL; this is a documented,
human-authorized override of a credible-but-mismatched gate. Precedent: Run 068.

## Self-audit requirement

The self-audit-reviewer MUST surface this waiver as a HIGH-visibility item:
record that the spec-eval gate was human-WAIVED, that the 44 residual failures
were dispositioned as single-shot-agent / harness artifacts (with several being
spec-compliant behavior the scorer misjudged), and that the spec passed the two
binding structural gates. Do NOT claim the spec-eval gate PASSED.

## Carry-forward (review/compound — NOT a spec change)

The 9w.8 scorer produces false-FAILs on (a) spec-allowed exceptions (the
`:memory:` throwaway, the stale-reaper SQL form), and (b) truncated/empty
single-shot output. Log this to agent-pitfalls.md + the run's solution doc so
future runs interpret the gate correctly.
