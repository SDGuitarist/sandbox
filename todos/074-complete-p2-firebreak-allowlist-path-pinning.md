---
status: complete
priority: p2
issue_id: "074"
tags: [code-review, firebreak, g1, security, hardening]
dependencies: [071]
---

# P2 — Path-pin the FC58 trusted-pipeline allowlist (retire both basename residuals)

## Problem Statement

The FC58 carve-out (todo 071) matches the pipeline scripts by **basename only**, per
the agreed invariant ("allowlist matches script basenames ONLY"). The run-079 review
(security-sentinel + architecture-strategist) confirmed this is SAFE within the threat
model but leaves two trusted-only residuals:

- **Residual A — no path pinning.** `python3 /tmp/evil/verify_delegated_status.py` run
  BY a trusted identity is ALLOWED (basename matches, path ignored). A test pins this
  as accepted behavior (`FC58 orch path-prefixed allowlisted basename allowed (residual)`).
- **Residual B — `first_verb` flag-value mis-pick.** `python3 -W verify_delegated_status.py
  realscript.py` (orchestrator) returns the allowlisted token as the `-W` *value* and
  grants the carve-out while python actually runs `realscript.py`. Trusted-only; the
  mis-pick is asymmetric (never grants on a non-allowlisted leading target).

Both are exploitable only by an already-trusted identity, which already holds
control-plane Write and can run the real allowlisted scripts (themselves arbitrary
code). So the marginal risk is low — this is hardening, not a live hole.

## Proposed Solution

Pin the allowlist to a small set of resolved repo-relative paths (e.g.
`tools/verify_delegated_status.py`, `tools/check_spec_provenance.py`,
`.claude/hooks/firebreak-activate.py`) and match the **resolved script path**, not
`first_verb`'s token. This closes A (path now matters) and B (resolve the actual
python target rather than the first non-flag token).

**Watch-out:** the orchestrator runs from repo root but worktree workers run from the
worktree root — path resolution must use `repo_root` from the sentinel, and the
carve-out is already TRUSTED-only so worktree-relative paths are not a concern. Confirm
`set-phase`/`deactivate` invocation paths still resolve under the live cwd before
committing (the run-079 lesson: harness-green ≠ live).

## Acceptance Criteria

- [x] `python3 /tmp/x/verify_delegated_status.py` from orchestrator → DEFERRED (residual A closed)
- [x] `python3 -W verify_delegated_status.py realscript.py` from orchestrator → DEFERRED (residual B closed)
- [x] All existing positive carve-out tests still ALLOW (correct relative paths)
- [x] Update the `(residual)` test to assert the new DENY, with a comment noting the change
- [x] Full classifier bench passes

## Work Log

- 2026-06-29: Created from run-079 FC58 review. Both reviewers flagged path-pinning as
  the genuine structural hardening that retires residuals A+B; both rated it P2 optional,
  not a merge blocker. Deferred from the FC58 fix cycle (todos 071-073) per the invariant
  "basename-match only" — changing to path-match is a conscious follow-up decision.
- 2026-07-09: RESOLVED. Replaced the basename set `TRUSTED_PIPELINE_SCRIPTS` with the
  path-pinned set `TRUSTED_PIPELINE_SCRIPT_PATHS` (`tools/verify_delegated_status.py`,
  `tools/check_spec_provenance.py`, `.claude/hooks/firebreak-activate.py`). Added
  `python_script_target()` (resolves python's REAL `.py` target past `-W`/`-X` value-flags
  and returns None for `-c`/`-m` modes, closing residual B) and `_is_pinned_pipeline_script()`
  (resolves the target against `repo_root` from the sentinel and matches the pinned set,
  closing residual A). `trusted_pipeline_indirection_ok` now takes `repo_root`. Flipped the
  residual-A test to DENY, added residual-B DENY test + a `-W ignore` positive control.
  Benches: classifier 281/281, soundness 319 RED + 129 GREEN, superset 297/297. Verified
  live-safe: all SKILL.md invocations are repo-relative python/python3 by the TRUSTED
  orchestrator from repo root (no `$VAR`/absolute forms that would newly defer).
  **Supersedes the "basename-match only" invariant** (this change was its pre-registered
  follow-up).
