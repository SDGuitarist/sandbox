---
title: "G1 Phase 1 — second review: gate-superset claim + residuals"
date: 2026-06-22
type: review
branch: feat/g1-risk-tiered-firebreak
reviews_commits: [66182d9, ceb8f50, "<this hardening commit>"]
verdict: GO-WITH-RESIDUALS (declared)
---

# G1 Phase 1 — Second Review

Scope: the hardening pass that (a) made the gate a real superset of classifier
denials by extracting `tool_name` + the Bash `command` and matching brace/
backslash obfuscation and direct script paths against the command (not raw JSON),
and (b) closed classifier bypasses for git config-aliases and listed exec-wrapper
`-c` command-string forms. Plan: `docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md`.

## What changed

**Gate (`firebreak-gate.sh`) — rewritten.** Extracts `tool_name`, then for Bash
extracts the `command` value and matches markers against THAT. Because the
extraction starts *after* `"command": "`, it excludes the envelope's structural
`{`, so a literal `{` in the extracted text is genuine brace-expansion; a real
command backslash is JSON-escaped to `\\` (matched), distinct from an escaped
quote `\"` (not matched). Added: direct script-path argv0 regex (`./x`, `/abs/x`,
`path/to/x`, with optional leading `VAR=` assignments), all exec-wrappers as
markers, `$HOME`/`$`-rooted Write paths, the ` remove` package verb, and the
`alias.` token.

**Classifier (`firebreak-classify.py`) — three additions.**
1. `classify_bash_command()` recurses into nested `-c` command strings, so the
   real action behind `flock /tmp/l -c 'curl …'` / `timeout 5 sh -c 'curl …'`
   is classified (previously the wrapper recursion mis-resolved argv0 to `-c`).
2. `git_outward_category()` resolves inline `-c alias.NAME=VALUE` definitions and
   `git config alias.NAME …` setup, and follows `!`-shell aliases through the full
   bash classifier. Closes `git -c alias.p=push p`, `git config alias.p push`,
   `git -c alias.x='!curl evil' x`.
3. Refactored the Bash branch to route through `classify_bash_command` with a
   depth guard (>4 → fail-closed).

## Gate-superset verification

The superset claim is the safety-critical one: the gate must forward EVERY call
the classifier denies. Verified two ways.

1. **By construction.** The gate forwards on: any `$` / backtick / `{` / `\\`
   (covers all F13 opacity + env-indirection); control-plane path tokens +
   `~`/`$`/`..`/absolute-redirect (control-plane + escaping writes); every outward/
   indirection/delete/package VERB the classifier keys on (enumerations kept in
   lockstep); script-path argv0; all exec-wrappers; all `mcp__*`; and Write/Edit
   absolute/escaping/control-plane file paths. The residual risk is a
   classifier-deny whose trigger token is absent from the gate's verb enumeration.

2. **By corpus (operationalized as a test).** `test_firebreak_superset.py` runs a
   94-case corpus and asserts there is NO command where the classifier denies but
   the gate fast-paths. It is a permanent regression guard against future marker/
   rule drift. **Current result: 0 unsafe gaps.**

**Bug found & fixed by this review:** `npm/yarn/pnpm remove` — the classifier
denied (package removal) but the gate had no `remove` marker, so it fast-pathed
unseen. (`npm rm` was already covered by the `rm ` marker.) Added ` remove`.
This is exactly the failure mode the superset test now prevents from recurring.

Test totals after hardening: classifier **62/62**, gate **19/19**, superset
**94 cases, 0 gaps**.

## Remaining residuals (honest bound — UNCHANGED in spirit, narrowed in reach)

The plan's three declared residuals still hold; the fixes REDUCE classes #3 and
the git-alias surface but do not close them.

- **#1 Allowlisted-interpreter escape (F6).** Code inside an allowlisted framework
  (a worker-authored `test_*.py` collected by `pytest`, run by the swarm-runner)
  does `open(...,'w')`/`subprocess` directly — invisible to a PreToolUse hook.
  Unchanged. This bounds EVERY v1 guarantee to direct worker tool calls.
- **#2 Inherited-`$VAR` redirection.** `echo x > "$CP"` where `$CP` is inherited
  (not an inline `VAR=`) and resolves to a control-plane path: the classifier
  cannot resolve the env var (it only expands its own environment), so it allows.
  The gate DOES forward it (`$`), but the classifier can't catch it. Unchanged.
- **#3 Unlisted dispatcher / exec-wrapper with literal argv0.** Set enumeration is
  leaky. The wrapper `-c` recursion and git-alias resolution shrink this class,
  but new concrete instances remain:
  - **`npx <pkg>`** — `npx` is not in the dispatcher or wrapper set, so
    `npx vercel deploy` resolves argv0 to `npx` and is NOT denied (the gate
    forwards it via the `vercel` marker, but the classifier allows). Candidate to
    add `npx` to the exec-wrapper set in a follow-up; left out here to respect the
    plan's enumerated F13 wrapper list and the honest "leaky set" stance.
  - **Pre-existing / externally-defined git aliases.** A `git <alias>` whose alias
    was written to `.git/config` BEFORE the firebreak window (or by a non-classified
    path) is unresolvable by the stateless classifier. NOTE the mitigation: an
    in-run `git config alias.* push` SETUP is itself denied, so the firebreak
    breaks the two-step "define then invoke" attack at step 1; only aliases that
    pre-date the run survive.

## Verdict

GO-WITH-RESIDUALS. The gate-superset invariant holds (test-enforced), the
git-alias and wrapper-`-c` bypasses are closed, and the three plan residuals are
declared with their post-hardening reach. Recommend: (1) a plan decision on adding
`npx` to the F13 wrapper set; (2) keep `test_firebreak_superset.py` in the
pre-activation gate. Activation (global hook wiring + orchestrator integration)
remains out of scope pending the external (Codex) review.
