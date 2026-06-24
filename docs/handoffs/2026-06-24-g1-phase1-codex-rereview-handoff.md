# Codex Re-Review Handoff — G1 Firebreak Phase 1 (post-NO-GO fixes)

**Date:** 2026-06-24
**Repo:** `~/Projects/sandbox` · **Branch:** `feat/g1-risk-tiered-firebreak` (pushed)
**Range to review:** your NO-GO was against `5f4d6d8`; fixes are in `49a6e9c..a54b640` (HEAD `a54b640`).
**Prior verdict:** NO-GO for activation (4 false negatives). **This pass:** confirm the 6th-pass NO-GO fixes hold AND review the 7th-pass directory-level control-plane fix; hunt for new gaps before activation.

## What changed since your NO-GO

Two fix passes since `5f4d6d8`. All findings are test-locked and the residual #3
wording is re-bounded. Files touched across both passes:
`.claude/hooks/firebreak-classify.py`, `.claude/hooks/firebreak-gate.sh`, all four
test corpora, HANDOFF, and the sixth + seventh review docs in `docs/reviews/`.

### 6th pass — your four findings + three self-review variants

| Your finding | Fix to verify |
|---|---|
| **P0** control-plane missed metadata/creation verbs | `CP_WRITE_VERBS` now adds `chmod`/`chown`/`chgrp`/`touch`/`mkdir`/`chflags`/`setfacl`/`xattr`/`link`/`mkfifo`/`mknod`; gate got matching verb markers (escaping dests like `/etc/x` have no path marker, so the verb marker preserves the superset invariant). |
| **P0** runner value-flags hid the inner command | `WRAPPER_VALUE_FLAGS` (npx) + `RUNNER_VALUE_FLAGS` (two-token) now include `-w`/`--workspace`/`--filter`/`--prefix`/`--cwd`/`--dir`. |
| **P1** `corepack`/`pnpx` shims | Added to `WRAPPERS`. |
| **P1** MCP read-only allowlist allowed compound mutating verbs | `mcp_decision` vetoes FIRST on any mutating token, splitting on `_`/`-` **and** camelCase, exact-token match (`get_updates` is NOT vetoed). New `MCP_MUTATING_TOKENS`. |
| self-review: global dispatcher flag before the runner verb (`pnpm --filter app exec X`) | New `_runner_subcommand_end` skips the dispatcher's global value-flags to find the runner verb. |

### 7th pass — directory-level control-plane mutation (NEW; please scrutinize)

`is_control_plane` matched only the protected **files**, so a worker could disable
the firebreak by mutating the **parent directory** — all classified allow:
`rm -rf .claude/hooks`, `rm -rf .claude`, `rmdir .claude/hooks`, `mv .claude
.claude.bak`, `chmod -R 000 .claude`, `unlink`/`shred` a hook file. Fixes:

| Area | Fix to verify |
|---|---|
| dir-level target | new `is_control_plane_dir(path, repo_root)` — a path that **is or is an ANCESTOR of** a protected location (`.claude`/`.claude/hooks` by shape, plus ancestors of the hooks/sentinel/`~/.claude/settings.json`/`todos/approvals` anchors → catches parent-dir variants `rm -rf .` / `rm -rf ~` / `rm -rf /`). |
| check site | `bash_control_plane` denies a worker write whose positional is a control-plane **file OR dir**; redirects keep the file-only check (a `>` can't remove a dir). |
| bypass verbs | `CP_WRITE_VERBS` += `rmdir`/`unlink`/`shred` (they were `DELETE_VERBS`-only and skipped the control-plane check entirely — a pre-existing hole for files too). |
| `cd`-shift evasion (self-review) | `( cd .claude && rm -rf hooks )` split the sequence and resolved the mutation against the process cwd, missing the `cd`. New fail-closed guard: a sequence that both `cd`/`pushd`s into a control-plane dir AND carries a mutation verb defers (`_cd_into_control_plane` + `_has_mutation_verb`). |

Must stay GREEN (verify no over-defer): `.claude/worktrees/<agent>/...` (worker's
own worktree), `build/`, `.git/hooks`, `cd src && rm -rf build`, `cd .claude && cat
…` (read, no mutation). Trusted identities may still mutate the control plane (F5).

## Residual #3 — re-bounded honestly (your P1 ruling)

Was narrowed to "unrecognized package only" — too narrow. Now stated as: **an
UNLISTED dispatcher/exec-wrapper with a literal `argv[0]`, OR a recognized runner
fetching an UNRECOGNIZED package name.** Recursion lands on the real command word
for every *listed* runner/shim; set enumeration remains leaky by design. Residuals
#1 (allowlisted-interpreter escape) and #2 (inherited-`$VAR` redirect) unchanged.

## Re-review focus (adversarial; P0/P1/P2 with exact file:line + R/F number)

1. **Re-confirm the four fixed classes are actually closed**, including variants I
   may have missed:
   - control-plane metadata verbs through obfuscation (`$HOME`, `..`, symlink,
     env-indirected dest, `--` separators, flag/value ordering);
   - runner value-flags in *new* combinations (other package managers, `=`-joined
     globals, repeated/interleaved flags, value-flag whose value looks like a path);
   - MCP verbs that pair a read prefix with a mutating action your token set or the
     camelCase split still misses (kebab-case, digits, acronyms like `getACLs`);
   - shims/wrappers still off the lists (any new deploy/cloud CLI, `bun`/`deno`
     forms, `corepack <pm> <runner>` chains).
2. **Directory-level control-plane (7th pass) — can a worker still remove/disable
   the hook or sentinel?** Probe: parent-dir reach the classifier can't resolve
   (env-indirected dir `D=.claude/hooks; rm -rf $D`, `$(...)` dir, symlink to the
   dir then delete through it); `cd`/`pushd` chains the guard misses (`cd a; cd
   ../.claude; rm -rf hooks`, subshell nesting, `cd` via `pushd`/`popd`); a
   worktree-nested `rm -rf .` whose cwd is the worktree (not at/above a repo_root
   anchor); and whether `is_control_plane_dir`'s shape match (`endswith /.claude`)
   has a false-positive or false-negative edge.
3. **Over-defer / false positives** from the new verbs/dirs — does a benign
   in-worktree `chmod`/`touch`/`mkdir`/`setfacl`, a benign `rm -rf build`/`rmdir`,
   a `cd .claude && cat …` (read), a benign MCP read verb, or a benign runner build
   command now wrongly defer?
4. **Superset invariant** still holds for every NEW denial (gate forwards it)?
5. **Is residual #3 now correctly and honestly bounded**, or still over/under-claimed?
6. Anything that should still **block activation** (global hook wiring +
   orchestrator integration), which remains OUT OF SCOPE for this review.

## Run the tests (baseline to confirm)

```
python3 .claude/hooks/test_firebreak_classify.py     # 168/168
python3 .claude/hooks/test_firebreak_gate.py         # 26/26
python3 .claude/hooks/test_firebreak_superset.py     # 191 cases, 0 gaps
python3 .claude/hooks/test_firebreak_soundness.py    # 132 RED + 51 GREEN
```

If clean, return GO (or GO-WITH-RESIDUALS naming the accepted residuals). Otherwise
return findings as P0/P1/P2 with exact file:line (and R/F number) to change.
