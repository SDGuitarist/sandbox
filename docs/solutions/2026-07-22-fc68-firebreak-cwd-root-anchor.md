---
title: "FC68 fix — deterministic firebreak sentinel root anchoring (git-metadata)"
date: 2026-07-22
status: complete
type: fix
branch: fix/fc68-firebreak-cwd-anchor
closes: [083-W6, FC68]
tags: [governance, firebreak, G1, worktree, cwd-drift, safety-control, run-083]
related:
  - docs/plans/2026-07-22-fix-fc68-firebreak-cwd-root-anchor-plan.md
  - docs/reports/083/self-audit.md
  - docs/reports/083/harvest-findings.md
  - docs/solutions/2026-07-22-swarmlimit-19-agent-max-value-swarm-build.md
codex_review: "NO-GO (P1) round 1 -> fix -> GO (P0/P1/P2 = 0) round 2"
---

# FC68 fix — deterministic firebreak sentinel root anchoring

Closes the HIGH-severity deferred item **083-W6** (Run 083 self-audit) and gives
failure class **FC68** (`RC-firebreak-cwd-root-drift`) a structural fix. This was
a **silent fail-open of the primary G1 safety control**, so it was treated as a
governance-critical change: full plan → work → Codex review → fix → Codex GO cycle.

## The original failure (cwd-drift fail-open)

The G1 firebreak is a PreToolUse classifier (`.claude/hooks/firebreak-classify.py`)
that is a **no-op unless a run sentinel exists** at
`<main-repo>/.claude/firebreak-active.json`. Worker agents run in isolated git
worktrees under `<main-repo>/.claude/worktrees/agent-*/` and **discover** the
sentinel by walking **up** from their own cwd (`find_sentinel`). The main repo root
is an ancestor of every worker worktree, so the sentinel MUST live at the **main
root** for a sibling-wave worker to find it.

The activator (`firebreak-activate.py`) derived the repo root from the **current
working directory** (`git rev-parse --show-toplevel` in cwd). During Run 083 the
orchestrator's cwd drifted **into a lingering worker worktree** at a wave
transition, so `activate` wrote the sentinel *inside that worktree*
(`.claude/worktrees/agent-…/.claude/firebreak-active.json`) and stamped its
`repo_root` field with the worktree path. The **main-repo sentinel was absent**
during the Wave 0 → Wave 1 window. A sibling-wave worker walking up from its own
worktree never traverses a sibling's tree, so it found **nothing** → the classifier
silently stopped governing → **fail-open**. It was caught only by a manual
`cat`-verify of the sentinel's `repo_root`; no ungoverned worker actually ran, but
nothing structural prevented it.

## Why `__file__` anchoring alone was insufficient

The obvious first fix — anchor the root to the script's own location
(`<repo>/.claude/hooks/firebreak-activate.py` → two dirs up) instead of cwd — is
**not sufficient**, and this was the plan's pre-registered least-confident risk. The
reason: **each worktree carries its own tracked copy** of
`.claude/hooks/firebreak-activate.py`. The orchestrator invokes the tool as
`python3 .claude/hooks/firebreak-activate.py` (a cwd-relative path), so when cwd has
drifted into a worktree, the **worktree's copy** executes and `__file__` two-up
resolves to that **worktree root** — the exact wrong answer, again. `__file__`
anchoring fixes the "main copy ran from a drifted cwd" case but not the "worktree
copy ran" case. So `--root` (an explicit absolute path the orchestrator captures
once, before drift) is the primary channel, and `__file__` is only a fallback that
must itself be validated.

## Why lexical pathname detection was rejected (Codex P1)

The first implementation validated the resolved root by refusing any path whose
string contained `/.claude/worktrees/`. Codex's binding review (round 1: **NO-GO**)
correctly found this **bypassable**:

- A **linked worktree placed elsewhere** — `git worktree add` accepts any path, not
  only under `.claude/worktrees/` — has no such substring, yet still carries its own
  tracked `firebreak-classify.py`, so the classifier-presence check passed too.
- A **symlink alias** to a worktree, or a **case-variant** spelling on a
  case-insensitive filesystem, both evade a literal substring match.
- A **relative `--root`** was silently `abspath`-ed against cwd, re-introducing the
  very cwd coupling the fix was supposed to remove.

A wrong `<MAIN>` then made `activate` and `status` agree on the *same wrong value*,
so a read-back gate that merely compared them would pass while sibling workers
stayed ungoverned. **Lexical pathname detection cannot soundly distinguish a main
worktree from a linked one** — the distinction is a property of Git's on-disk state,
not of the path string.

## The final solution (absolute + realpath + Git-metadata)

`anchored_root()` now resolves and validates **pathname-independently**:

1. **Absolute `--root` only.** An explicit `--root` is `expanduser`-ed and then
   **rejected unless `os.path.isabs`** — a relative value cannot re-introduce cwd
   coupling. `--root` (captured once by the orchestrator before drift) is the
   preferred channel; `__file__` two-up is the fallback.
2. **Canonicalize first.** The candidate is `os.path.realpath`-ed **before**
   validation, sentinel placement, and `repo_root` storage — this defeats **symlink
   aliases** and **case variants** (git then resolves the canonical path).
3. **Git-metadata main-worktree check.** The canonical root must:
   - be a git **worktree top-level**: `git -C <root> rev-parse --show-toplevel`
     equals `<root>` (not a subdirectory), AND
   - be the **MAIN** worktree, not a linked one:
     `git -C <root> rev-parse --git-dir` **equals** `--git-common-dir`. A linked
     worktree's per-worktree git-dir (`<main>/.git/worktrees/<name>`) differs from
     the shared common-dir (`<main>/.git`); the main worktree's are identical. This
     holds **regardless of where the worktree lives, how it is aliased, or its case
     spelling**.
   - still carry `.claude/hooks/firebreak-classify.py` (a real firebreak repo).
