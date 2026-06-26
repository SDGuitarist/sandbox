---
title: "feat: G3 — Self-Audit Disconfirmer for Verification Diversity"
type: feat
status: active
date: 2026-06-25
branch: feat/g3-verification-diversity
origin: docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md
governance_ref: docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md
feed_forward:
  risk: "Does an Opus disconfirmer reading the SAME run artifacts produce ORTHOGONAL findings, or just restate the Sonnet confirmer's concerns in stronger words? (carried from brainstorm 'least confident')"
  verify_first: true
---

# feat: G3 — Self-Audit Disconfirmer for Verification Diversity ✨

## Overview

Seat a **dedicated disconfirmer** (an Opus agent with an adversarial brief) at the autopilot's
**terminal verification surface** — immediately *before* the `self-audit-reviewer` step — to break
the **perspective monoculture** the governance scorecard marks ❌ "a risk we embody"
(`docs/governance/2026-06-21-...`, G3 row). The disconfirmer's job is to *prove the run is NOT
shippable*; its findings flow into the **existing WARN-disposition machinery** as mandatory WARNs the
self-audit must dispose, and a **new deterministic Gate 8** in `/verify-self-audit` enforces that none
are silently dropped. One pass, no loop, no LLM in the dispose path.

**This plan carries forward every decision from** `docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md`.

## Problem Statement / Motivation

