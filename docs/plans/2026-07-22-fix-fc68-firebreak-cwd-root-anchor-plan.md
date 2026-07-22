---
title: FC68 fix — deterministic firebreak sentinel root anchoring
date: 2026-07-22
type: fix
status: ready
swarm: false
branch: fix/fc68-firebreak-cwd-anchor
tracks: 083-W6
feed_forward:
  risk: "The worktree carries its own tracked copy of firebreak-activate.py, so __file__-relative anchoring alone can still resolve to a worktree root if the worktree copy is the one executed. The fix must fail CLOSED (refuse) in that case, not silently write to the wrong root."
  verify_first: true
---

# FC68 fix — deterministic firebreak sentinel root anchoring

Closes the HIGH-severity deferred item **083-W6** (self-audit Run 083). The G1
firebreak's activator (`.claude/hooks/firebreak-activate.py`) derives the repo
root from the **current working directory** (`git rev-parse --show-toplevel` in
cwd). During Run 083 the orchestrator's cwd drifted into a lingering worker
worktree, so `activate` wrote the run sentinel **into that worktree**
(`.claude/worktrees/agent-.../.claude/firebreak-active.json`) and set its
`repo_root` field to the worktree. The main-repo sentinel was **absent** during
the wave-transition window. Sibling-wave workers discover the sentinel by
walking **up** from their own worktree cwd (`find_sentinel`, classifier
line 2266) — they walk up to the main repo root and find nothing → **silent
fail-open of the primary safety control**. Caught only by a manual `cat`-verify
of the sentinel's `repo_root`; no ungoverned worker actually ran, but nothing
structural prevented it.

Root cause class: **FC68** (`RC-firebreak-cwd-root-drift`), registered in
`~/.claude/docs/agent-pitfalls.md`. Evidence: `docs/reports/083/harvest-findings.md`
(H7), `docs/reports/083/self-audit.md` (083-W6), `docs/reports/083/firebreak-probe.md`.

## 1. What exactly is changing?

**A. `.claude/hooks/firebreak-activate.py` — root derivation (the fix).**
Replace cwd-relative `git rev-parse` with a deterministic resolver:

1. `--root <abs-path>` (PREFERRED) — the orchestrator passes the known main-repo
   absolute path. Immune to cwd drift AND to which copy of the script executed.
2. `__file__`-relative fallback — the hook lives at
   `<repo>/.claude/hooks/firebreak-activate.py`, so the repo root is two directory
   levels up from the hooks dir (`dirname×3` of the abs `__file__`).
3. **Validation (fail CLOSED).** The resolved root must:
   - contain `.claude/hooks/firebreak-classify.py` (it is a real firebreak repo), AND
   - **NOT** be inside a worktree — reject if the normalized path contains
     `/.claude/worktrees/`.
   On any validation failure, write a loud error to stderr and **exit non-zero**
   (refuse) — never fall back to cwd, never write the sentinel to a worktree.

The resolved root is used for BOTH the sentinel write location AND the sentinel's
`repo_root` field, and is threaded through all four subcommands
(`activate`/`set-phase`/`deactivate`/`status`). `--root` is optional and parsed
out before the existing positional args, so every current call shape keeps working.

**B. `.claude/skills/autopilot/SKILL.md` — structural read-back gate.**
- Step 9w.9.6: `activate` is invoked with an explicit `--root <main-repo-abs>`, and
  a **post-activation read-back gate** is added: `cat <root>/.claude/firebreak-active.json`
  and assert its `repo_root` == the expected main-repo root; **abort the spawn on
  mismatch**. This is the structural replacement for the manual `cat`-verify. A note
  requires re-asserting the read-back before **each wave spawn** in multi-wave runs.
- Step 17w: `set-phase` invoked with `--root <main-repo-abs>`.
- New short subsection formalizing the **H5** orchestrator-gate-window toggle
  protocol (see §H5 below).

**C. `tests/test_firebreak_activate_root.py` — live-lifecycle test (new).**
Proves: activating from a worktree cwd with `--root <main>` lands the sentinel at
the MAIN root with `repo_root == <main>`; and the `__file__`/no-`--root` path
**refuses** (non-zero) when the resolved root is inside a worktree.

**D. `~/.claude/docs/agent-pitfalls.md` — FC68 entry** updated to record the
structural fix (allowed out-of-repo learnings-propagation write, compound phase).

## 2. What must NOT change?

- **`firebreak-classify.py`'s `find_sentinel()` walk-up discovery** (line 2266) —
  it is cwd-independent and correct; the bug is in the ACTIVATOR's root
  derivation, not the classifier's discovery. Do not touch it.
- The classifier's `TRUSTED_PIPELINE_SCRIPT_PATHS` carve-out and its explicit
  exclusion of `-c`/`-m` module mode (no file to path-pin). The H5 decision below
  deliberately does NOT weaken this.
- `firebreak-activate.py`'s **path** stays `.claude/hooks/firebreak-activate.py`,
  so it remains on the trusted allowlist (editing content ≠ changing the pinned path).
- The sentinel JSON schema (`run_id`, `repo_root`, `project_key`, `phase`,
  `test_allowlist`) — the classifier reads these fields; keep them all.
- Existing positional CLI shapes (`activate <run_id> [project_key] [phase] [json]`,
  `set-phase <phase>`, `deactivate`, `status`) — backward compatible.

## 3. Acceptance Tests (EARS)

