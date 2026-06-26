# HANDOFF — Sandbox · Next step: G3 (monoculture in verification)

**Date:** 2026-06-25
**Branch:** `feat/g1-risk-tiered-firebreak` (G1 work; start G3 on a fresh branch)
**Phase:** G1 Compound COMPLETE. Next compound cycle = **G3, starting at Brainstorm.**

---

## TL;DR — where we are

We analyzed Google DeepMind's *"Three Layers of Agent Security"* and scored the autopilot
swarm against it (`docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md`),
producing five hardening gaps **G1–G5**. **G1 (risk-tiered firebreak) is DONE and LIVE**
— built, hardened, global hook registered, orchestrator-wired, captured across all
learning surfaces. Its only open item is first-real-swarm validation, which its built-in
probe performs automatically. **The recommended next step is G3.**

⚠️ **Two live facts a new session must know up front:**
1. **The firebreak is active machine-wide.** A global PreToolUse hook is registered in
   `~/.claude/settings.json` (backup `…bak-firebreak-20260625`). It is a **no-op unless a
   run sentinel exists**, so manual sessions are unaffected — but any **autopilot swarm
   run now activates it** (writes `.claude/firebreak-active.json`, runs a positive-control
   probe that ABORTS the run fail-open if the hook isn't governing). To clear a stale
   sentinel from a crashed run: `python3 .claude/hooks/firebreak-activate.py deactivate`.
2. **G3 touches the autopilot verification path, which now overlaps G1.** Changing review
   roles means re-reading how the firebreak + review agents interact.

---

## THE NEXT STEP — G3: Name & mitigate monoculture

### What G3 is (from the governance scorecard)
> Inject **model/prompt diversity into critical *verification* roles** (not just research
> fan-outs); apply the playbook's adversarial-verify + "opus disconfirmer > sonnet
> extractors" lessons. — Layer II (multi-agent), monoculture / correlated errors.

The scorecard marks this **❌ "a risk we embody"**: *"All workers = Opus, near-identical
briefs; the FC catalog* is *a correlated-error log."* When every agent is the same model
running near-identical briefs, they make the **same mistakes**, so review can't catch what
all reviewers are blind to.

### Why now — we have FIELD PROOF
The G1 review loop was a live instance of exactly this failure: **Codex and Claude were
functionally correlated reviewers**, both running "find any allowed input," neither holding
the orthogonal "is this surface even in scope / is this convergent?" perspective — so the
loop ran ~17 passes and could not self-terminate. We diagnosed it in
`docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md` (Update 2026-06-25).
G3 is the systemic fix for that class.

### The asymmetry to close
The **antidote is already proven — but only in RESEARCH/outreach fan-outs, not in BUILD
verification.** See `~/.claude/docs/search-agent-playbook.md`:
- A dedicated **Disconfirmer / adversary** role (≥1 agent told to *disprove/attack*, not
  confirm) catches what confirmers structurally miss (playbook SL5/SL8; line 54).
- **"opus disconfirmer > sonnet extractors"** for the adjudication role; **Haiku is
  unreliable for adjudication** (line 146 + the Haiku caveat).
These lessons live in the search/research playbook. **G3's job is to carry them into the
autopilot's build-verification roles** (the review agents, the self-audit, the spec gates).

### Concrete surfaces a fresh session should examine (don't pre-decide — brainstorm first)
- **Local review agents:** `.claude/agents/flow-trace-reviewer.md`, `self-audit-reviewer.md`.
- **Plugin review agents** used by `/workflows:review` (security-sentinel, performance-oracle,
  learnings-researcher, etc.) — from the compound-engineering plugin, not local.
- **Where the review mix + models are chosen:** `.claude/skills/autopilot/SKILL.md`
  (Steps 11w–16w assembly/verification via swarm-runner; Step 17w/18w tail via tail-runner;
  the self-audit gate). Workers spawn `model: "opus"` (SKILL Step 10w) — the monoculture
  source.
- **The self-audit** (`self-audit-reviewer` → `/verify-self-audit`) is the single highest-
  leverage place to seat a disconfirmer, since it's the terminal verdict.

### Hard constraints to weigh in the brainstorm
- **Billing (CRITICAL):** model diversity must stay Max-covered. Standard Sonnet 4.6 and
  Opus 4.8 are covered; **Sonnet 4.6 (1M context) DRAWS FROM USAGE CREDITS — avoid it.**
  Haiku is cheap but **unreliable for adjudication** (playbook). So "diversity" ≠ "any
  model"; it's prompt/role diversity + a careful model choice for the disconfirmer.
- **Apply the stopping discipline we just learned** (don't let G3 spiral): it's a bounded
  design + wiring task. Pre-register what "done" means; a fix that "adds another reviewer"
  without changing the *perspective distribution* is the tell to stop and rethink.
- **Determinism boundary:** the firebreak proved "no LLM in the dispose path." G3 adds LLM
  diversity to *advisory* verification, not to deterministic gates — keep that line.

### Process (six-phase compound loop)
Start at **Brainstorm** (`/workflows:brainstorm`) — G3 is a design question (which roles,
which models, confirmer-vs-disconfirmer split, how to adjudicate conflicts) before it's
code. Carry the Feed-Forward risk forward. This is a clean new cycle on a fresh branch.

---

## Key Artifacts & Pointers

| Topic | Location |
|-------|----------|
| Governance map (G1–G5, scored) | `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md` |
| G1 plan | `docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md` |
| G1 activation arc (solution) | `docs/solutions/2026-06-25-g1-firebreak-activation-arc.md` |
| Convergence-loop lesson (solution) | `docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md` |
| Disconfirmer / adversarial-verify lessons | `~/.claude/docs/search-agent-playbook.md` (lines ~54, 146) |
| G1 code | `.claude/hooks/firebreak-{gate.sh,classify.py,activate.py}`; SKILL 9w.9.6/17w/18w |
| Sandbox auto-memory (cycle note) | `~/.claude/projects/-Users-alejandroguillen-Projects-sandbox/memory/g1-firebreak-2026-06-25.md` |

## Deferred Backlog (priority order)

0. **G1 live validation** — first real swarm run self-validates (probe aborts fail-open).
   Needs the `dangerouslySkipPermissions` env.
1. **G3 — monoculture in verification (NEXT)** — see the full brief above.
2. **G4 — ledger nonce** — per-run nonce / signed STATUS (also key **FC52-BASEREF-FRESH-071**).
3. **G5 — delegation as authority transfer** — handoff records carry authority/accountability.
4. **G2 — in-flight AI monitor** — net-new; brainstorm first (cost vs coverage).
5. **G1 follow-ons (small):** wire the SOLO autopilot path; close stale-sentinel-on-crash;
   outward `--cache-to type=registry` (cache push) declared residual.
6. **Carried (pre-G1):** FC51 spec-at-worktree-base repair rule; Track A `P-extract`;
   `validate_hardening.py` adoption gate; eval-harness↔catalog FC drift (FC48–FC57);
   Todo #070 (P2 double-query in `callsheets.generate`).

## Stashes (untouched, local)
3 stashes on `master`: `stash@{0}`/`{1}` superseded cpaa WIP (safe to drop);
`stash@{2}` = unmerged venue-scraper proxy/`html_mode` for `feat/lead-scraper-expansion`
(keeper — fix `claude-sonnet-4-20250514` → `claude-sonnet-4-6` on revival).

## Recovery SHAs (older)
| Ref (deleted) | Tip SHA | Where it lives now |
|---------------|---------|--------------------|
| `feat/film-production-pm` | `9b432bf` | 2nd-parent lineage of `49deb17` on master |
| `test/fc52-9w95-rewire-real-swarm` | `998854e` | reflog / GC window (~30d) |

## Three Questions (G1 Feed-Forward, carried)
1. **Hardest decision?** Whether "flip it on" meant the hook (inert for swarms) or the
   orchestrator wiring (the real thing). Both, in order.
2. **What was rejected?** Manufacturing a throwaway swarm to validate G1 — the probe
   self-validates on first real use.
3. **Least confident?** The first real swarm run (env permitting); failure mode is a
   halted run, not an ungoverned one.

---

## Prompt for Next Session (copy-paste)

```
Read HANDOFF.md. This is sandbox; G1 firebreak is DONE/live (don't reopen it). Start the
G3 compound cycle: "Name & mitigate monoculture — inject model/prompt diversity into
build-VERIFICATION roles, not just research fan-outs." Begin with /workflows:brainstorm.

Ground it in: (a) the governance map G3 row (docs/governance/2026-06-21-...), (b) the
field proof that correlated reviewers share blind spots (docs/solutions/2026-06-24-...
Update 2026-06-25), and (c) the proven antidote in ~/.claude/docs/search-agent-playbook.md
(disconfirmer role; "opus disconfirmer > sonnet extractors"; Haiku unreliable for
adjudication). The antidote is proven in RESEARCH fan-outs — G3 carries it into autopilot
build-verification (review agents, self-audit, spec gates; models pinned in
.claude/skills/autopilot/SKILL.md).

Constraints: keep diversity Max-covered (avoid Sonnet 1M-context = usage credits); no LLM
in deterministic gates (advisory only); and apply the stopping discipline from the G1
retro — G3 is a bounded design+wiring task, pre-register what "done" means.
```
