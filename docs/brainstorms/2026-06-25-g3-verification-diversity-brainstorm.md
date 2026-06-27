---
title: "G3 — Name & Mitigate Monoculture in Build-Verification"
date: 2026-06-25
type: brainstorm
status: complete
phase: brainstorm
branch: feat/g3-verification-diversity
governance_ref: docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md
field_proof: docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md  # on feat/g1-risk-tiered-firebreak branch
antidote_ref: ~/.claude/docs/search-agent-playbook.md  # Disconfirmer role; "opus disconfirmer > sonnet extractors"; Haiku unreliable for adjudication
tags: [governance, agent-security, autopilot, monoculture, verification, disconfirmer]
---

# G3 — Name & Mitigate Monoculture in Build-Verification

## What We're Building

A **dedicated disconfirmer** seated at the autopilot's **terminal verification surface** — the
`self-audit-reviewer` step — to break the algorithmic monoculture that the governance scorecard
marks ❌ *"a risk we embody"* (`docs/governance/2026-06-21-...`, G3 row): *all workers = Opus,
near-identical briefs, so they share blind spots and review can't catch what all reviewers miss.*
At the self-audit surface specifically, the monoculture being fixed is **perspective monoculture** —
a *lone confirmer* (one agent, one confirming lens) — independent of model. (As verified below, the
confirmer is already a different *model* from the workers; the missing axis here is a second *role*.)

The disconfirmer is an **Opus agent with an orthogonal brief** — its job is to *prove the run is NOT
shippable / find what the self-audit is structurally blind to*, the opposite of the confirming
self-audit. Its findings flow into the **existing WARN-disposition machinery** as mandatory WARNs
the self-audit must dispose, and the **existing deterministic `/verify-self-audit` gate** enforces
that none are silently dropped.

> **Verified facts (2026-06-25), correcting an initial premise.** The build workers run on
> **Opus** (`SKILL` Step 10w). The terminal `self-audit-reviewer` runs on **Sonnet** (agent
> frontmatter; the SKILL invocation does not override it) — *not* Opus as first assumed. So the
> terminal verdict today is a **single Sonnet agent auditing Opus work**. `/verify-self-audit` is
> **project-local** (`.claude/skills/verify-self-audit`), so the schema change below stays in-repo
> without breaching CLAUDE.md's control-surface boundary. These facts strengthen the design (see
> Decision 2) rather than change the three core decisions.

