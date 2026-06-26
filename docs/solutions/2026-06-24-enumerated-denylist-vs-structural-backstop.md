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
  end?" is caught in pass 2, not pass 9. UPDATE 2026-06-25: the structural backstop's
  own enumerated EXEMPTION (listed dispatchers) restarted the loop for 8 more passes —
  the deeper lesson, plus why this happened here and never in prior feature builds
  (finite vs infinite review target) and the pre-registered stopping discipline, are
  in the "Update (2026-06-25)" section.
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

## Update (2026-06-25): the structural backstop had an enumerated EXEMPTION that restarted the loop

The original doc declared the structural backstop "the fix that converged." It wasn't —
not fully. The backstop **exempts listed `DISPATCHERS`** (so `git add .claude/hooks`, a
benign stage, stays GREEN). That exemption is *itself an enumerated allowlist with an
open complement* — and it quietly restarted the exact loop the backstop was supposed to
end. Eight more passes followed, every one a child of that one exemption:

- F16b: listed dispatchers writing the control plane via local-output flags
  (`go build -o`, `git archive --output`, `npm pack --pack-destination`, …)
- F16c: a control-plane dest hidden inside a STRUCTURED flag value
  (`docker build -o type=local,dest=.claude/hooks`)
- then podman/nerdctl/buildah/buildctl (unlisted build tools), then
  `--cache-to`/`--metadata-file`/`--iidfile`, then `docker buildx --push` (outward via a
  flag, not the `push` verb).

**The deeper lesson: a structural backstop with an enumerated EXEMPTION is still
deny-known-bad — it just relocates the enumeration to the exemption's complement.** The
"watch-item" the original doc footnoted ("adding a binary to DISPATCHERS removes it from
backstop coverage") was not a footnote; it was the loop's next engine. A backstop only
converges if its exemptions are *also* structural (e.g. exempt the dispatcher's READ
positionals by role, not the whole binary), or if the same catch-all is applied inside
the exempted path (which is what finally closed it — `_structured_subvalues` runs in BOTH
the dispatcher handler AND the unrecognized-verb catch-all).

## Why this happened HERE and never in prior compound workflows

Every prior compound build (WRC, GigSheet, Ethics Toolkit, producer-brief) is a **feature
build against a frozen, finite spec** — a closed set of EARS criteria / routes / an auth
matrix. The reviewer is a **checker** against a fixed reference, and a checker over a
finite spec always terminates. Your spec-convergence loop terminates for the same reason:
its target (a spec's cross-section consistency) is finite and enumerable.

This task was the first time the loop's target was an **adversarial security control** —
its correctness is universally quantified ("for ALL malicious inputs, deny") over an
**infinite, unfrozen** input space (every shell command). "Found nothing new" is not a
reachable state when the domain is infinite, so the same loop that always converged
couldn't. **It was never the loop; it was the first finite→infinite target switch, and
nothing in the process noticed the category change.** A second-order instance of the
governance doc's own G3 (monoculture): Codex and Claude were *correlated* reviewers, both
running "find any allowed input," neither holding the orthogonal "is this surface even in
scope / is this convergent?" perspective.

A frozen spec is also what gives a reviewer *permission to decline* a true-but-irrelevant
finding. With no frozen spec, every valid finding was in-scope-by-construction, so nothing
could be refused, so the loop had no membrane.

## The stopping discipline (pre-register this BEFORE an adversarial review loop)

1. **Pre-register convergence:** "stop when K consecutive rounds yield zero findings that
   aren't variants of an already-handled class." Find-rate not decaying → stop signal, not
   a license for another round.
2. **Class-fix-only gate:** a finding may be closed only by a rule that provably covers
   its family. If the fix is "append to a list," that's the tell — escalate to a
   structural rule or DECLARE the residual.
3. **Honor the residual budget:** decide up front which surfaces get chased to zero and
   which are declared per the threat model. Findings on a declared surface are *logged*,
   not looped. (This control's own threat model says "honest-agent guard, declared
   residuals" — we spent P0 effort fighting a surface we'd already agreed to bound.)
4. **Hard pass cap (~3):** beyond it, continuing requires a written "why isn't this
   converging?" — which IS the diagnosis. The cap forces analysis instead of the next patch.
5. **Reviewer mandate = "find a NEW CLASS, or prove a declared residual is mis-scoped,"**
   not "find anything."

And the activation bookend: **harness-green ≠ live.** The classifier passed 265 tests
while being completely inert (unregistered hook, unwritten sentinel). "Done" must mean
"runs in reality," validated by a live/self-validating mechanism, not a green harness.

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
