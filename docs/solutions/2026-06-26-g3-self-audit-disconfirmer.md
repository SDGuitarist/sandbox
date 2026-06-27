---
title: "G3 — Self-Audit Disconfirmer for Verification Diversity"
date: 2026-06-26
category: architecture
severity: P1
problem_type: verification-monoculture/perspective-blind-spot
tags:
  - verification-diversity
  - disconfirmer
  - adversarial-review
  - fail-closed-gate
  - autopilot
  - self-audit
  - cross-family-judging
  - agent-spawning
  - governance
components:
  - .claude/agents/self-audit-disconfirmer.md
  - .claude/agents/self-audit-reviewer.md
  - .claude/agents/tail-runner.md
  - .claude/skills/autopilot/SKILL.md
  - .claude/skills/verify-self-audit/SKILL.md
  - tools/verify_delegated_status.py
  - docs/spikes/2026-06-25-g3-disconfirmer-efficacy-probe.md
root_cause: >
  The autopilot's terminal verdict was a single Sonnet self-audit-reviewer
  confirming a run is shippable. A lone confirmer shares its own blind spots —
  no agent's job was to disagree — so a class of real defects (gate overrides
  against the repo's own contract, 0-conflict integration that fails at runtime,
  test oracles edited to match the implementation) could pass terminal
  verification undisputed. Governance scorecard G3 row: "monoculture in
  verification — a risk we embody."