Today the terminal verdict is a **single Sonnet `self-audit-reviewer`** confirming a run is shippable.
A lone confirmer shares its own blind spots — there is no agent whose *job is to disagree*. The G1
review loop was field proof of the failure class: correlated reviewers (Codex + Claude, both "find any
allowed input") ran ~17 passes and could not self-terminate because neither held the orthogonal lens
(`docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md`, Update 2026-06-25, on the
`feat/g1-risk-tiered-firebreak` branch). The disconfirmer antidote is **proven in research fan-outs**
(`~/.claude/docs/search-agent-playbook.md`: SL5/SL8; "opus disconfirmer > sonnet extractors"; "Haiku
unreliable for adjudication") but has **never been carried into build-verification**. G3 does exactly
that, for one surface.

## Proposed Solution

Add four artifacts/edits, all greppable-markdown (there is **no JSON schema** — the gates validate
prose markers):

1. **New agent** `.claude/agents/self-audit-disconfirmer.md` (`model: opus`). Reads the run artifacts
   adversarially, writes `docs/reports/<run-id>/disconfirmer.md` with a `**Disconfirmer Verdict:**`
   (`CONCUR` | `DISPUTE-PASS`) and a findings table keyed with *local* IDs (`D1`, `D2`, …).
2. **Wire it BEFORE the self-audit** in both the solo path (`.claude/skills/autopilot/SKILL.md`,
   between "Verify BUILD_TRACKING" and "Self-Audit", ~line 1153) and the swarm path
   (`.claude/agents/tail-runner.md`, between Step 7 and Step 8). The two are kept in sync by the
   existing `TAIL_SYNC_POINT` contract (`SKILL.md` ~992–999) — **both must be edited.**
3. **Extend `self-audit-reviewer.md`**: it must (a) ingest each disconfirmer `D#` finding as a WARN row
   (assign the canonical `<run-id>-W<N>` key — the disconfirmer never assigns global keys, avoiding
   FC34 races), dispose it, and cite `disconfirmer.md` as the Source; (b) record a
   `**Disconfirmer Verdict:**` line; and (c) if the verdict is `DISPUTE-PASS`, it may **not** claim a
   clean `PIPELINE_PASS` — it must be `PIPELINE_PASS_WITH_DEFERRED_RISK` (or `PIPELINE_FAIL`) and carry
   the dispute in `## Unresolved Risk`. Add the field to its report template (Step 4) and its Step 6
   self-validation list.
4. **New Gate 8** in `.claude/skills/verify-self-audit/SKILL.md` (after 7f, before `## Output`; bump
   the "Run all N checks" preamble at ~line 26 and the success line at ~line 241). Gate 8 is
   **deterministic and fail-CLOSED**.

### Why this approach (carried from brainstorm)

- **Scope = self-audit only** (not the `/workflows:review` mix, not the spec gates). Highest-leverage
  single surface; bounded "done." *(see brainstorm: Decision 1)*
- **Opus disconfirmer.** Because the confirmer is already **Sonnet**, an Opus disconfirmer adds *both*
  role diversity (disconfirm vs confirm) **and** model diversity (Opus vs Sonnet) — the playbook's
  "opus disconfirmer > sonnet extractors" realized. Both standard models are Max-covered (no Sonnet-1M
  usage credits). Cross-**family** (Codex) diversity is a declared plan-time residual, not the
  unattended tail. *(see brainstorm: Decision 2)*
- **Option-A adjudication.** Disconfirmer runs **first/independent** (confirmer can't pre-bias it) →
  findings become mandatory WARNs the self-audit disposes → deterministic Gate 8 enforces every finding
  is disposed and every *dismissal* is justified (mirroring Gate 7f). No new blocking path, no arbiter,
  no re-run loop. *(see brainstorm: Decision 3)*
- **Determinism boundary held.** The disconfirmer is advisory (an LLM finding); all enforcement lives
  in deterministic Gate 8. No LLM in the dispose path. *(see brainstorm: Decision 4)*

## Technical Approach

### Architecture (one pass, before the audit)

```
... Verify BUILD_TRACKING.md (existing gate)
      │
      ▼
[NEW] self-audit-disconfirmer  (model: opus, adversarial brief)
      │   reads run artifacts → writes docs/reports/<run-id>/disconfirmer.md
      │   { Disconfirmer Verdict: CONCUR|DISPUTE-PASS ; findings D1..Dn }
      ▼
self-audit-reviewer (model: sonnet, existing)
      │   ingests each D# as a WARN row (key <run-id>-W<N>, Source=disconfirmer.md), disposes it;
      │   records Disconfirmer Verdict; DISPUTE-PASS ⟹ not clean PIPELINE_PASS
      ▼
/verify-self-audit  (existing Gates 1–7 + [NEW] Gate 8, deterministic, fail-CLOSED)
      ▼
... Done   (swarm: Step 18w disk-verify also confirms disconfirmer.md freshness)
```

### Disconfirmer agent brief (the orthogonal lens — this is the load-bearing part)

The brief must make the disconfirmer **structurally orthogonal**, not a second confirmer:
- Mandate: *"Assume this run should NOT ship. Find the strongest reasons it is not shippable that a
  competent-but-bounded confirming reviewer would miss."* Target the classes the playbook says
  confirmers miss: scope/convergence errors, silent gaps, claims unbacked by on-disk artifacts.
- **Ground-truth bias** (playbook "Ground-truth verifier"): open the actual on-disk artifacts and check
  claims against them, never against summaries/STATUS lines.
- **Current-run scope only** (autonomy-hardening rule): do NOT surface pre-existing backlog/HANDOFF
  "Deferred Items (from prior work)". A clean run must pass even with a large backlog.
- **Reviewer-mandate stopping rule** (enumerated-denylist lesson): findings must name a *class* of
  problem ("X category of WARN is missing/mis-disposed"), not whack-a-mole line items; the disconfirmer
  runs **once** — it is not a loop.
- Output contract: `**Disconfirmer Verdict:** CONCUR` (no blocking findings) or `DISPUTE-PASS`, plus a
  table `| D# | Category | Why this threatens shippability | Severity (LOW/MED/HIGH) |`. Header carries
  `Run ID: <run-id>` and a timestamp (FC52). Tools: `Read, Write, Grep, Glob`.

### Gate 8 — deterministic, fail-CLOSED

Implemented as markdown-instruction checks (consistent with Gates 1–7), reading via Read/Grep/Glob:
- **8a — Exists & identity (fail-closed):** `docs/reports/<run-id>/disconfirmer.md` exists (Glob) and
  its header contains the exact `Run ID: <run-id>`. **Missing/mismatched ⟹ FAIL** (never pass — the
  skeptic is mandatory). *(FC10 fail-closed; FC52 identity)*
- **8b — Verdict present:** contains `**Disconfirmer Verdict:**` with exactly `CONCUR` or `DISPUTE-PASS`.
- **8c — Every finding disposed:** every `D#` row in `disconfirmer.md` maps to a WARN row in
  `self-audit.md` whose `Source` cites `disconfirmer.md`, with a valid Disposition and non-empty
  Rationale. Any finding the audit *dismisses* (disposes as non-blocking) requires an explicit
  justification string in the Rationale (mirrors 7f's "can't silently drop the skeptic").
- **8d — Verdict honored:** if Verdict is `DISPUTE-PASS`, the self-audit `Final Status` is **not**
  `PIPELINE_PASS` (must be `_WITH_DEFERRED_RISK` or `_FAIL`) **and** the dispute appears in
  `## Unresolved Risk`.
- **Swarm freshness:** extend `SKILL.md` Step 18w to also disk-verify `disconfirmer.md`
  (`verify_delegated_status.py --artifact docs/reports/<run-id>/disconfirmer.md`-style mtime ≥
  run_start_ts + run-id match), matching how `self-audit.md` is disk-verified. *(harness-green ≠ live)*

### System-Wide Impact

- **Interaction graph:** new agent spawn sits inside the Shared Tail; it adds one Opus pass before the
  existing Sonnet self-audit. Solo runs it inline; swarm runs it inside `tail-runner` (which `SKILL.md`
  Step 18w disk-verifies). No other callbacks fire.
- **Error propagation:** disconfirmer crash/empty output → Gate 8a FAIL → run fails (fail-closed),
  surfaced exactly like a self-audit FAIL. No silent `PIPELINE_PASS`.
- **State lifecycle:** one new artifact per run (`disconfirmer.md`), one per run-id (FC5/FC34 — no
  parallel-run collision because it is namespaced under `docs/reports/<run-id>/`).
- **API-surface parity:** the solo and swarm paths are the parity surface; `TAIL_SYNC_POINT` forces both
  edits. Missing one = swarm and solo diverge (the single biggest implementation risk — see Risks).
- **Integration scenarios:** (a) CONCUR happy path; (b) DISPUTE-PASS forces non-clean status; (c)
  missing artifact fails closed; (d) dismissed finding without justification fails 8c; (e) solo and
  swarm both gated.

## What Must NOT Change (invariants)

- **Gates 1–7 of `/verify-self-audit` and their semantics** — Gate 8 is additive only.
- **The `self-audit-reviewer` model stays Sonnet.** G3 does not bump it to Opus (declared latent
  finding, out of scope — would breach the pre-registered "done"). *(see brainstorm: Latent finding)*
- **No LLM enters the deterministic dispose path.** Gate 8 is markdown-deterministic; the disconfirmer
  is advisory only.
- **No re-run / convergence loop.** Disconfirmer runs exactly once per run. *(rejecting the loop the
  learnings research proposed — it reintroduces the G1 convergence trap.)*
- **Current-run WARN scoping** — the disconfirmer must not downgrade a clean run with pre-existing
  backlog.
- **Existing WARN-key convention** (`<run-id>-W<N>`, sequential, no gaps) and disposition enum — verify
  the exact enum strings against `.claude/agents/self-audit-reviewer.md` during implementation
  (research reported `ACCEPTED/PROMOTED/DEFERRED`; confirm before coding).

## Acceptance Tests (EARS)

Format: `WHEN [condition] THE SYSTEM SHALL [behavior]`.

### Happy path
- WHEN a run reaches the tail and the disconfirmer finds no blocking issues THE SYSTEM SHALL write
  `docs/reports/<run-id>/disconfirmer.md` with `**Disconfirmer Verdict:** CONCUR` and an empty/"none"
  findings table, and `/verify-self-audit` Gate 8 SHALL pass.
  - Verify: `grep -c 'Disconfirmer Verdict:\*\* CONCUR' docs/reports/<run-id>/disconfirmer.md` → `1`
- WHEN the disconfirmer raises findings `D1..Dn` THE SYSTEM SHALL cause the self-audit report to contain
  one WARN row per `D#` (Source = `disconfirmer.md`), each disposed with a non-empty rationale.
  - Verify: count of `disconfirmer.md`-sourced WARN rows in `self-audit.md` == count of `D#` rows in
    `disconfirmer.md`, AND every such WARN row has a non-empty Disposition (∈ enum) and a non-empty
    Rationale cell (no `|  |` empties in those two columns).
- WHEN both solo and swarm tails run THE SYSTEM SHALL invoke the disconfirmer before the self-audit in
  each path.
  - Verify: `grep -l 'self-audit-disconfirmer' .claude/skills/autopilot/SKILL.md .claude/agents/tail-runner.md` → both files.

### Error cases
- WHEN `disconfirmer.md` is missing or its `Run ID` does not match the run THE SYSTEM SHALL FAIL
  `/verify-self-audit` at Gate 8a (fail-closed).
  - Verify: with the file absent, `/verify-self-audit <run-id> docs/reports/<run-id>/` returns
    `STATUS: FAIL`.
- WHEN the Verdict is `DISPUTE-PASS` but the self-audit `Final Status` is `PIPELINE_PASS` THE SYSTEM
  SHALL FAIL Gate 8d.
  - Verify: a fixture with `DISPUTE-PASS` + `PIPELINE_PASS` → `/verify-self-audit` returns `STATUS: FAIL`.
- WHEN a disconfirmer finding is dismissed without an explicit justification in the WARN rationale THE
  SYSTEM SHALL FAIL Gate 8c.
  - Verify: a fixture with an undisposed/justification-less `D#` → `STATUS: FAIL`.
- WHEN the disconfirmer (Opus) agent is unavailable THE SYSTEM SHALL fail the run, NOT fall back to a
  pass. *(billing note: the agent pins standard `opus` via frontmatter — Max-covered, never Sonnet-1M.)*

### Verification commands (run against a fixture run-id, copy reports to /tmp first — never mutate real runs)
- `grep -n 'Gate 8' .claude/skills/verify-self-audit/SKILL.md` — Gate 8 present
- `grep -n 'self-audit-disconfirmer' .claude/skills/autopilot/SKILL.md .claude/agents/tail-runner.md` — both wired
- `grep -n 'model: opus' .claude/agents/self-audit-disconfirmer.md` — Opus pinned, Max-covered
- `head -8 .claude/agents/self-audit-reviewer.md` — confirm it still says `model: sonnet` (invariant)

## Success Metrics

- First real swarm run (env permitting) produces a fresh `disconfirmer.md`, Gate 8 passes/fails
  deterministically, and the run is **not** ungoverned. (Failure mode = a halted run, not a silent pass.)
- **Efficacy probe (the feed-forward risk):** on ≥1 historical `docs/reports/*/self-audit.md`, the
  disconfirmer surfaces ≥1 finding the original Sonnet audit did not — *evidence of orthogonality, not
  restatement.* If it only restates, the brief needs sharpening (this is the verify-first item).

## Dependencies & Risks / Mitigation

- **R1 — TAIL_SYNC drift (highest):** editing only one of solo/swarm. *Mitigation:* the EARS "both
  files" check; treat as a P1 in review.
- **R2 — Non-orthogonality (the feed-forward risk):** Opus disconfirmer restates Sonnet's concerns.
  *Mitigation:* the historical-report efficacy probe before declaring done; sharpen the adversarial
  brief; cross-family (Codex) is the declared residual if role+model diversity proves insufficient.
- **R3 — Fail-open regression:** a future edit makes a missing artifact pass. *Mitigation:* Gate 8a is
  explicitly fail-closed + an EARS error-case test pins it.
- **R4 — Latency/token cost:** a second tail pass (Opus) on every unattended run. *Mitigation:* accepted;
  one pass only, no loop; note in compound doc for cost tracking.
- **R5 — Sequencing limitation (declared residual):** running *before* the audit means the disconfirmer
  critiques the **run**, not the audit's **disposition judgment**. Catching audit-judgment errors would
  need an after-pass (a loop) — explicitly rejected. Declared residual.

## Pre-registered "Done" (stopping discipline — from the G1 retro)

Done =
1. `self-audit-disconfirmer.md` agent exists (`model: opus`) and runs before the self-audit in **both**
   paths;
2. its findings are ingested as WARNs the self-audit disposes; the `disconfirmer_verdict` is recorded;
3. `/verify-self-audit` Gate 8 (8a–8d) enforces existence (fail-closed), disposition, justified
   dismissals, and verdict-honoring;
4. one end-to-end pass (real or fixture) shows the wiring works AND the efficacy probe shows ≥1
   orthogonal finding on a historical report.

**Tell-to-stop:** if a change "adds another reviewer" without changing the *perspective distribution*,
adds a re-run loop, or creeps to the review mix / spec gates — stop and re-scope. Hard pass-cap on any
brief-tuning iteration: **3**; beyond it, write a "why isn't it orthogonal?" diagnosis instead of
another tweak.

## File-by-file change list (pseudo)

- `.claude/agents/self-audit-disconfirmer.md` — NEW. Frontmatter `model: opus`, `tools: Read, Write,
  Grep, Glob`; adversarial brief + output contract above.
- `.claude/skills/autopilot/SKILL.md` — insert disconfirmer block before `### Self-Audit` (~1153);
  extend Step 18w disk-verify to include `disconfirmer.md`.
- `.claude/agents/tail-runner.md` — insert disconfirmer step between Step 7 and Step 8 (mirror; respect
  `TAIL_SYNC_POINT`).
- `.claude/agents/self-audit-reviewer.md` — Step 4 report template gains `**Disconfirmer Verdict:**` +
  the "ingest each D# as a WARN" instruction; Step 6 self-validation gains the verdict/ingest checks.
- `.claude/skills/verify-self-audit/SKILL.md` — add `### Gate 8` (8a–8d); bump check-count preamble
  (~26) and success line (~241).
- (test fixtures) `docs/reports/<fixture>/…` copies in `/tmp` for the EARS error-case checks — never
  mutate real run reports.

## Sources & References

### Origin
- **Brainstorm:** [docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md](docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md)
  — carried decisions: scope=self-audit-only; Opus disconfirmer (role+model diversity, confirmer is
  Sonnet); Option-A adjudication (mandatory WARNs + deterministic teeth, no loop); dedicated
  `disconfirmer_verdict` field.

### Internal references (verified during planning)
- `.claude/agents/self-audit-reviewer.md` — `model: sonnet`; 9-section report; WARN table columns; keys
  `<run-id>-W<N>`; pipeline statuses.
- `.claude/skills/verify-self-audit/SKILL.md` — Gates 1–7 (7a–7f), markdown-instruction, no schema file;
  Gate 7f key-citation mechanics (the pattern Gate 8 mirrors).
- `.claude/skills/autopilot/SKILL.md` — Shared Tail ordering; solo spawn (~1154) vs swarm Step 17w/18w
  disk-verify (`verify_delegated_status.py`); `TAIL_SYNC_POINT` (~992–999).
- `.claude/agents/tail-runner.md` — swarm tail Steps 7–10; self-audit spawn `subagent_type:
  "self-audit-reviewer"`, `mode: "bypassPermissions"`.
- `docs/reports/070/self-audit.md` — ground-truth sample (`PIPELINE_PASS_WITH_DEFERRED_RISK`, keys
  070-W1..W4, Overall 4.7/5.0 (A); a real Gate-7f-by-exemption).
- `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md` — G3 row (monoculture).

### Prior-art learnings (gotchas designed around)
- `docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md` (g1 branch) — field proof +
  stopping discipline; *don't* enumerate disconfirmer exclusions; reviewer mandate = find a class.
- `docs/solutions/2026-06-25-g1-firebreak-activation-arc.md` (g1 branch) — gate-wiring pattern;
  positive-control probe; **harness-green ≠ live**; artifact-based (disk) authority.
- `docs/solutions/2026-04-30-spec-convergence-loop.md` — model-diversity-as-blind-spot-coverage pattern.
- `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md` — WARN current-run scoping.
- `~/.claude/docs/agent-pitfalls.md` — FC10 (fail-closed), FC34/FC5 (one-per-run-id), FC50 (pin the
  spawn entrypoint), FC52 (artifact identity/freshness), FC11 (propagate the disconfirmer pattern in
  compound).
- `~/.claude/docs/search-agent-playbook.md` — Disconfirmer + Ground-truth-verifier roles; "opus
  disconfirmer > sonnet extractors"; Haiku unreliable for adjudication.

## Feed-Forward

- **Hardest decision:** Sequencing the disconfirmer *before* the audit (independent, no loop) vs *after*
  (can critique the audit's judgment, but needs a loop). Chose before — it preserves Option A's
  one-pass/no-new-blocking-path discipline and the brainstorm's independence requirement; the cost
  (can't critique disposition judgment) is a declared residual (R5).
- **Rejected alternatives:** (a) the learnings research's **re-run loop** — rejected as a re-entry into
  the G1 convergence trap; (b) a unilateral-BLOCK disconfirmer — rejected (puts an LLM back in the abort
  path G1 removed); Gate 8's deterministic must-dispose gives teeth instead; (c) bumping the
  self-audit-reviewer to Opus — rejected as scope creep (latent finding).
- **Least confident (verify first):** Whether an Opus disconfirmer on the *same* artifacts yields
  *orthogonal* findings or restates the Sonnet audit. The Success-Metrics efficacy probe (≥1 historical
  report) is the gate on this before declaring done; cross-family (Codex) is the fallback residual.

## Codex Handoff Prompt (Plan Review — paste into a fresh Codex context)

```
You are reviewing an IMPLEMENTATION PLAN (not code) for a fresh, skeptical second opinion before any
code is written. Repo: ~/Projects/sandbox, branch feat/g3-verification-diversity.

Plan: docs/plans/2026-06-25-feat-g3-self-audit-disconfirmer-plan.md
Origin brainstorm: docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md

What it does: adds an Opus "disconfirmer" agent that runs BEFORE the Sonnet self-audit-reviewer in the
autopilot tail; its findings become mandatory WARNs the self-audit disposes; a new deterministic
fail-CLOSED Gate 8 in /verify-self-audit enforces disposition + verdict-honoring. One pass, no loop, no
LLM in the dispose path. Scope is the self-audit surface only.

Ground the review in these verified facts: /verify-self-audit is pure markdown-instruction gates (no
script/schema); WARN keys are <run-id>-W<N>; the solo path (SKILL.md ~1153) and swarm path
(tail-runner.md Step 7→8) are kept in sync by TAIL_SYNC_POINT and BOTH must be edited; self-audit-reviewer
stays model: sonnet (invariant).

Look hardest for, and return as P0/P1/P2 with file:line and a concrete fix:
1. TAIL_SYNC drift — any way solo and swarm diverge.
2. Fail-OPEN holes — any path where a missing/malformed disconfirmer.md still lets the run PASS.
3. Determinism-boundary leaks — any LLM judgment that ends up in the dispose path.
4. Sequencing soundness — does "before the audit" actually deliver the meta-objection (DISPUTE-PASS)
   teeth Gate 8d claims, given the audit runs after?
5. Cross-section contradictions between this plan, the brainstorm, and the verified self-audit contract
   (e.g. the disposition enum: plan assumes ACCEPTED/PROMOTED/DEFERRED — confirm against
   .claude/agents/self-audit-reviewer.md).
6. Convergence/stopping-discipline gaps — anything that could reintroduce a review loop.

Return: a prioritized findings list + a GO / NO-GO for proceeding to /workflows:work.
```