### Happy path
- WHEN `activate <run-id> --root <MAIN>` is run with cwd inside a lingering
  worktree THE SYSTEM SHALL write the sentinel to `<MAIN>/.claude/firebreak-active.json`
  with `repo_root == <MAIN>` and exit 0.
  - Verify: `.venv/bin/python .claude/hooks/firebreak-activate.py activate T1 --root <MAIN>` run from a worktree dir, then `jq -r .repo_root <MAIN>/.claude/firebreak-active.json` == `<MAIN>`.
- WHEN `activate <run-id>` is run with NO `--root` and cwd == the main repo root
  THE SYSTEM SHALL resolve the root via `__file__` and write the sentinel at the
  main root (backward-compatible behavior for the non-drift case).
  - Verify: activate with no `--root` from main root; sentinel `repo_root` == main root.
- WHEN `set-phase tail --root <MAIN>` is run THE SYSTEM SHALL update the phase
  field of `<MAIN>/.claude/firebreak-active.json` in place, preserving `run_id`
  and `repo_root`, and exit 0.
  - Verify: `jq -r .phase` == `tail` and `jq -r .run_id` unchanged.

### Error cases (fail CLOSED)
- WHEN the resolved root is inside a worktree (path contains `/.claude/worktrees/`)
  THE SYSTEM SHALL print a loud error to stderr and exit non-zero WITHOUT writing
  any sentinel.
  - Verify: invoke the worktree's COPY of the script (or `--root <worktree>`); assert non-zero exit and no `firebreak-active.json` under the worktree.
- WHEN the resolved root does NOT contain `.claude/hooks/firebreak-classify.py`
  THE SYSTEM SHALL print a loud error and exit non-zero.
  - Verify: `--root /tmp` → non-zero exit, stderr names the missing classifier.
- WHEN (SKILL 9w.9.6) the post-activation read-back finds `repo_root` != the
  expected main root THE SYSTEM SHALL abort the wave spawn.
  - Verify: read-back assertion in SKILL.md aborts on mismatch (documented gate).

### Verification commands
- `.venv/bin/python -m pytest tests/test_firebreak_activate_root.py -q` — all pass.
- `.venv/bin/python -m pytest tests/ -q` — no regression in the existing suite.
- `.venv/bin/python .claude/hooks/firebreak-activate.py status --root <MAIN>` — reports ACTIVE/INACTIVE against the main root.

## 4. Most likely way this plan is wrong

The single biggest uncertainty (Feed-Forward risk): **`__file__` anchoring is not
sufficient by itself** because worktrees carry a tracked copy of the activator, so
if the orchestrator runs `python3 .claude/hooks/firebreak-activate.py` with cwd in
a worktree, the worktree's copy runs and `__file__` two-up = the worktree root.
The mitigation is the **fail-closed worktree guard**: that path must REFUSE, not
write. If the guard's worktree-detection (substring `/.claude/worktrees/`) is
wrong or bypassable, the fix is incomplete. Hence `--root` is the PRIMARY channel
(orchestrator always passes it) and the guard + read-back gate are defense in depth.
A second-order risk: a future worktree layout that is NOT under `.claude/worktrees/`
would evade the substring guard — the `--root` primary channel + read-back gate
still cover it, which is why we do not rely on the guard alone.

## H5 decision (related, LOWER priority — FC58 variant)

`python -m compileall` and `python -m <pkg>.smoke` are NOT on
`TRUSTED_PIPELINE_SCRIPT_PATHS`, and `-m` module mode never qualifies for the
carve-out (there is no script FILE to path-pin). Two options:

- **(i) Narrow module-mode carve-out** for those two orchestrator gate invocations.
  **REJECTED.** A `-m` carve-out can only match by module NAME, not a pinned path.
  Module resolution honors `sys.path`, which a worktree/worker could shadow — so a
  name-based carve-out is materially weaker than the path-pinned file carve-out and
  would erode the exact `-c`/`-m` exclusion the classifier deliberately maintains.
  Weakening the classifier to fix an orchestrator-convenience issue is a poor trade.
- **(ii) Formalize the deactivate-for-orchestrator-gate-window toggle protocol** in
  SKILL.md. **CHOSEN.** The orchestrator is TRUSTED and already owns the firebreak
  lifecycle (activate / set-phase / teardown). Between waves (a barrier where NO
  workers are spawned) it may `deactivate` for its own parse/smoke gate window and
  re-`activate` — with the new read-back gate re-asserting the sentinel's root —
  before the next wave spawn. This keeps the security property intact (workers never
  run in the gate window) without weakening the classifier. Documented as a bounded,
  reactivate-before-spawn protocol.

This decision is surfaced to the human in the run summary; the code change (A) is
independent of it and can land first.

## Feed-Forward
- **Hardest decision:** Whether `__file__` anchoring alone closes FC68. It does
  not — the worktree's tracked copy of the activator defeats it. Resolved by making
  `--root` the primary channel and the worktree guard **fail closed**, converting a
  silent wrong-root write into a loud refuse.
- **Rejected alternatives:** (1) Keep `git rev-parse` but add a post-hoc cwd check —
  still cwd-coupled, fragile. (2) H5 option (i) module-mode carve-out — weakens the
  classifier's `-m` exclusion (see H5). (3) `__file__`-only anchoring — insufficient
  against the worktree copy.
- **Least confident:** The worktree-detection guard relies on the `/.claude/worktrees/`
  path convention. If a future harness places worktrees elsewhere, the guard misses
  it — but the `--root` primary channel + SKILL read-back gate still cover that case,
  so the guard is the third layer, not the only one.