resolution: >
  Seated a dedicated Opus disconfirmer BEFORE the Sonnet self-audit in both the
  solo and swarm tails, with the explicit mandate to prove the run is NOT
  shippable. Its grounded findings become mandatory WARNs the self-audit
  disposes (Source=disconfirmer.md#D<n>, severity verbatim); a new deterministic,
  fail-CLOSED Gate 8 (8a existence/identity/parseability + 8c exact per-finding
  bijection) enforces that none are dropped. One pass, no loop, no LLM verdict
  with binding force, no LLM in the dispose path. Efficacy was proven cross-family
  (Opus generates → Codex judges): novel-valid 4/4, overcall 0/25.
review_findings:
  p1_count: 2
  p2_count: 1
  all_fixed: true
related_runs:
  - "064"
  - "068"
  - "069"
  - "070"
governance_ref: docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md
failure_class: verification-monoculture
recurrence_risk: low
---

# G3 — Self-Audit Disconfirmer for Verification Diversity

## Problem

The autopilot's last word on whether a run ships was a single **Sonnet
`self-audit-reviewer`**. A lone confirmer is structurally blind in the same places
it is competent: no agent's *job* was to disagree, so the terminal gate could not
catch a defect the confirmer's own priors missed. The G1 review loop was field proof
of the failure class — correlated reviewers (Codex + Claude, both "find any allowed
input") ran ~17 passes and could not self-terminate
(`docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md`). The
disconfirmer antidote was already proven in research fan-outs ("opus disconfirmer >
sonnet extractors", `~/.claude/docs/search-agent-playbook.md`) but had **never been
carried into build-verification**. G3 does exactly that, for one surface.

## Solution

Five edits — four greppable-markdown, one small Python change:

1. **New agent** `.claude/agents/self-audit-disconfirmer.md` (Opus, 5 explicit args,
   `bypassPermissions`). Reads the run artifacts adversarially, writes
   `docs/reports/<run-id>/disconfirmer.md` with local `D#` findings (or the canonical
   `No disconfirmer findings.` sentinel). Advisory — no STATUS line, no verdict.
2. **Wired BEFORE the self-audit in both tail paths, same pass** (TAIL_SYNC) — solo
   `### Disconfirmer` section in `autopilot/SKILL.md`; swarm `Step 7.5` in
   `tail-runner.md`. Both `TAIL_SYNC_POINT` comments now assert the load-bearing
   *ordering*, not just presence.
3. **`self-audit-reviewer` Step 2 ingestion** — one WARN per `D#`, `Source` cell
   **exactly** `disconfirmer.md#D<n>`, severity inherited verbatim (so a HIGH finding
   DEFERRED under an A grade trips the existing Gate 7f for free). Stays `model: sonnet`.
4. **New fail-CLOSED Gate 8** in `verify-self-audit/SKILL.md` — 8a (exists + `**Run
   ID:**` identity + anchored-table parseability) and 8c (exact bijection: whole-cell
   Source equality, merged-row + phantom-citation rejection, `#D<n>` dismissal token
   with a non-digit boundary). Literal-token deterministic, mirroring Gate 7f. All gate-
   count sites bumped 9→8 (resolved a pre-existing mislabel: 7 headings were labeled 9).
5. **`verify_delegated_status.py --artifact-kind disconfirmer`** — advisory kind
   (existence + freshness + run-id only; no status), called at swarm Step 18w.

## Key design decisions

- **`disconfirmer_verdict` field CUT** (deepen-plan). It was cosmetic (DISPUTE-PASS →
  the *normal* `_WITH_DEFERRED_RISK` status) AND it put a binding LLM verdict back in
  the dispose path — a soft form of the rejected unilateral-block. The brainstorm's
  intent ("a meta-objection can't be silently flattened") is preserved by routing
  findings through the existing Gates 2/5/7f teeth. **Diversity of detection, with
  deterministic non-LLM enforcement.**
- **Before-placement is bias-correct, not just convenient.** Running the disconfirmer
  *blind to* the self-audit verdict avoids anchoring/confirmation bias — CoT does not
  undo an anchor once seen. It stays an independent reviewer.
- **Within-family is the WEAK lever.** Opus-vs-Sonnet adds role diversity (disconfirm
  vs confirm) but NOT model diversity that neutralizes self-preference bias (same
  family). So **cross-family (Codex) is a pre-registered escalation**, not an
  open-ended residual — and it is exactly what judged the efficacy probe.

## Efficacy probe (the verify-first risk — PASSED)

The feed-forward risk: does an Opus disconfirmer on the same artifacts produce
*orthogonal, valid* findings or restate the Sonnet audit? Probed on historical runs
**064 / 068 / 069 (known-miss) / 070**. Each generator read only build-time artifacts,
**hard-blocked** from that run's `self-audit.md` and post-hoc answer-key files so
novelty was real. **Opus generated; cross-family Codex judged** (Opus never scored its
own family). Result: **Novel-valid 4/4 = 1.00, Overcall 0/25 = 0.00 → PASS**, first
pass, zero brief-tuning iterations of the 3 allowed. The 069 headline known-miss held:
the disconfirmer independently re-derived the FC50 unpinned-entrypoint class the later
binding review caught. Data: `docs/spikes/2026-06-25-g3-disconfirmer-efficacy-probe.md`.

## Risk Resolution

| Flagged (brainstorm/plan Feed-Forward) | Actual outcome | Learned |
|----------------------------------------|----------------|---------|
| Opus may restate Sonnet (within-family self-preference); orthogonality unproven | Cross-family-judged probe: 25/25 valid, 14/25 novel, ≥1 novel-valid per run | Role diversity (disconfirm vs confirm) produced genuinely orthogonal findings even within one model family — the *role* lever did the work the *model* lever could not. |
| TAIL_SYNC drift (R1, top risk) — wiring one path or the wrong order | Both paths wired same-pass; ordering asserted in EARS + both comments | Asserting *ordering* (not just `grep -l` presence) is the right parity check for duplicated tails. |
| Fail-OPEN regression — a malformed/dropped finding still passes | Code review caught 8c `contains` was not bijective (D1⊂D10, merged rows) → fixed to whole-cell equality + merged/phantom rejection | A bijection gate stated as `contains` is a latent fail-open; "exact one-to-one, whole-cell, grep-safe boundary" is the durable phrasing. |
| Disposition monoculture (R5) — the lone Sonnet confirmer still *disposes* the findings | Unchanged; declared out of scope | This is the real residual G3 leaves open — detection is diversified, disposition is not. |

## Prevention / What this fixes — and what it does NOT

**Fixes:** terminal verification now has an orthogonal adversarial lens whose findings
are deterministically enforced (fail-closed), proven to surface novel-valid defects on
real historical runs.

**Durable prevention rules (carry forward):**
- **Verifier diversity is a core rule, not a footnote.** A second reviewer that shares
  the first's blind spots adds cost, not coverage. Diversify the *role* (disconfirm)
  and, when self-preference matters, the *family* (cross-family judge). Never judge a
  model's output with its own family.
- **Finite gate ≠ infinite security control.** Gate 8 enforces a *finite, enumerable*
  contract (each D# linked + disposed), so it **converges** — unlike the G1 firebreak's
  infinite adversarial target that looped ~17 passes
  (`2026-06-24-enumerated-denylist-vs-structural-backstop.md`). Frame disconfirmer
  enforcement as a finite gate; do NOT let it grow a re-run loop.
- **State bijection gates as exact one-to-one, never `contains`.** Whole-cell equality
  + grep-safe digit boundary (`#D1` ≠ `#D10`) + merged-row/phantom rejection. (Codex
  P1 in this very build.)
- **Field-validation gate with a demotion path.** Harness-green ≠ live
  (`2026-06-25-g1-firebreak-activation-arc.md`). The efficacy probe is G3's field gate;
  if a future model makes the within-family disconfirmer restate the audit, the
  pre-registered demotion is cross-family Codex as the standing verifier — not a bigger
  model, not a loop.

**Remaining risks (declared, not solved):**
- **R5 (PRIMARY RESIDUAL) — disposition monoculture.** The lone Sonnet confirmer still
  *disposes* the disconfirmer's findings; nothing checks whether a disposition was
  *correct* (only that it exists and is token-linked). Diversifying *disposition* is
  out of scope for G3.
- **Solo fail-closed is only as strong as the orchestrator reaching `/verify-self-audit`.**
  Same class as the pre-existing self-audit risk; swarm is backstopped by Step 18w
  disk-verify. Not a regression.
- **Markdown-instruction gates, not a compiled regex engine.** Gate 8 is parsed by the
  Sonnet gate-runner like Gates 1–7. Unambiguous now, but not exercised by a real tail
  run yet — a live positive-control (does a real disconfirmer worker, spawned in an
  autopilot run, actually halt on a planted self-audit violation?) is the next
  validation, per the firebreak-activation pattern.

## Compound metadata

- **Branch:** `feat/g3-verification-diversity` (pushed to origin; unmerged, mirroring
  G1's DONE-on-branch posture). 11 commits.
- **Review trail:** Plan review (Codex) GO → Work (5 checkpoints) → efficacy probe
  (Codex) PASS → code review (Codex) NO-GO (3 findings: 8c bijection, 8a parse, stale
  gate count) → fix `65954b4` → re-review GO. Handoffs in `docs/handoffs/2026-06-26-*`.
- **Governance:** closes the G3 row of
  `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md` (G2/G4/G5
  remain open).

## Feed-Forward

- **Hardest decision:** whether the meta-objection needed its own binding verdict field.
  Cut it — cosmetic AND it violated no-LLM-in-dispose-path; intent preserved via the
  deterministic Gates 2/5/7f.
- **Rejected alternatives:** a re-run/convergence loop (re-entry into the G1 trap); a
  binding/unilateral-BLOCK disconfirmer (LLM back in the dispose path); bumping the
  reviewer to Opus (scope creep); a Sonnet/Haiku disconfirmer (weaker skeptic, moot).
- **Least confident / next open risk:** the PRIMARY RESIDUAL — **disposition
  monoculture**. G3 diversified *detection*; the next governance move (a future G-gate)
  is diversifying *disposition* without re-introducing a binding LLM verdict or a loop —
  the exact tension this build was careful to avoid. Also unvalidated-live: Gate 8 has
  not yet fired in a real autopilot tail (harness-green ≠ live).
