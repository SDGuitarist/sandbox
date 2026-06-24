# Codex Re-Review Handoff — G1 Firebreak Phase 1 (post-NO-GO fixes)

**Date:** 2026-06-24
**Repo:** `~/Projects/sandbox` · **Branch:** `feat/g1-risk-tiered-firebreak` (pushed)
**Range to review:** your NO-GO was against `5f4d6d8`; fixes are in `49a6e9c..23bfc58` (HEAD `23bfc58`).
**Prior verdict:** NO-GO for activation (4 false negatives). **This pass:** confirm the fixes hold and hunt for new gaps before activation.

## What changed since your NO-GO

Your four findings + three deeper variants I found in a self-review are all fixed,
test-locked, and the residual #3 wording is re-bounded. Files touched:
`.claude/hooks/firebreak-classify.py`, `.claude/hooks/firebreak-gate.sh`, all four
test corpora, HANDOFF, and `docs/reviews/2026-06-24-g1-phase1-sixth-review.md`.

| Your finding | Fix to verify |
|---|---|
| **P0** control-plane missed metadata/creation verbs | `CP_WRITE_VERBS` now adds `chmod`/`chown`/`chgrp`/`touch`/`mkdir`/`chflags`/`setfacl`/`xattr`/`link`/`mkfifo`/`mknod`; gate got matching verb markers (escaping dests like `/etc/x` have no path marker, so the verb marker preserves the superset invariant). |
| **P0** runner value-flags hid the inner command | `WRAPPER_VALUE_FLAGS` (npx) + `RUNNER_VALUE_FLAGS` (two-token) now include `-w`/`--workspace`/`--filter`/`--prefix`/`--cwd`/`--dir`. |
| **P1** `corepack`/`pnpx` shims | Added to `WRAPPERS`. |
| **P1** MCP read-only allowlist allowed compound mutating verbs | `mcp_decision` vetoes FIRST on any mutating token, splitting on `_`/`-` **and** camelCase, exact-token match (`get_updates` is NOT vetoed). New `MCP_MUTATING_TOKENS`. |
| self-review: global dispatcher flag before the runner verb (`pnpm --filter app exec X`) | New `_runner_subcommand_end` skips the dispatcher's global value-flags to find the runner verb. |

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
2. **Over-defer / false positives** introduced by the new verbs — does a benign
   in-worktree `chmod`/`touch`/`mkdir`/`setfacl`, a benign MCP read verb, or a
   benign runner build command now wrongly defer?
3. **Superset invariant** still holds for every NEW denial (gate forwards it)?
4. **Is residual #3 now correctly and honestly bounded**, or still over/under-claimed?
5. Anything that should still **block activation** (global hook wiring +
   orchestrator integration), which remains OUT OF SCOPE for this review.

## Run the tests (baseline to confirm)

```
python3 .claude/hooks/test_firebreak_classify.py     # 151/151
python3 .claude/hooks/test_firebreak_gate.py         # 26/26
python3 .claude/hooks/test_firebreak_superset.py     # 177 cases, 0 gaps
python3 .claude/hooks/test_firebreak_soundness.py    # 107 RED + 40 GREEN
```

If clean, return GO (or GO-WITH-RESIDUALS naming the accepted residuals). Otherwise
return findings as P0/P1/P2 with exact file:line (and R/F number) to change.
