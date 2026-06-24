---
title: "G1 Phase 1 — fifth review: runner recursion before activation (npx --call, runner value-flags, npm/pm exec family) + second false-negative sweep"
date: 2026-06-23
type: review
branch: feat/g1-risk-tiered-firebreak
verdict: GO-WITH-RESIDUALS (declared; residual #3 unchanged)
focus: "P0 classifier false negatives — gate-forwarded/classifier-allowed RUNNER commands"
---

# G1 Phase 1 — Fifth Review

This pass closed three runner-recursion false negatives found before activation,
added the failing inputs to the permanent corpora, reconciled the soundness test
count with the prior review docs, reran all four tests, then ran a second
adversarial false-negative sweep focused on gate-forwarded / classifier-allowed
runner commands.

## False negatives fixed

All three let a worker hide a **recognized** inner RED command behind a package
runner so it classified GREEN (the gate forwarded it, but the classifier waved it
through — the security-critical "gate-forwards-but-classifier-allows" direction):

1. **`npx --call` / `-c` command-string flag.** `npx` recursed as an exec-wrapper,
   but `npx --call 'vercel deploy'` (and the `=`-joined `--call='curl …'`) put the
   real command in a STRING flag the resolver skipped, landing argv0 on the quoted
   string. `extract_nested_commands` only recognized bare `-c`. **Fix:** it now also
   recurses `--call`, plus the `=`-joined `--call=<cmd>` / `-c=<cmd>` forms — like
   `sh -c '<cmd>'`. (`npx -c '<cmd>'` already worked; `--call` was the gap.)

2. **Runner value-flags before the real command word.** The two-token runners
   (`pnpm dlx` / `yarn dlx` / `pipx run`) recursed by skipping exactly two tokens,
   so `pnpm dlx --package vercel vercel deploy` / `pipx run --spec ./evil cmd`
   resolved argv0 to the flag, not the command. **Fix:** a new `_skip_runner_flags`
   skips the runner's leading option flags (and the values of value-taking ones:
   `-p`/`--package`/`--spec`/`--python`/`--pip-args`/`-i`/`--index-url`/`--registry`/
   `--node-range`) plus a `--` end-of-options separator, so the resolver lands on the
   real command word. Both space-separated and `=`-joined flag values are handled.

3. **`npm exec` / `npm x` / package-manager `exec`.** `npm`/`pnpm`/`yarn` are
   dispatchers, so `npm exec -- vercel deploy` read the verb as `exec` and never saw
   the inner `vercel deploy`. **Fix:** the `exec` family is added to
   `TWO_TOKEN_RUNNERS` — `("npm","exec")`, `("npm","x")`, `("pnpm","exec")`,
   `("yarn","exec")`, `("bun","x")` — so it recurses to the inner command exactly
   like `npx`. The `--` separator and value-flags are handled by `_skip_runner_flags`.

## Corpora updated

The 15 failing inputs were added as applicable:

- **soundness** (`test_firebreak_soundness.py`): +15 RED (the runner recursion
  block) and +8 GREEN over-defer guards (`npm exec -- jest`, `npm x tsc`,
  `pnpm exec prettier`, `yarn exec tsc`, `pnpm dlx --package typescript tsc`,
  `pipx run --spec build pytest`, `npx --call 'pytest -q'`, `bun x tsc`).
- **superset** (`test_firebreak_superset.py`): +13 RED runner variants to the Bash
  corpus (the gate must forward every one — verified, 0 gaps).
- **classifier unit** (`test_firebreak_classify.py`): +13 cases (8 RED runner
  variants + GREEN guards: `npx --call pytest`, `pnpm dlx --package typescript tsc`,
  `npm exec -- jest`).

## Test-count reconciliation

The fourth-review doc and HANDOFF reported soundness as **70 RED + 26 GREEN**. The
live corpus at the start of this pass was actually **68 RED + 26 GREEN** (the "70"
was an overcount by 2). This review corrects that and records the new totals.

| Suite | 4th review (as reported) | 4th review (actual) | 5th review (this pass) |
|-------|--------------------------|---------------------|------------------------|
| classifier unit | 119/119 | 119/119 | **131/131** |
| gate | 26/26 | 26/26 | **26/26** |
| superset | 140 / 0-gaps | 140 / 0-gaps | **153 / 0-gaps** |
| soundness | 70 RED + 26 GREEN | **68** RED + 26 GREEN | **83 RED + 34 GREEN** |

## Second false-negative sweep (the requested focus)

An adversarial probe of **14 RED runner variants** + **5 GREEN** beyond the corpus,
all targeting the gate-forwarded / classifier-allowed runner surface:

- `=`-joined value flags (`pipx run --spec=./evil …`, `npm exec --package=foo -- …`)
- wrapper **then** runner (`sudo npm exec -- …`, `env FOO=1 npx --call …`,
  `time npm exec -- …`)
- `npm exec -c '<cmd>'` command string
- **opaque** inner argv0 (`npm exec -- $(printf vercel) deploy` → caught by F13)
- short valueless flags (`yarn dlx -q wrangler publish`)
- inner `gh api` / `git push` / `git push --force` behind the runner
- `bun x -- …`, and **nested runners** (`npm exec -- npx vercel deploy`)

Result: **0 false negatives, 0 false positives** — every RED variant denied AND
forwarded by the gate; every GREEN (`pipx run --spec=build pytest`,
`npm exec --package=typescript -- tsc`, `sudo npm exec -- jest`,
`npm exec -- npx eslint .`, `yarn dlx -q tsc --noEmit`) stayed GREEN. Convergence
on the runner-recursion class.

## Residuals after this pass

Unchanged from the fourth review — no new class opened:

- **#1 allowlisted-interpreter escape** — unchanged (bounds guarantees to direct
  worker tool calls).
- **#2 inherited-`$VAR` redirection** — unchanged (`~`/`$HOME` resolved & caught;
  a classifier-unknown inherited `$VAR` redirect dest stays GREEN by design).
- **#3 runner/dispatcher + UNRECOGNIZED inner** — the recursion now lands on the
  real command word for `npx`/`bunx`/`pnpm dlx`/`yarn dlx`/`pipx run`/`npm exec`/
  `npm x`/`pnpm exec`/`yarn exec`/`bun x`, so all **recognized** inner RED commands
  deny; but a runner fetching a package whose NAME is not a recognized RED command
  (`npx some-evil-pkg`, `npm exec -- some-evil-pkg`) still stays GREEN — we cannot
  know an arbitrary package is malicious without running it. This is the honest
  leaky-set bound, not a closed gap.
  > **Re-bounded in the 6th review (2026-06-24):** this wording was too narrow.
  > Codex found `corepack`/`pnpx` shims (now listed) and runner value-flag forms
  > slipping through. The honest bound is **an UNLISTED dispatcher/exec-wrapper
  > with a literal `argv[0]`, OR an unrecognized package name** — matching the
  > plan's F13 residual #3. See `docs/reviews/2026-06-24-g1-phase1-sixth-review.md`.
- **Command-substitution / nesting depth** — capped at >4 → fail-closed.

## Verdict

GO-WITH-RESIDUALS. The three runner false negatives are fixed and test-locked; the
second sweep found no further runner false negatives or false positives; both
invariants hold (superset: gate ⊇ denials; soundness: RED denied / GREEN allowed)
across the enlarged corpora. Activation (wiring the gate into global settings +
orchestrator integration) remains out of scope.

Test totals: classifier 131/131, gate 26/26, superset 153/0-gaps, soundness 83 RED + 34 GREEN.
