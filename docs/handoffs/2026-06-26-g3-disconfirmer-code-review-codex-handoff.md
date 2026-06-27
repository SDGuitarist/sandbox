# Codex Code-Review Handoff — G3 Self-Audit Disconfirmer

**Date:** 2026-06-26
**Repo/branch:** `~/Projects/sandbox`, `feat/g3-verification-diversity`
**Diff range:** `2a333e5..b9e590b` (7 commits, +536/-18 across 8 files)
**Plan (completed):** `docs/plans/2026-06-25-feat-g3-self-audit-disconfirmer-plan.md`
**Probe (PASSED):** `docs/spikes/2026-06-25-g3-disconfirmer-efficacy-probe.md`

This is the CODE review (the PLAN review already returned GO; the verify-first efficacy
probe already returned PASS). Review the implementation, not the design.

---

## Codex prompt (paste into a fresh Codex context)

```
You are doing a fresh, skeptical CODE review of a completed change in ~/Projects/sandbox
on branch feat/g3-verification-diversity. Review the diff 2a333e5..b9e590b (7 commits,
8 files). This is a markdown-instruction + one Python change to an autonomous build
("autopilot") system — there is no app runtime; the "code" is agent briefs, skill gates,
and a disk-verify tool. Correctness = the instructions are unambiguous, the gate is truly
fail-closed, and the two tail paths cannot drift.

WHAT IT DOES: an Opus "self-audit-disconfirmer" agent runs ONCE, BEFORE the Sonnet
self-audit-reviewer, in both the solo (.claude/skills/autopilot/SKILL.md) and swarm
(.claude/agents/tail-runner.md Step 7.5) tails. It writes docs/reports/<run-id>/
disconfirmer.md with local D# findings (or the literal "No disconfirmer findings."
sentinel). The self-audit-reviewer ingests each D# as one WARN (Source=disconfirmer.md#D<n>,
severity verbatim). A new deterministic, fail-CLOSED Gate 8 in
.claude/skills/verify-self-audit/SKILL.md enforces existence/identity/parseability (8a) and
per-finding bijection + ACCEPTED-dismissal #D<n> token (8c). tools/verify_delegated_status.py
gains an advisory --artifact-kind disconfirmer (existence+freshness+run-id only, no status),
called at SKILL.md swarm Step 18w.

INVARIANTS THAT MUST STILL HOLD (flag any breach as P0):
- self-audit-reviewer stays model: sonnet (it is NOT bumped to opus).
- No LLM in the deterministic dispose path; no LLM verdict has binding force. Gate 8 is
  literal-token only. The disconfirmer is advisory.
- No re-run / convergence loop. The disconfirmer runs exactly once.
- Disposition enum stays exactly ACCEPTED / PROMOTED / DEFERRED (no DISMISSED). Gate 8c
  uses ACCEPTED as the dismissal set.
- Gates 1–7 of /verify-self-audit are unchanged in semantics (Gate 8 is additive).

LOOK HARDEST FOR, and return as P0/P1/P2 with file:line + concrete fix + a GO/NO-GO:
1. TAIL_SYNC drift / ORDER: is the disconfirmer guaranteed to run BEFORE the self-audit in
   BOTH paths? Could a reader of either file run them out of order, or skip one path? Are
   both TAIL_SYNC_POINT comments now consistent and self-enforcing?
2. Fail-OPEN holes in Gate 8: any path where a missing / stale / truncated / header-only /
   mismatched-run-id disconfirmer.md still PASSes. Specifically: (a) is "header-only with
   neither D# rows nor sentinel" truly a FAIL? (b) can a malformed table be read as
   "zero findings"? (c) solo has no Step 18w disk-verify — is the in-tail freshness story
   honest, and is the partial-tail-abort (disconfirmer written, audit not yet run) boundary
   correctly declared rather than silently passing?
3. Bijection (8c) soundness: is the D<n> -> exactly-one-WARN mapping actually greppable and
   unforgeable? Can the Sonnet reviewer drop, merge, or duplicate a finding and still pass?
   Is the anchored ^| D<n> | regex robust against a stray "D3" in prose, zero-pad (D01),
   or non-sequential D#? Does the ACCEPTED -> needs-#D<n>-token rule have a bypass (e.g.
   PROMOTED/DEFERRED dispositions that should also be checked)?
4. The Python change (tools/verify_delegated_status.py): is the disconfirmer branch placed
   correctly BEFORE the ACCEPT_SETS lookup (which would KeyError)? Does _extract_run_id now
   correctly use the **Run ID:** regex for disconfirmer? Is skipping the status check the
   right call, and does it weaken the existing self-audit/assembly authority model at all?
   Any exit-code collision? (exit codes must stay 1..255.)
5. Gate-count consistency: all five "N gates" mentions in verify-self-audit/SKILL.md should
   now read 8 and match the 8 actual gate headings. Confirm none were missed.
6. Cross-section contradictions between the agent brief, the two tail wirings, the reviewer
   ingestion rule, Gate 8, and the Python tool — e.g. does the disconfirmer's output contract
   (D# format, severity vocab LOW/MEDIUM/HIGH, sentinel text) EXACTLY match what Gate 8 and
   the reviewer expect? A one-character mismatch (e.g. "No disconfirmer findings" vs the
   trailing period) is a real fail-closed-on-valid-run bug — check the literal strings.
7. Arg-count / spawn correctness: the disconfirmer takes 5 args (run_id, reports_dir,
   plan_path, build_tracking_path, handoff_path) — no solution-doc. Both spawn blocks pass
   exactly those, with mode: "bypassPermissions". Confirm.

Return a prioritized findings list (P0/P1/P2, each with file:line + concrete fix) and a
single GO / NO-GO for merging feat/g3-verification-diversity.
```

---

## Reviewer orientation (context, not part of the paste)

- **Files in the diff:** `self-audit-disconfirmer.md` (new), `self-audit-reviewer.md`,
  `tail-runner.md`, `autopilot/SKILL.md`, `verify-self-audit/SKILL.md`,
  `verify_delegated_status.py`, plus the plan + probe docs (informational).
- **Highest pre-identified risk (R1):** TAIL_SYNC drift — the solo and swarm tails are
  duplicated by contract; the disconfirmer had to be wired into both in the same pass with
  correct ordering. The acceptance check asserts *ordering*, not just presence.
- **Already verified by the author:** Python change smoke-tested 6/6 (happy/sentinel PASS,
  missing=2, stale=3, runid-mismatch=6, self-audit-still-needs-status=4); all 5 gate-count
  sites bumped 9→8; reviewer confirmed still `model: sonnet`.
- **Known declared residuals (not bugs to "fix" — confirm they're honestly stated):** solo
  fail-closed is only as strong as the orchestrator reaching /verify-self-audit (same class
  as the pre-existing self-audit risk, not a regression); the manual "copy a prior run's
  file and edit its Run ID" case is out of the unattended threat model; disposition
  monoculture (the lone Sonnet confirmer still disposes the disconfirmer's findings) is the
  primary residual G3 leaves open by design.