**Scope is deliberately narrow (one surface):** the self-audit terminal verdict only. NOT the
`/workflows:review` agent mix, NOT the deterministic spec gates. This is the highest-leverage
single surface (it's the terminal verdict that writes `docs/reports/<run-id>/self-audit.md`) and
gives a bounded, pre-registered "done."

## Why This Approach

**The field proof (why now).** The G1 review loop ran ~17 passes and could not self-terminate
because Codex and Claude were *functionally correlated reviewers* — both running "find any allowed
input," neither holding the orthogonal "is this surface even in scope / is this convergent?" lens
(`docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md`, Update 2026-06-25). G3
is the systemic fix for that class: a reviewer whose *job is to disagree*.

**The antidote is already proven — but only in RESEARCH fan-outs** (`search-agent-playbook.md`):
a dedicated **Disconfirmer/adversary** (≥1 agent told to disprove/attack, not confirm) catches what
confirmers structurally miss (SL5/SL8). G3's whole job is to **carry that into build-verification.**

**The central tension — and why it dissolves at THIS surface.** In general the monoculture gap argues
for a *different model*, while the playbook's adjudication lesson cuts the other way: **"opus
disconfirmer > sonnet extractors"** and **"Haiku unreliable for adjudication"** — the skeptic role
wants the *strong* model, so diversity-by-downgrade fights adjudication quality. At the self-audit
surface this tension **resolves cleanly**: the confirmer is already **Sonnet**, so adding an **Opus
disconfirmer** delivers *both* axes at once — role diversity (disconfirm vs confirm) **and** model
diversity (Opus vs Sonnet), while *upgrading* the skeptic to the strong model the playbook
recommends. It is literally *"opus disconfirmer > sonnet extractors"* realized. Both standard models
are Max-covered (no Sonnet-1M usage credits). True cross-**family** diversity (Codex) is recorded as
a residual for the *plan-time* spec-convergence loop, not the unattended tail.

**Latent finding (noted, not in scope).** The terminal verdict currently runs on a *weaker* model
(Sonnet) than the Opus workers it audits. The Opus disconfirmer covers the "strong skeptic" need
**without** touching the existing confirmer — so G3 does not bump the `self-audit-reviewer` itself
(that would breach the pre-registered "done"). Flagged here for a possible future item.

**It fits the existing architecture by construction.** Today's self-audit is already a clean
two-layer split: **LLM `self-audit-reviewer` (advisory — makes WARN dispositions)** →
**`/verify-self-audit` 9 deterministic hard gates (the dispose path; Gate 7f independently checks
DEFERRED+HIGH WARNs).** G3 adds LLM diversity to the **advisory layer only**, never to the 9 gates —
so the "no LLM in deterministic gates" constraint is satisfied automatically.

## Key Decisions

1. **Scope = self-audit only** (narrowest of three surfaces). Review mix + spec gates explicitly
   deferred. YAGNI + bounded "done."
2. **Diversity axis = Hybrid: Opus disconfirmer now, Codex cross-family flagged later.**
   Max-covered (standard Opus 4.8 + standard Sonnet 4.6; no Sonnet-1M usage credits), unattended-safe.
   Because the existing confirmer is **Sonnet**, the Opus disconfirmer adds **both** role *and* model
   diversity at this surface — *not* "still all-Opus" as first written. Codex = the cross-**family**
   residual for plan-time, not the unattended tail.
3. **Adjudication = Mandatory WARNs + deterministic teeth (Option A).** Disconfirmer runs **first**,
   independent, on its **own artifact** (so the confirmer can't pre-bias it). The `self-audit-reviewer`
   must ingest each finding as a WARN and dispose it; `/verify-self-audit` enforces every disconfirmer
   finding was disposed, and (mirroring Gate 7f) any DISMISSED finding needs explicit justification.
   No new blocking path, no new arbiter — reuses all existing machinery.
4. **Determinism boundary held:** disconfirmer is advisory; enforcement is deterministic.
5. **Stopping discipline pre-registered (see below).**

### Pre-registered "Done" (stopping discipline — from the G1 retro)
G3 is a **bounded design + wiring task**, not an open-ended hardening loop. Done =
- a disconfirmer agent/brief exists and runs at the self-audit step on its own artifact;
- its findings are ingested as WARNs the self-audit must dispose;
- `/verify-self-audit` enforces "every disconfirmer finding disposed; dismissals justified";
- one pass through a real (or dry-run) self-audit shows the wiring works end-to-end.
**Tell-to-stop:** if a proposed change "adds another reviewer" without changing the *perspective
distribution*, or if scope creeps to the review mix / spec gates, stop and re-scope.

## Resolved Questions

- **Meta-objection vs. line-item WARN → RESOLVED: dedicated `disconfirmer_verdict` field.**
  The disconfirmer gets its own verdict field (e.g. `CONCUR` / `DISPUTE-PASS`) separate from
  line-item WARNs, so a meta-objection to the whole PASS *can't be flattened into a dismissable
  line item*. `/verify-self-audit` gates on it. A small, explicit schema change to the self-audit
  contract — accepted as in-scope for G3 because it's what makes the disconfirmer's highest-value
  output (challenging the PASS itself) actually have teeth. (The line-item findings still flow
  through the existing WARN machinery per Decision 3.)

## Open Questions

1. **Run ordering & context.** Does the disconfirmer run strictly before the self-audit-reviewer
   (clean independence, but a sequential Sonnet-confirmer + Opus-disconfirmer pair = latency + tokens
   at the tail), or in parallel (faster, but needs care that it doesn't read the confirmation)?
   Plan-phase wiring detail.
2. **Disconfirmer output contract.** Its findings must be keyed to match the WARN-key schema
   `/verify-self-audit` validates. Exact contract = plan detail, not a brainstorm blocker.
3. **Solo vs swarm path.** The self-audit runs on both autopilot-solo and autopilot-swarm tails
   (SKILL note: solo produces self-audit.md itself). Confirm G3 wiring covers both, or scope to one.

## Feed-Forward

- **Hardest decision:** The diversity axis — and the verification step that nearly sent it the wrong
  way. The named gap reads "all-Opus" (argues for a different model), while the playbook proves the
  skeptic needs the *strong* model. The brainstorm initially resolved this by separating *role*
  diversity from *model* diversity. **Verification then showed the confirmer is already Sonnet**, so
  an Opus disconfirmer delivers both axes at once and the tension dissolves at this surface. The
  durable lesson: the "monoculture" framing was about the *workers*; the *terminal verdict* was
  never part of that monoculture — it was a weaker, lone Sonnet. Check the actual model before
  theorizing about diversity.
- **Rejected alternatives:** (a) Broader scope across all three verification surfaces — rejected as
  spiral risk and YAGNI; spec gates would also breach the determinism boundary. (b) Sonnet/Haiku
  disconfirmer for model diversity — rejected: playbook says it's a structurally weaker skeptic
  (and moot here — confirmer is already Sonnet, so the disconfirmer goes the *other* way, to Opus).
  (c) Disconfirmer with unilateral BLOCK authority — rejected: re-introduces an LLM in the abort
  path, the exact thing G1 removed; Option A's deterministic must-dispose gives teeth without it.
  (d) Bumping the `self-audit-reviewer` from Sonnet to Opus as part of G3 — rejected as scope creep
  past the pre-registered "done"; logged as a latent finding instead.
- **Least confident:** **Efficacy — does an Opus disconfirmer reading the *same* artifacts actually
  produce *orthogonal* findings, or converge on the same blind spots in stronger words?** Role +
  model diversity make orthogonality *likely*, and run-first independence helps, but the real proof
  is a live run (or dry-run) showing the disconfirmer surfaces something the Sonnet confirmer missed
  — not just restating it. Secondary: the token/latency cost of a second Opus pass at the tail on
  every unattended run. Both are plan/verify-phase concerns, not brainstorm blockers.
