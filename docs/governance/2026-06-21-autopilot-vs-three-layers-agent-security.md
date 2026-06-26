---
title: Autopilot Swarm vs. Google's "Three Layers of Agent Security"
date: 2026-06-21
type: governance
status: active
framework:
  name: The Three Layers of Agent Security — A Framework for Policymakers
  publisher: Google DeepMind
  authors: Shaun Ee, Pegah Maham
  published: 2026-06-18
  url: https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/securing-the-future-of-ai-agents/three-layers-of-agent-security.pdf
  companion: AI Control Roadmap (Google DeepMind, 2026-06-18)
subject_system: sandbox unattended swarm autopilot (see docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md)
tags:
  - governance
  - agent-security
  - autopilot
  - swarm
  - guardrails
  - human-oversight
summary: >
  Scores the sandbox unattended-autopilot swarm system against Google DeepMind's
  three-layer agent-security framework and its three core principles (human
  controllers, limited powers, observability). Confirms where the build is
  already strong, names the gaps, and converts each gap into a tracked item.
---

# Autopilot Swarm vs. Google's "Three Layers of Agent Security"

**What this is.** A governance self-assessment: map our unattended swarm
autopilot system (the one documented in
`docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md`)
against Google DeepMind's June 2026 framework, score each dimension, and turn the
gaps into tracked items. Pairs with `project_security-audit-brief` (Layer 1
governance) — the framework's principles are the external rubric; this doc is our
score against it.

**The framework in one paragraph.** Three *layers* (loci of failure): individual
agents, multi-agent systems, the digital ecosystem. Three *core principles* for
downstream developers: agents must have **(1) well-defined human controllers,
(2) limited powers, (3) observable actions and planning.** Cross-referenced with
Meta's "Agents Rule of Two" (at most two of: processes untrusted input / accesses
sensitive data / takes binding external actions). The novel payload is the
multi-agent layer: accountability vacuums, the "zone of indifference,"
algorithmic monoculture, systemic traps — cured (aspirationally) by intelligent
delegation protocols, verification standards, firebreaks, trust/reputation
architectures, and tamper-proof performance ledgers.

---

## Scorecard — the three core principles

Scale: ✅ Strong · ⚠️ Partial · ❌ Gap

| Principle | Score | Evidence in our system | Gap |
|-----------|:-----:|------------------------|-----|
| **1. Well-defined human controllers** | ⚠️ | Compound-Engineering human gates between phases; spec-convergence loop has a non-optional human verification pass; global CLAUDE.md Safety Rule + permissions matrix prompt on destructive ops | Autopilot's `dangerouslySkipPermissions` + injected `bypassPermissions` **blanket-overrides** the risk-tiering during unattended runs. No firebreak-to-human for binding/irreversible actions mid-swarm. |
| **2. Limited powers / least privilege** | ✅ | File-ownership gate (`check_ownership.py`), one-agent-per-blueprint vertical split, per-agent file registry, Bash Command Rules, worktree isolation | Tool/data scope is bounded per agent, but the *blanket* permission bypass widens powers beyond least-privilege for the risky tail. |
| **3. Observable actions & planning** | ✅ | BUILD_TRACKING ledger, phase-report `STATUS` contracts, worker-roster.md, disk-verified status (`verify_delegated_status.py`), cross-worker structural scan, spec-provenance gate | Observation is **pre-swarm (eval) and post-swarm (assembly/review)** — there is no *in-flight* monitor watching workers during execution. |

**Headline finding.** We are strong on **limited powers** and **observability**
(post-hoc), and weakest on **human controllers** — by deliberate design, because
zero-prompt throughput was the whole point. The reconciliation is not "always
prompt"; the framework's real standard is **oversight proportionate to risk**,
which our own CLAUDE.md already encodes and autopilot overrides.

---

## Layer-by-layer mapping

### Layer I — Securing individual agents

| Framework element | Our implementation | Status |
|-------------------|--------------------|:------:|
| System-level safeguards (input/output filtering, defence-in-depth) | Spec-completeness 6-section gate; agent-pitfalls injection (FC1–FC57) as a "recognise-and-refuse" prior | ✅ |
| Least-privilege tools | File-ownership gate + per-agent registry | ✅ |
| Model hardening / red-teaming against prompt injection | Not our layer (we are downstream of the model); pitfalls injection is the nearest analog | n/a |
| Oversight proportionate to risk | CLAUDE.md Safety Rule + permissions matrix — **but bypassed under autopilot** | ⚠️ |
| "AI monitors" (in-flight, e.g. dual-agent Planner/Talker) | — | ❌ |

### Layer II — Multi-agent risks (where our system actually lives)

