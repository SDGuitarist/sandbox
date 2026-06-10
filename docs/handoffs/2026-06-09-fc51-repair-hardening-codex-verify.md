# Codex Verification Handoff — FC51 Step 9w.9.5 Edit

**Type:** Verification pass (does the implemented edit match the recommendation?).
**Date:** 2026-06-09
**Repo:** `~/Projects/sandbox`
**Branch:** `feat/fc51-worktree-spec-base` (off `master` @ `49deb17`), uncommitted working-tree change.
**File changed:** `.claude/skills/autopilot/SKILL.md` (Step 9w.9.5 only).

---

## Context

You (Codex) already gave the design recommendation for hardening the FC51
spec-provenance REPAIR in autopilot Step 9w.9.5. Your verdict was:

- **PRIMARY repair = cherry-pick the converged spec to the worktree base.**
- **Mandatory post-repair re-verify**, regardless of channel.
- **Inline brief injection = fallback only** (not self-verifying).
- **Cleanup contract** for an abort after repair but before spawn (revert OR
  explicitly record the repaired base; never leave an unexplained side effect).
- Focused skill edit, not a full brainstorm/plan loop.
- The old table's "preferred = brief injection" labeling was backwards.

Full prior handoff: `docs/handoffs/2026-06-09-fc51-repair-hardening-codex-decision.md`.

This pass: **verify the implemented edit faithfully encodes that recommendation**,
with no gaps, no contradictions with the rest of the step, and no new failure modes.

---

## Read first

1. `.claude/skills/autopilot/SKILL.md` — Step 9w.9.5 (lines ~602–676) AND Step 10w
   (the spawn path it gates, ~678+). Read the WHOLE step as it now stands, not just
   the diff, to check internal consistency.
2. `tools/check_spec_provenance.py` — the detector re-run in the re-verify step.
3. The diff below.

---

## The implemented diff

```diff
@@ Step 9w.9.5 @@
-The worktree base is harness-opaque, so do BOTH:
+The worktree base is harness-opaque, so run this gate as a strict sequence —
+detect, repair, re-verify (the proof), then record. Never spawn until the
+re-verify passes (cherry-pick channel) or the fallback is recorded:

 1. **Detect (run the shared detector).** Run:
    `python tools/check_spec_provenance.py --default-branch <default-branch> --original-branch <original_branch> --spec-path docs/plans/<spec>.md`
    ... [unchanged] ...
    If it reports `PROVENANCE_DRIFT`, proceed to Repair; if `PROVENANCE_OK`, skip to Record.

-2. **Repair (choose the reliable channel).** If the SHAs differ:
-   - **Preferred / reliable — make the brief the authoritative spec channel.**
-     Do NOT rely on workers reading the worktree file. Inject the full converged
-     spec (or the per-role relevant sections) INLINE into every worker brief, and
-     tell workers the brief is authoritative over any spec file in their worktree.
-     This sidesteps the harness-opaque worktree base entirely.
-   - **Additional — put the converged spec at the worktree base.** Commit/cherry-pick
-     the converged spec file onto the default branch HEAD (where worktrees root) so
-     the file channel also matches. (NOTE: merging the default branch INTO the
-     feature branch does NOT fix this ...)
-3. **Record.** Write `docs/reports/<run-id>/spec-provenance.md` with line 1 =
-   `STATUS: PROVENANCE_OK` or `STATUS: PROVENANCE_REPAIRED -- <inline-injection | spec-committed-to-base>` ...
-4. NEVER spawn workers while the worktree-base spec differs from the gated spec
-   without recording the repair. ...
+2. **Repair (PRIMARY = put the converged spec at the worktree base).** If the SHAs
+   differ, the goal is NOT "avoid touching the default branch" — it is to make the
+   workers read the EXACT spec the gates validated, and to PROVE it. Only the
+   file-channel repair is self-verifying, so it is the primary path:
+   - **PRIMARY / deterministic — commit/cherry-pick the converged spec onto the
+     default branch HEAD** (where worktrees root) so the file channel matches before
+     spawn. Cherry-pick the spec-only commit if one exists; otherwise commit the
+     converged `docs/plans/<spec>.md` to the default branch as a dedicated spec-only
+     commit. (NOTE: merging the default branch INTO the feature branch does NOT fix
+     this — it leaves the converged spec absent from the default branch. ...)
+   - **FALLBACK ONLY — inline brief injection.** Use this *only* when the
+     deterministic repair cannot be applied cleanly (e.g. the spec change is not
+     isolable into a clean commit). Inject the full converged spec (or per-role
+     sections) INLINE into every worker brief and tell workers the brief is
+     authoritative over any worktree spec file. This is **not self-verifying** — the
+     file channel still differs, so the detector will still report `PROVENANCE_DRIFT`.
+     It reduces risk but does NOT prove equivalence. Never treat it as a peer of the
+     cherry-pick channel.
+3. **Re-verify (MANDATORY — the proof, not an afterthought).** After the repair:
+   - **Cherry-pick channel:** re-run `tools/check_spec_provenance.py` with the same
+     args. Require `STATUS: PROVENANCE_OK` (exit 0) before spawn. If it is anything
+     else, ABORT the spawn — the repair did not close the drift. This re-run IS the
+     proof that all worktrees will read the converged spec (valid as long as
+     worktrees root on the default-branch HEAD in this same repo ...).
+   - **Injection fallback:** the detector will still report `PROVENANCE_DRIFT` (file
+     unchanged). Record an explicit **injected-section manifest** (the list of spec
+     section titles injected, derived from the spec diff between base and feature).
+     This is an AUDIT step, not equivalence proof — flag it as such.
+4. **Cleanup contract (abort safety).** The cherry-pick repair mutates the default
+   branch before the build is validated. If the run ABORTS after the repair but
+   before spawn, the spec-only commit must NOT be left as an unexplained side effect.
+   Either (a) revert the spec-only repair commit on the default branch, OR
+   (b) explicitly record it as the intentional repaired base carried into the next
+   run. Record which in `spec-provenance.md`.
+5. **Record.** Write `docs/reports/<run-id>/spec-provenance.md` with line 1 =
+   `STATUS: PROVENANCE_OK` (no repair needed) or
+   `STATUS: PROVENANCE_REPAIRED -- spec-committed-to-base` (cherry-pick + re-verify
+   PASSED) or `STATUS: PROVENANCE_REPAIRED -- inline-injection-FALLBACK`. Include:
+   both pre-repair blob SHAs; the post-repair re-verify result (cherry-pick) OR the
+   injected-section manifest (injection, labeled "FALLBACK — not equivalence proof");
+   and the cleanup disposition if applicable.
+6. NEVER spawn workers while the worktree-base spec differs from the gated spec
+   without a recorded repair AND (for the cherry-pick channel) a passing re-verify. ...
```