4. **Fail closed.** Any validation failure prints a loud stderr line and **exits 3
   with no sentinel written** — the old silent wrong-root write is now a hard refuse.

The literal `/.claude/worktrees/` substring guard was **removed entirely** — the Git
check subsumes it. Proven live against a real lingering worktree: rejected because
`git-dir …/.git/worktrees/agent-… != common-dir …/.git`.

## The exit-code-driven per-wave read-back gate (SKILL 9w.9.6)

The manual `cat`-verify that caught the incident is replaced by a structural gate:

- **Step 0** captures `<MAIN>` **once**, before any worker spawns (cwd is still the
  main root), and reuses that literal for every `firebreak-activate.py` call and
  every `rm …/firebreak-active.json` teardown — never a fresh `git rev-parse` from a
  possibly-drifted cwd.
- **Step 1b** is an **independent** machine check: it runs
  `firebreak-activate.py status --root <MAIN>` and **branches on the exit code**.
  Because `status` re-runs `anchored_root()`, it *independently re-proves* `<MAIN>`
  is the main worktree via Git metadata (exit 3 → wrong root → **abort the spawn**),
  rather than comparing two values derived from the same possibly-wrong capture.
  Exit 0 + `INACTIVE` → sentinel missing → abort; exit 0 + `ACTIVE … root=<MAIN>` →
  proceed.
- The read-back is **re-asserted before EACH wave spawn** and after any firebreak
  toggle — the FC68 incident happened at a wave transition, *after* the one-time
  positive-control probe, so the probe alone does not protect later waves.

The H5 orchestrator-gate-window issue (module-mode `python -m compileall` / `-m
<pkg>.smoke` are not path-pinnable for the trusted carve-out) is handled by a
**formalized deactivate → gate → reactivate → read-back** toggle bounded to the
between-waves barrier (no worker runs in that window). A name-based `-m` carve-out
was **rejected** — module resolution honors `sys.path`, which a worktree can shadow,
so it is materially weaker than path-pinning and would erode the classifier's
deliberate `-c`/`-m` exclusion.

## Risk Resolution

- **Flagged risk (plan Feed-Forward, "least confident"):** `__file__` anchoring alone
  might be insufficient because the worktree carries its own tracked copy of the
  activator, so lexical/self-location detection could still resolve to a worktree
  root.
- **What happened:** the risk **fired** — Codex's round-1 P1 was exactly this class:
  the substring guard was bypassable (elsewhere-placed linked worktree, symlink,
  case variant) and relative `--root` re-coupled to cwd. The first implementation
  was NO-GO.
- **What was learned:** the sound anchor is **Git's own worktree metadata**
  (`git-dir == git-common-dir`), not any string property of the path, combined with
  `realpath` canonicalization and an absolute-only `--root`. The read-back gate must
  **independently re-run** that validation (exit-code branch), not compare
  same-source values. This is the general lesson for FC68: *governance tools that
  self-locate must validate their anchor against ground truth (Git/filesystem
  metadata), fail closed, and be re-checked at each trust boundary.*

## Accepted residuals (from the mandatory second self-review; Codex-accepted)

1. **Cross-repo misconfiguration.** A `--root` pointing at a *different* repository's
   main worktree that also carries firebreak files would be accepted — the check
   verifies "a main worktree + firebreak files", not "*this* repo's". Outside FC68's
   same-repo linked-worktree-drift threat; mitigated because the orchestrator derives
   `<MAIN>` from its own `git rev-parse --show-toplevel` (Step 0) plus the read-back.
2. **Requires git ≥ 2.5** (`--git-common-dir`). Older git makes every root fail
   closed — an availability limitation, not a safety bypass.
3. **Privileged-local PATH-poisoning / TOCTOU** remain outside the threat model — the
   firebreak governs worker *tool calls*, not local filesystem races by a privileged
   actor.

## Verification

- `tests/test_firebreak_activate_root.py` — **18 tests** on real git repos +
  `git worktree add` (linked-worktree-outside-`.claude/worktrees`, symlink alias to
  linked/main, relative `--root`, case-variant, subdir, non-git, missing-classifier,
  worktree-copy fail-closed, deactivate, status active/inactive, legacy 4-positional
  form, `--root=`, arg positions, set-phase field preservation) — all pass.
- Existing firebreak suites unaffected: classify **282**, gate **26**, soundness
  **319R+129G**, superset **297**.
- `git diff --check` clean. Codex round 2: **GO**, P0/P1/P2 = 0.

## Feed-Forward
- **Hardest decision:** How to distinguish the main worktree from a linked one
  *soundly*. Lexical detection (any path-string heuristic) is bypassable; the answer
  is to ask Git (`git-dir == git-common-dir`), which is ground truth regardless of
  location, symlink, or case. Running `git` here is safe (it is anchored to the
  explicit candidate root, not the ambient cwd that caused FC68).
- **Rejected alternatives:** (1) `__file__`-only anchoring — defeated by the
  worktree's own tracked copy. (2) `/.claude/worktrees/` substring guard — bypassable
  (Codex P1). (3) H5 module-mode `-m` carve-out — `sys.path`-shadowable, weaker than
  path-pinning; rejected in favor of a bounded deactivate/reactivate toggle. (4) A
  read-back that compares two same-source values — passes on a wrong capture; replaced
  by an exit-code branch that re-runs validation.
- **Least confident:** Residual #1 (cross-repo misconfig). It is out of the FC68
  threat model and operationally mitigated, but a future hardening could bind the
  accepted root to the orchestrator's own repository identity (e.g., compare the
  resolved `git-common-dir` against the orchestrator's) if cross-repo runs ever
  become real.