| Framework element | Our implementation | Status |
|-------------------|--------------------|:------:|
| Verification standards ("what a completed task looks like before handoff") | Contract-check, spec-eval gate, `STATUS: PASS` artifact contracts | ✅ primitive form |
| Accountability vacuum / "zone of indifference" | Cross-worker structural scan flags *divergent gap-fills* (two workers filling the same spec gap differently) | ✅ **ahead of the curve** |
| Firebreaks (halt & escalate to human) | Blocking failure classes → **abort** (`assembly-ownership-conflict`, contract-check fail) | ⚠️ halts, but escalates to abort, not to a human |
| Tamper-proof performance ledger | BUILD_TRACKING + disk-verified artifacts + run-id matching | ⚠️ primitive; integrity gap already logged (per-run nonce TODO) |
| Compositional-fragment / artifact-poisoning traps | `check_spec_provenance.py` (FC52 / BASEREF-FRESH) — workers must read the *same* artifact the gates validated | ✅ benign-case cousin |
| Algorithmic monoculture / correlated errors | All workers = Opus, near-identical briefs; FC catalog *is* a correlated-error log | ❌ **risk we embody** |
| Intelligent delegation = explicit transfer of authority/responsibility | STATUS contracts cover "verification"; authority/responsibility transfer is implicit, not modeled | ⚠️ |
| Independent verification (ISO 42001/27001 spirit) | Spec-convergence loop: Claude ↔ Codex ↔ NotebookLM ↔ human | ✅ |

### Layer III — Digital ecosystem

Largely out of scope for an internal build system (this layer is supply-chain
integrity, agent-IDs/IAM, and cyber-defense operations). Nearest analogs: our
eval-harness + Monte-Carlo + pitfall-eval ≈ the framework's call for "advanced
cyber capability evaluations / realistic multi-stage scenarios"; the
share-not-fork rule on `check_spec_provenance.py` ≈ supply-chain integrity in
miniature. No action items taken here for now.

---

## The central tension — zero-prompt vs. human controllers

Our unattended-autopilot win is `dangerouslySkipPermissions` plus injected
`bypassPermissions` on every spawned agent. It **removes the human controller**
for throughput. The framework's standard, though, is *oversight proportionate to
risk* — and we already encode that risk-tiering in two places the blanket bypass
overrides:

- **Global CLAUDE.md Safety Rule** — ask before destructive/irreversible actions
  (delete files/branches, force-push, discard uncommitted changes, destructive DB
  ops, remove packages, amend pushed commits).
- **Permissions matrix** — auto-accept reads/edits/most git, but still prompt on
  `git push`, `git reset --hard`, `git clean`, `mv`.

**Reconciliation (the design target):** keep zero-prompt for the safe 95% (file
writes inside the worktree, local commits, tests), but route the binding/
irreversible tail (production DB, external sends, force-push, package removal,
pushes to shared branches) through a **firebreak that escalates to a human**.
That satisfies "limited powers + human controllers" *without* surrendering
unattended throughput. This is the framework's firebreak concept applied to our
abort-only halt.

---

## Tracked items (gaps → work)

| # | Item | Framework basis | Priority | Status | Notes |
|---|------|-----------------|:--------:|:------:|-------|
| **G1** | **Risk-tiered firebreak in autopilot** — classify actions; auto-run low-stakes, escalate binding/irreversible to a human gate instead of blanket `bypassPermissions` | Principle 1 (human controllers) + firebreaks | **High** | **DONE** (live-validation pending) | Built, hardened, global hook registered, orchestrator-wired (sentinel + positive-control probe + teardown), e2e-verified. **Not yet exercised on a real swarm run** — the built-in probe self-validates on first real use (aborts fail-open if not live). Residuals: stale sentinel on orchestrator crash; solo path unwired; classifier interpreter/`$VAR`/outward-unlisted-binary tails. Arc: `docs/solutions/2026-06-25-g1-firebreak-activation-arc.md`; convergence lesson: `docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md` |
| **G2** | **In-flight AI monitor** — a monitor agent (Planner/Talker dual-agent pattern) watching workers *during* execution, not only pre/post gates | Layer I "AI monitors" | Medium | Open | Net-new capability; brainstorm first — cost vs. coverage |
| **G3** | **Name & mitigate monoculture** — inject model/prompt diversity into *critical verification* roles (not just research fan-outs); apply playbook's adversarial-verify + "opus disconfirmer > sonnet extractors" lessons | Layer II monoculture / correlated errors | Medium | Open | We know the antidote; we just don't apply it to build-verification yet. **The G1 review loop was field proof of this** — correlated Codex+Claude reviewers, both blind the same way |
| **G4** | **Harden the performance ledger** — per-run nonce / signed STATUS artifacts to close the reused-run-id integrity hole | Layer II tamper-proof ledger | Medium | Open | Already on the autopilot backlog; framework independently argues for it |
| **G5** | **Model delegation as authority transfer** — make the handoff record explicit authority/responsibility/accountability, not just task status | Layer II intelligent delegation | Low | Open | Mostly a documentation/contract upgrade to existing STATUS artifacts |

## Where the framework validates what we already do

- Cross-worker divergent-gap-fill detection **anticipates** the "accountability
  vacuum / zone of indifference" risk Part II spends pages on.
- The spec-convergence loop **is** the "independent verification" the framework
  calls for (and our human pass is the non-optional structural-contradiction
  catch the paper says AI tools miss).
- Our backlog items (per-run nonce, FC51 cherry-pick rule, eval harness) are each
  independently argued for by this framework — useful external confirmation that
  the roadmap is pointed the right way.

---

## Provenance

Framework read in full (Exec Summary, Background, Part I, Part II; Part III
characterised from the Exec Summary) on 2026-06-21 from the published PDF.
Subject-system facts drawn from
`docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md` and
the underlying autopilot/guardrail/eval source docs it indexes.
