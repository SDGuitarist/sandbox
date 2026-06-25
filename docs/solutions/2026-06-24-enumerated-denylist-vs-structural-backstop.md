---
title: "Enumerated Denylist vs Structural Backstop — diagnosing why a review loop won't converge"
date: 2026-06-24
type: solution
status: canonical
tags:
  - lessons-learned
  - security
  - classifier
  - red-team
  - convergence
  - review-loop
  - firebreak
summary: >
  The G1 firebreak took 9 review passes + 6 adversarial red-team rounds before a
  reviewer (Codex) stopped finding bypasses. The root cause of the extended loop was
  NOT slow reviewing — it was that the classifier was an ENUMERATED denylist
  (deny-known-bad), so every pass fixed the cited case and the next adjacent variant
  survived. The fix that finally converged was STRUCTURAL: a catch-all backstop that
  closes the whole class by construction. This doc records the diagnostic signal, the
  fix pattern, and the convergence method so the next "why won't this review loop
  end?" is caught in pass 2, not pass 9.
---

# Enumerated Denylist vs Structural Backstop

## The symptom (what the extended handoff loop looked like)

The G1 risk-tiered firebreak is a deterministic PreToolUse classifier that DENIES an
untrusted swarm worker from disabling the firebreak / exfiltrating / deploying. It
went through **nine review passes**, several of them Codex NO-GO verdicts, each
fixing the *exact* false-negative Codex cited:

- pass 5: runner recursion (`npx --call`, `pnpm dlx`…)
- pass 6: control-plane metadata verbs (`chmod`/`touch`…)
- pass 7: directory-level mutation (`rm -rf .claude/hooks`)
- pass 8: same-command variable target (`D=.claude/hooks; rm -rf $D`)
- pass 9: more assignment mechanisms (`read <<<`, `printf -v`, `${D:=…}`)

Each pass closed the cited case. Each next pass, the reviewer found *the adjacent
variant*. That is the tell.

## The diagnosis (the real lesson)

**When external review keeps finding a NEW VARIANT of the same bug class across
multiple passes, the recurrence is itself the diagnosis: the design is an ENUMERATED
DENYLIST (deny-known-bad), which can never be complete.** Patching cited cases is
playing whack-a-mole against an infinite well of syntax (every shell expansion form,
every wrapper binary, every obfuscation of a path). The loop does not converge
because the *strategy* — enumerate bad things — cannot converge.

The mistake was treating each NO-GO as "I missed one" instead of "my approach is
structurally leaky."

## The fix pattern (what actually converged)

Stop extending the denylist. Add a **STRUCTURAL BACKSTOP that closes the class by
construction**, then keep a small allowlist for the benign case. For the firebreak:

> Any **UNRECOGNIZED** verb (not a known reader / write-verb / dispatcher / wrapper /
> interpreter) that names a control-plane path **as a positional, a flag-value, or a
> `name=value` operand** fails closed. Genuine readers (`cat`, `grep`, `ls`, …) are a
> small explicit allowlist (`READ_ONLY_VERBS`).

After this, `busybox rm`, `vim -es`, `patch`, `sponge`, `gio`, and **every future
write binary** defer **without being individually modeled** — the thing the
denylist could never enumerate. The very next red-team round went dry.

General form of the pattern, reusable for any "flag/deny known-bad patterns" system
(classifiers, validators, linters, spec gates, WAF rules):

1. Identify the **protected invariant** (here: "the control plane must not be mutated
   by a worker").
2. Write a **catch-all** that defends the invariant for the UNKNOWN/unmodeled case
   (deny-by-default when the invariant is even *potentially* touched).
3. Carve a **narrow, auditable allowlist** for the benign case (readers), not a
   broad denylist for the bad case.
4. Keep the specific handlers (they give better categories/messages), but the
   backstop is the floor that makes the class complete.

## The convergence method (how to KNOW it's done, not hope)

Don't declare convergence from one more passing review. **Measure it.**

- **Parallel adversarial red-team in ROUNDS**, fix between rounds, until a round is
  dry. Slice agents by ATTACK SURFACE with complementary blind spots (variable
  expansion / path obfuscation / verb-wrapper opacity / structural-git / redirects /
  outward-MCP / backstop-defeat).
- **The find-rate sequence IS the convergence signal.** Here it was
  **21 → 15 → 12 → 9 → 1 → 0** across six rounds. A monotonic collapse to a dry round
  is the evidence; a flat or noisy rate means keep going.
- **Run a dedicated FALSE-POSITIVE lens in parallel** with the bypass hunters.
  Aggressive fail-closed fixes silently break benign cases — for an UNATTENDED system
  a wrong deny halts a real build, so over-correction is a first-class risk, not an
  afterthought. (Here: `cp ../tmpl build/`, `eslint .`, `pytest $F`, loopback `nc`,
  `find . -name '*.pyc' -delete` all had to be rescued.)
- **Hard-wire the adversarial identity into the shared probe harness.** Two agents
  nearly mis-tested as the TRUSTED identity, which would have reported everything as a
  "bypass." The harness must make testing-as-attacker the only option.
- **Give each round a growing "already-fixed, don't re-report" list** so agents spend
  budget on the frontier, not re-derivation.

## Honest residuals (a structural fix narrows residuals, rarely to zero)

The backstop closed the **control-plane** half of the "unlisted binary" leak by
construction. What remains is purely OUTWARD: an unlisted network/exfil binary
sending a NON-control-plane file out — still an enumerated set, still leaky, now
explicitly declared (analogous to the interpreter-escape residual). And a
**watch-item**: adding a binary to the recognized `DISPATCHERS` set REMOVES it from
backstop coverage, so re-run the red-team after any such change.

## Feed-Forward

- **Hardest decision:** whether to keep enumerating (cheap per-pass, never converges)
  or stop and re-architect around a backstop (one bigger change, converges). The
  recurrence pattern is what justified the re-architecture.
- **Rejected alternative:** flipping the WHOLE classifier to allow-known-good — would
  break every benign tool (cat/grep/jq/make/…) and need an impossibly large
  allowlist. The backstop is allow-known-good ONLY for the protected-resource slice,
  which is small and auditable.
- **Least confident:** the OUTWARD-channel residual (unlisted exfil binary) — the one
  place still enumerated; a capability/egress-layer control would close it but is out
  of scope for a static command classifier.

## Pointers
- Classifier: `.claude/hooks/firebreak-classify.py` (`READ_ONLY_VERBS`,
  `_arg_path_candidates`, `_cp_path_protected`, backstop tail of `bash_control_plane`).
- Convergence writeup: `docs/reviews/2026-06-24-g1-phase1-redteam-convergence.md`.
- Red-team method also captured in `~/.claude/docs/search-agent-playbook.md` (Pending).