---

## Verify each — does the edit match the recommendation?

1. **Channel priority correct?** Is cherry-pick unambiguously PRIMARY and injection
   unambiguously fallback-only, with no residual "preferred = injection" language
   anywhere in the step?
2. **Re-verify mandatory and correctly scoped?** For cherry-pick, is "re-run detector
   → require PROVENANCE_OK → else ABORT" stated as a hard gate? For injection, is it
   correct that the detector STILL reports DRIFT (so PROVENANCE_OK can NOT be the
   injection gate), and is the manifest-audit substitute clearly labeled non-proof?
   Is there any path where the pipeline could spawn without either a passing
   re-verify OR a recorded fallback?
3. **Cleanup contract sound?** Is the abort-after-repair contract actionable as
   written? Does "revert the spec-only repair commit on the default branch" have any
   hidden hazard (e.g. if other commits landed on the default branch in between)?
   Is option (b) "carry the repaired base into the next run" safe, or could it leak
   an unvalidated spec into a future unrelated run?
4. **Record statuses complete?** Are the three STATUS lines exhaustive and mutually
   exclusive? Any drift case they fail to cover (e.g. spec exists on only one branch
   → detector exit 3; ERROR exit 2 — does the step handle these, or only DRIFT)?
5. **Internal consistency with the rest of 9w.9.5 and Step 10w?** Does the new
   sequence contradict any other precondition (e.g. gate-verification.md CLEARED in
   Step 10w, the path-validation, the worker-roster step)? Does "spawn" mean the same
   boundary in both steps?
6. **New failure modes introduced?** Does making cherry-pick PRIMARY create any
   ordering hazard with the other pre-spawn gates (9w.9 ghost-file cleanup, 10w path
   validation) or with run-id generation? Could committing the spec to the default
   branch interact badly with the FC51 cherry-pick ASSEMBLY (Track A) later in the run?
7. **Anything missing** that your recommendation implied but the edit omitted?

---

## Output we want

- **GO** (edit faithfully encodes the recommendation, safe to commit) or a list of
  blocking findings.
- For each finding: severity, the exact line/bullet, and the minimal fix.
- Confirm there is no path to spawn without a passing re-verify (cherry-pick) or a
  recorded labeled fallback (injection).
