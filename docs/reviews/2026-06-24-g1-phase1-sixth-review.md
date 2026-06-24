---
title: "G1 Phase 1 — sixth review: Codex NO-GO fixes (control-plane metadata verbs, runner value-flags, MCP compound verbs) + second self-review"
date: 2026-06-24
type: review
branch: feat/g1-risk-tiered-firebreak
verdict: GO-WITH-RESIDUALS (declared; residual #3 re-bounded honestly)
focus: "P0/P1 classifier false negatives found by Codex (pre-activation NO-GO) + self-review sweep"
---

# G1 Phase 1 — Sixth Review (Codex NO-GO → fixed)

Codex reviewed the hardened Phase 1 implementation (handoff
`docs/handoffs/2026-06-23-g1-phase1-impl-codex-review-handoff.md`) and returned
**NO-GO for activation** with four classifier false negatives OUTSIDE the corpus
(the gate forwarded them; the classifier allowed). The official suites still passed
— these were gate-forwarded/classifier-allowed gaps, exactly the soundness
direction. All four are fixed, locked into the corpora, and a second self-review
sweep found and fixed three deeper variants of the same classes.

## Codex findings fixed

| Sev | Finding | Fix |
|-----|---------|-----|
| **P0** | **Control-plane protection missed metadata/creation verbs.** `bash_control_plane` only checked positionals when `argv0 ∈ CP_WRITE_VERBS`, which excluded `chmod`/`chown`/`chgrp`/`touch`/`mkdir`/`chflags`. A worker could `chmod 000 .claude/hooks/firebreak-classify.py` or `touch .claude/firebreak-active.json` to disable/clobber the control plane. | Added those verbs (+ self-review `setfacl`/`xattr`/`link`/`mkfifo`/`mknod`) to `CP_WRITE_VERBS`, and their markers to the gate (escaping dests like `/etc/x` carry no path marker, so the verb marker is needed to preserve the superset invariant). |
| **P0** | **Runner value-flags let recognized RED through.** `_skip_runner_flags` lacked workspace/prefix/filter flags, so `npm exec --workspace app -- vercel deploy` / `pnpm exec --filter app vercel deploy` / `npx --workspace app vercel deploy` resolved argv0 to the flag value (`app`) instead of the command. | Added `-w`/`--workspace`/`--filter`/`--prefix`/`--cwd`/`--dir` to both `WRAPPER_VALUE_FLAGS` (npx) and `RUNNER_VALUE_FLAGS` (two-token). |
| **P1** | **Residual #3 under-bounded for JS shims.** `corepack pnpm dlx …` and `pnpx …` classified allow; the fifth-review wording had narrowed residual #3 to "unrecognized package," which these are not. | Added `corepack` + `pnpx` to `WRAPPERS`; **re-bounded residual #3 honestly** (see below) to match the plan's F13 wording (unlisted dispatcher/wrapper OR unrecognized package). |
| **P1** | **MCP read-only allowlist allowed compound mutating verbs.** `verb.startswith(...)` treated `get_or_create`, `read_and_write`, `list_and_delete` as read-only. | `mcp_decision` now vetoes FIRST on any mutating token (split on `_`/`-` AND camelCase; exact-token match so `get_updates` is NOT falsely vetoed). New `MCP_MUTATING_TOKENS` set. |

## Second self-review sweep (Codex's requested focus)

Adversarial probe of deeper variants in the four flagged areas found **three more
gaps**, all now fixed and corpus-locked:

1. **Global dispatcher flag BEFORE the runner subcommand** — `pnpm --filter app exec
   vercel deploy`, `pnpm -C dir dlx vercel deploy`, `yarn --cwd x exec wrangler
   publish`. The two-token match required adjacency. New `_runner_subcommand_end`
   skips the dispatcher's global value-flags to locate the runner verb, then
   `_skip_runner_flags` reaches the command word.
2. **More control-plane metadata verbs** — `setfacl`/`xattr`/`link`/`mkfifo`/`mknod`.
3. **MCP camelCase compound verbs** — `getOrCreate`/`readAndWrite`. The veto now
   splits camelCase (`get`/`or`/`create`) before matching.

Final probe: 0 false negatives, 0 false positives across the runner / control-plane
/ MCP surfaces.

## Residual #3 — re-bounded honestly (Codex P1 ruling)

The fifth-review/HANDOFF wording narrowed residual #3 to "unrecognized package."
That was too narrow. The correct, honest bound (matching the plan's F13 residual #3)
is: **an UNLISTED dispatcher/exec-wrapper with a literal `argv[0]`, OR a recognized
runner fetching a package whose NAME is not a recognized RED command.** The
recursion now lands on the real command word for every *listed* runner/shim
(`npx`/`bunx`/`pnpx`/`corepack` + `pnpm dlx`/`yarn dlx`/`pipx run`/`npm exec`/
`npm x`/`pnpm exec`/`yarn exec`/`bun x`, including global-flag and value-flag forms),
so all **recognized** inner RED commands deny — but set enumeration is leaky:
a wrapper/dispatcher off the maintained lists, or an unknown package name, still
passes. Keep the lists current; this is the declared honest-agent-guard bound, not a
closed gap. Residuals #1 (allowlisted-interpreter escape) and #2 (inherited-`$VAR`
redirect) are unchanged.

## Residual rulings carried from Codex

- **Unrecognized-package bound:** acceptable for `npx some-evil-pkg`-style unknown
  packages; NOT acceptable while known runner-flag forms or common shims hide a
  recognized RED command — those are now fixed.
- **Pre-existing/external git aliases:** acceptable v1 residual (documented);
  in-run alias setup is denied.

## Test-count reconciliation

| Suite | 5th review | 6th review (this pass) |
|-------|-----------|------------------------|
| classifier unit | 131/131 | **151/151** |
| gate | 26/26 | **26/26** |
| superset | 153 / 0-gaps | **177 / 0-gaps** |
| soundness | 83 RED + 34 GREEN | **107 RED + 40 GREEN** |

## Verdict

GO-WITH-RESIDUALS — the four Codex false negatives and three self-review variants
are fixed and test-locked; both invariants hold across the enlarged corpora;
residual #3 is re-bounded honestly. Recommend Codex re-confirm before activation
(the harness-contract identity assumption and the three declared residuals are
unchanged). Activation (global hook wiring + orchestrator integration) remains out
of scope.

Test totals: classifier 151/151, gate 26/26, superset 177/0-gaps, soundness 107 RED + 40 GREEN.
