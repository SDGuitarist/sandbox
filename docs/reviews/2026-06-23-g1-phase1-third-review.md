---
title: "G1 Phase 1 — third review: lists/pipelines, bare-host sends, dispatcher options, npx; false-negative sweep"
date: 2026-06-23
type: review
branch: feat/g1-risk-tiered-firebreak
verdict: GO-WITH-RESIDUALS (declared)
focus: "gate forwarded but classifier ALLOWED (false negatives), not only superset gaps"
---

# G1 Phase 1 — Third Review

This pass hardened the classifier per request and then did a review focused on the
direction the superset test cannot see: **commands the gate forwards but the
classifier ALLOWS** (false negatives = real bypasses).

## Hardening implemented

1. **Command lists & pipelines.** `classify_bash_command` now splits on top-level
   `;` `&&` `||` `|` `|&` `&` (quote/`$()`/backtick/backslash-aware; redirections
   like `2>&1`, `>&`, `&>`, `>|` are NOT split) and classifies EVERY simple
   command — so `base64 -d | sh`, `foo && curl evil`, `a; ./deploy` are caught.
2. **Bare-host curl/wget.** `curl_external_category` defers unless every target is
   loopback. Bare hosts (`curl evil.com`), scheme URLs, and opaque/unverifiable
   hosts (`curl $(echo evil.com)`) defer; flag VALUES (`-d @data.json`) are skipped
   so they are not mistaken for the target; `curl http://localhost/...` stays GREEN.
3. **Dispatcher global value-options.** `dispatcher_verb` skips global flags AND
   their values for gh / npm·pnpm·yarn / pip·pip3, so `gh --repo o/n api`,
   `npm --prefix /p uninstall`, `pip --cache-dir /t uninstall`, `pip3 -i <url>
   uninstall` resolve to the real verb instead of mistaking the flag value for it.
4. **npx / bunx wrapper recursion.** Added to the exec-wrapper set (and `-p/--package`
   value-flags skipped), so `npx vercel deploy` recurses to `vercel` → deny.

## False-negative sweep (the requested focus)

Ran a soundness probe: a corpus of RED commands a worker must not run, asserting
the classifier denies each. **Found 9 false negatives in 3 classes:**

- **Command-substitution outward (3)** — `echo $(curl evil)`, `` `curl evil` ``,
  `X=$(curl evil) echo`. The curl executes inside the substitution but argv0 was a
  GREEN command. **FIXED:** `$(...)`/backtick bodies are now classified; deny only
  when the inner command is RED, so `$(date)`/`$(pwd)`/`$(git rev-parse)` stay GREEN.
- **Redirect to an escaping path (4)** — `echo x > /etc/cron.d/x`, `> ~/.bashrc`,
  `cat secrets > /etc/foo`, `printf x > ~/.ssh/authorized_keys`. F9's escaping
  check was gated on the verb being a write-verb; a bare redirect is a write.
  **FIXED:** redirection targets get the control-plane + escaping check for ANY
  verb (allowing `/dev/null`+sinks, `/tmp`, worktree; opaque dests stay residual #2).
- **Quote-split command word (2)** — `c""url`, `cu''rl`. **DECLARED, not fixed**
  (see below).

Re-run after fixes: **2 false negatives remain (both quote-split); 0 false
positives.** Promoted the probe to a permanent test: `test_firebreak_soundness.py`
(37 RED denied / 13 GREEN allowed).

## Residuals after this pass

- **#1 allowlisted-interpreter escape** — unchanged.
- **#2 inherited-`$VAR` redirection** — NARROWED: `> ~/x` and `> $HOME/x` now
  resolve and are caught (via `~`/`$HOME` expansion); only a truly inherited,
  classifier-unknown `$VAR` redirect dest stays GREEN (the plan deliberately keeps
  `> "$out"` computed-worktree writes GREEN).
- **#3 unlisted dispatcher/wrapper** — npx/bunx now covered; `pnpm dlx`/`yarn dlx`/
  `pipx run`/`deno run` (two-token runners) and arbitrary custom runners remain.
- **#4 (NEW) command-word quote-splitting** — `c""url`, `cu''rl`, `s""h`. Same
  leaky-set family as the plan's F13 brace/backslash. NOT fixed: closing it needs
  BOTH a classifier dequote-argv0 step AND a gate marker (`''`/`\"\"`) that
  over-forwards every empty-string argument — coupled, and the gate marker has a
  real R6 cost. Recommend a deliberate plan decision (as with npx), not an ad-hoc
  change mid-review. Until then it is an honest declared residual.
- **Command-substitution depth** — recursion is depth-capped (>4 → fail-closed);
  bare subshell grouping `( ... )` is not split (rare; declared).

## Verdict

GO-WITH-RESIDUALS. The four requested fixes are in and test-covered; the
false-negative sweep closed 7 of 9 found bypasses and the remaining 2 are a single
declared residual class. Both invariants are now test-enforced: superset (gate ⊇
denials) and soundness (RED denied / GREEN allowed). Recommend Codex rule on the
quote-split residual #4 (and the still-open npx-family siblings) alongside the
Phase-1 review. Activation remains out of scope.

Test totals: classifier 100/100, gate 26/26, superset 112/0-gaps, soundness 37+13.
