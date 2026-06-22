---
title: Unattended Swarm Autopilot — Master Extraction
date: 2026-06-21
type: reference
status: canonical
tags:
  - autopilot
  - swarm
  - agents
  - guardrails
  - evaluations
  - traceability
  - lessons-learned
summary: >
  Single canonical reference consolidating all sandbox work on unattended swarm
  autopilot: the orchestration system, the deterministic guardrails and
  traceability machinery, the pre-swarm evaluation layer, the full 24-build
  catalog, the 6-phase R&D arc, and the distilled lessons learned. Synthesized
  from a 6-agent location-slice extraction over ~30 source docs.
source_extraction:
  method: 6-agent Explore location-slice fan-out
  zones:
    - .claude/skills/autopilot + .claude/agents
    - tools/ + BUILD_TRACKING + ~/.claude/docs/agent-pitfalls.md
    - eval-harness/ + eval gate docs
    - docs/solutions/*swarm-build*
    - docs/plans + docs/brainstorms (autopilot R&D)
    - BUILD_TRACKING files + docs/reviews + lessons
---

# Unattended Swarm Autopilot — Master Extraction

**Purpose.** One canonical reference for everything the sandbox has built around
unattended multi-agent ("swarm") autopilot: the system itself, the guardrails,
the evaluation gates, the traceability chain, every build we ran, the design
evolution, and the lessons. Replaces the need to read ~30 scattered docs to
reconstruct the picture.

**Provenance.** Synthesized 2026-06-21 from a 6-agent location-slice extraction
(Explore agents, one per repo zone). Cross-slice agreement is treated as
confidence; the one cross-slice contradiction (FC catalog count) is flagged and
resolved in §7.

---

## 1. The System — what "unattended swarm autopilot" is

A four-role orchestration engine that turns a converged spec into a merged,
reviewed feature with **zero human prompts**.

- **Orchestrator** — `.claude/skills/autopilot/SKILL.md`. Runs inline. Spawns
  all worker agents in a single parallel batch with `mode:"bypassPermissions"`,
  `model:"opus"`, `isolation:"worktree"`, `run_in_background:true`. Workers root
  on `origin/<default-branch>`, **not** the orchestrator's feature branch (FC51
  safety net).
- **Swarm-planner** — `.claude/agents/swarm-planner.md`. Pre-work agent that
  reads the spec's shared interface and emits the vertical file→agent assignment
  table (typically one agent per Flask blueprint). Dedup gate: no file may appear
  in two assignments.
- **Swarm-runner** — `.claude/agents/swarm-runner.md`. Fresh-context assembly
  agent. Cherry-picks completed workers' commits over `merge-base..branch` (the
  O3 invariant), runs contract/smoke/test inline, merges to an isolated
  `swarm-<run-id>-assembly` branch before main. Cherry-pick conflict =
  `assembly-ownership-conflict` → abort, preserve worker branches.
- **Tail-runner** — review + compound + learnings propagation + BUILD_TRACKING
  fill + self-audit, all in one fresh window so the orchestrator never saturates.

**Phase delegation boundary:** Steps 1–10.5w run inline in the orchestrator
(needs the Agent tool to deepen + spawn). Steps 11w–16w run in swarm-runner.
Steps 17w–18w run in tail-runner. The orchestrator disk-verifies the tail result
via `tools/verify_delegated_status.py`.

**Two commands:** `/autopilot "description"` then `/resolve-todos` — fully
unattended.

### What makes it zero-prompt (the three-layer fix)

1. **Permission bypass.** `dangerouslySkipPermissions:true` in project
   `.claude/settings.local.json`. The orchestrator MUST run from the project root
   (`cd ~/Projects/sandbox`) or only `~/.claude/settings.json` loads and the
   permission is absent.
2. **Mandatory injection.** Every spawned agent brief includes
   `mode:"bypassPermissions"`. Without it, spawned agents inherit the session's
   mode and prompt for tool approval — breaking the guarantee.
3. **Bash Command Rules.** One command per call. No `&&`/`;` chains, no `cd &&`,
   no `source activate`, no `for` loops, no `python3 -c` (write to a file, run the
   file — the FC8 smoke-test rule). Security heuristics fire on compound commands
   *above* the permission bypass, so this is non-negotiable.

Also load-bearing for unattended runs: never invoke interactive skills mid-run
(`AskUserQuestion` blocks); model-pin workers to `opus`; standardize phase
reports so line 1 is `STATUS: PASS|FAIL` with no YAML frontmatter (orchestrator
reads `limit:1` on PASS to keep context clean); 10-minute per-agent timeout.

---

## 2. Guardrails & Traceability — the deterministic controls

### Traceability / provenance machinery (`tools/`)

- **`check_spec_provenance.py`** — the FC52 / FC51 / **BASEREF-FRESH-071** gate.
  Compares the spec file's git blob-SHA on the base ref vs the feature branch;
  resolves the base to `origin/<default>` when the remote-tracking ref exists
  (the ref worktrees actually root on under `baseRef=fresh`) and WARNs when the
  local default has unpushed commits. Exit codes: `0` PROVENANCE_OK, `3`
  PROVENANCE_DRIFT, `2` ERROR, `5` BAD_ARGS. Fail-closed. Built because **Run
  070** had 16 workers reading a stale 2010-line spec while the gates validated
  the converged 2295-line one — "missed only by luck." (The BASEREF-FRESH-071
  facet was added 2026-06-21.)
- **`verify_delegated_status.py`** — disk-verifies a delegated agent's terminal
  STATUS. On-disk artifact is authoritative; the echoed "wire" STATUS never
  overrides a fresh, run-id-matching, non-FAIL artifact. Checks existence,
  freshness (mtime ≥ run-start), run-id match, terminal-status presence. Exit:
  `0` PASS, `1` FAIL_STATUS, `2` MISSING, `3` STALE, `4` NO_STATUS, `5` BAD_ARGS,
  `6` RUNID_MISMATCH. Fail-closed.
- **`check_ownership.py`** — verifies each agent only touched its assigned files
  (`git diff --name-only` vs the per-agent registry); blocks assembly on any
  boundary violation. Proven at 31 agents.
- **`eval-harness/validate_hardening.py`** — negative-test fixture runner for the
  orchestration-hardening tracks (A/B/C + FC52), with an **honesty contract**:
  EXERCISED / SPIKE-VALIDATED / PROSE-ASSERTED / MIRRORED, never rounded up.

**Design rule — share-not-fork:** `check_spec_provenance.py` is the single impl
used by both the autopilot gate and the hardening fixture. No second copy that
can drift.

### The failure-class catalog

`~/.claude/docs/agent-pitfalls.md` — **1,027 lines, FC1–FC57** (frozen IDs,
append-only), distilled from 23 swarm builds + 8 solo/manual incidents
(~265 agent-runs). Injected into every agent brief so agents learn from prior
mistakes. Load-bearing codes:

| FC | Class | Guard |
|----|-------|-------|
| FC1 | Naming divergence without explicit registry | spec-completeness-checker (Export Names) |
| FC3 | Dead wiring across ownership boundaries | spec-consistency-checker (Cross-Boundary Wiring) |
| FC4 | Validation responsibility gap | spec-completeness-checker (Input Validation) |
| FC8 | Compound bash commands | Bash Command Rules / smoke-test-to-file |
| FC11 | Orchestrator skips learnings propagation | tail-runner mandatory step + artifact verify |
| FC29 | Non-transactional / missing BEGIN IMMEDIATE+ROLLBACK | Transaction Contracts section |
| FC37 | Worktree agent completes but fails to commit | post-spawn cross-worker scan |
| FC48 | Ghost files from prior build | ghost-file cleanup (Step 9w.9) |
| FC50 | Route→orchestration entrypoint unpinned | spec-completeness-checker Check 1b (signature-presence) |
| FC51 | Worker worktrees rooted on default branch | cherry-pick assembly + provenance gate |
| FC52 | Gate validates one artifact, consumer uses another | `check_spec_provenance.py` |

### Build tracking (the traceability ledger)

`BUILD_TRACKING.md` (template at `~/.claude/docs/autopilot-tracking-template.md`,
copied per run): Run Info / Phase Status / **AGENT_STATUS** (per-agent: status,
files, tests, duration, cross-boundary imports/exports, commit hash, issues) /
**FAILURES** (append-only, each with an FC reference) / **RUN_METRICS**.

**The traceability chain:** failure → FAILURES log (with FC ref) → trace to
originating agent in review → fold back into `agent-pitfalls.md` → injected into
the next build's agent briefs.

---

## 3. Evaluations — the pre-swarm validation layer

Three gates plus a simulator, wired into autopilot Steps 9w.5–9w.8.

| Tool | Question it answers | Method | Status |
|------|---------------------|--------|--------|
| **spec-completeness-checker** (9w.6) | Does the spec cover all 6 mandatory surfaces? (Export Names, Cross-Boundary Wiring, Input Validation, Registration, Transaction Contracts, Authorization) | Structural enumerate→heading→rows | **Hard gate.** 100% P1 correlation vs runs 047–052 |
| **spec_eval_gate.py** (9w.8) | Can agents actually *execute* the spec's concrete claims? | Extract claims (deterministic tables + LLM prose) → Haiku generates → Sonnet anti-leniency judge; HIGH-conf (≥0.90) must all pass | **Advisory only** — demoted after 2-for-2 false-FAILs (~0% field precision vs 81% bench) |
| **pitfall_eval.py** | Are the pitfall *rules* clear enough that agents follow them? | Per-FC YAML scenarios → Haiku agent → deterministic + Sonnet judge → CLEAR/AMBIGUOUS/BROKEN buckets + with/without-rule delta | Built (v1), Stage 1 validated |
| **mc_simulator.py** | Given N agents + injected rules, P(clean build)? | Monte Carlo over FC pass-rates × relevance weights (calibrated on 20 builds, 255 runs) | Built (v1, static model) |

**Pre-swarm gate sequence:** 9w.5 spec-consistency (hard) → 9w.6 spec-completeness
(hard, 1 retry + commit) → 9w.7 reserved (MC projection, future) → 9w.8 spec-eval
(advisory, writes `spec-eval-verification.md` on PASS to catch gate-bypass bugs).

**Vision** (`eval-harness/docs/multi-parallel-llm-mc-research.md`): multi-model
parallel sims → fit distributions from real telemetry → MC at scale → hybrid
LLM+MC auto-tuning (v2–v4, mostly unbuilt). Bridge steps: runner accepts a model
list; capture build telemetry from BUILD_TRACKING; parallel build runner; hybrid
feedback loop.

**Pre-launch hardening (the spec-convergence loop):** Claude Code authors → Codex
reviews (fresh context) → fix → NotebookLM cross-references source data → fix →
loop Codex↔Claude until clean → **human structural verification** → launch.
Convergence criterion: Codex clean AND human finds zero P0s. Key insight: P0s are
*always* cross-section contradictions; AI tools miss them, so the human pass is
non-optional.

---

## 4. The Builds — complete catalog (24 swarm builds)

| Date | Build (run #) | Agents | Files | Phases | P0/P1/P2 | Zero-prompt | Standout lesson |
|------|---------------|-------:|------:|:------:|:--------:|:-----------:|-----------------|
| 04-07 | Flask Swarm Acid Test | 4 | 20 | 1 | 0/0/0 | – | context-manager usage examples are mandatory in specs |
| 04-09 | Bookmark Manager | 3 | 17 | 1 | 0/2/0 | – | endpoint registry kills `url_for` naming divergence |
| 04-09 | Personal Finance Tracker | 3 | 23 | 1 | 0/0/1 | – | `ON DELETE SET DEFAULT` reliable w/ `PRAGMA foreign_keys=ON` |
| 04-09 | Recipe Organizer | 3 | 24 | 1 | 0/0/1 | – | composite PK on junctions; batch fetch kills N+1 |
| 04-09 | Task Tracker Categories | 4 | 19 | 1 | 0/1/0 | – | scalar return types need usage examples, not just signatures |
| 04-12 | Notes API (Node/Express) | 3 | 11 | 1 | 0/2/0 | – | swarm pattern is stack-agnostic |
| 04-12 | Project Tracker | 5 | 25 | 1 | 0/2/0 | – | cross-module writes work with exact prescribed call pattern |
| 04-30 | **AI Filmmaking Ethics** (033) | 15 | **116** | 4 | 0/13/0 | ✓ | **most files**; import mismatch + dead wiring + race conditions |
| 05-03 | Writers Room Council (034) | 13 | 85 | 4 | 0/6/7 | ✓ | schemas agent as a phase gate prevents incompatible shapes |
| 05-13 | Workshop Registration Hub | 8 | 35 | 1 | 2/8/4 | – | cross-stack transaction safety needs multi-step atomicity |
| 05-19 | Client Music Planner | 20 | 75 | 1 | 0/4/30 | – | token portal access validated at 20 agents |
| 05-19 | Solopreneur Command Center (047) | 16 | 98 | 1 | 0/1/0 | – | vertical blueprint split → 0 merge conflicts at 16 |
| 05-20 | VenueConnect | 25 | 90 | 1 | 0/10/15 | – | 3-role RBAC + settlement engine |
| 05-20 | **GigSheet** (050) | **31** | 96 | 1 | 0/8/17 | ✓ | **largest swarm**; 0 FC37; CSP-CDN cross-file pattern |
| 05-21 | RestaurantOps (052) | 29 | 98 | 1 | 0/8/0 | ✓ | `isolation_level=None` recurred; tx-error wrapper mandatory |
| 05-21 | BrewOps | 21 | 54 | 1 | 0/7/6 | ✓ | derived-state ownership enforced at VALID_TRANSITIONS (FC45) |
| 05-21 | GymFlow (054) | 26 | 67 | 1 | 0/2/0 | ✓ | missing ROLLBACK crashes tx; consistency-checker FP rate ~40% |
| 05-22 | CoWorkFlow | 22 | 62 | 1 | 0/1/0 | ✓ | CSRF token parens belong in Coordinated Behaviors |
| 05-22 | Prompting Dashboard (061) | 10 | 25 | 1 | 0/3/0 | – | context death at moderate scale; FTS5 BEFORE triggers |
| 05-23 | Client Intake Dashboard | 15 | 60 | 1 | 0/10/0 | – | XSS in Jinja2 custom filters needs explicit `Markup()` escaping |
| 06-01 | Prompting Dashboard (064) | 12 | 62 | 1 | 0/2/0 | ✓ | Py3.14 autocommit needs `with conn:`; Fernet encryption |
| 06-02 | Film Production PM (063) | 16 | 89 | 1 | 0/6/0 | – | contract-check caught 6 mismatches pre-swarm |
| 06-06 | Gig Outcome Tracker (068) | 12 | 33 | 1 | 0/0/2 | ✓ | 3-stage context-death delegation validated |
| 06-07 | CPAA Event Replay (069) | 24 | 43 | 1 | 0/4/2 | ✓ | **2× scale ceiling**; unpinned entrypoints diverged (FC50) |
| 06-08 | **Film Production PM** (070) | 16 | 94 | 1 | 0/0/0 | ✓ | **cleanest run**; Tracks A/B/C all validated |

**Superlatives:** largest = GigSheet **31 agents** · most files = Ethics **116** ·
cleanest = Run 070 (**0/0/0**) · highest review burden = Client Intake / Workshop
Hub (10 / 8 P1) · **0 merge conflicts across all 24 builds** (vertical blueprint
split + ownership gate).

> Note: the table lists 25 rows because two separate Prompting Dashboard runs
> (061, 064) are recorded; "24 builds" is the canonical count from the build
> catalog. Reconcile if a precise tally matters.

---

## 5. The R&D arc — how it evolved (6 phases)

1. **Foundation** (Mar 30–Apr 9) — agents parallelize *if* given one shared spec
   contract (Export Names + Cross-Boundary Wiring tables). Discovered the Bash
   Command Rules constraint. Unlocked 4–6 agent builds, 0 conflicts.
   `docs/solutions/2026-04-09-autopilot-swarm-orchestration.md`
2. **Scale + context-death discovery** (May 6–20) — orchestrator hits 0% context
   in the shared tail at 12–31 agents (Run 050 lost BUILD_TRACKING, self-audit,
   learnings). Five compounding causes (prompt accumulation, no state
   persistence, uncollapsed spec, tail re-reads everything, deferred tracking).
   `docs/solutions/2026-05-20-autopilot-context-window-optimization.md`
3. **Context management** — checkpointing worked but *broke unattended* execution
   (needed a manual `/tail-resume`) → rejected as the primary cure.
4. **Delegation architecture** (Jun 5) — three-layer defense: no-read (STATUS-only
   `limit:1`), output contracts (agents write to disk, return path+STATUS),
   delegate heavy phases to fresh-context agents. Buys unattended to ~12–15
   agents. Honest limit: deepening + worker spawn stay inline (Agent tool is
   top-level only), so 20+ agent builds remain partly unproven.
   `docs/solutions/2026-06-05-autopilot-context-death-delegation-architecture.md`
5. **Authority inversion** (Jun 6) — wire STATUS is unreliable (Run 068 tail
   forgot to echo STATUS on a fully successful run) → move terminal authority to
   disk-verified artifacts (`verify_delegated_status.py`); serialize all implicit
   state when delegating (worker-roster.md).
   `docs/solutions/2026-06-06-autopilot-orchestration-hardening-A-reliability.md`
6. **Field-driven hardening** (Jun 7) — three tracks: (A) cherry-pick assembly off
   `merge-base` for FC51; (B) FC50 orchestration-entrypoint signature guard; (C)
   demote spec-eval to advisory. **Field precision beats bench calibration.**
   `docs/solutions/2026-06-07-autopilot-orchestration-hardening.md`

### Key design decisions & rejected alternatives

| Decision | Chosen | Rejected | Why |
|----------|--------|----------|-----|
| Skill vs command | Skill with logic | Static markdown | runtime branching impossible in markdown |
| Spec as contract | Single shared doc | Per-agent sub-specs | reduces integration surface |
| Assembly isolation | Merge to `swarm-<run-id>-assembly` first | Direct to main | failed assemblies never pollute main |
| Worker isolation | Worktrees + ownership gate | Inline branches | parallel safety; diff catches contamination |
| Context-death cure | Layered (no-read + contracts + delegation) | Checkpointing only | checkpointing breaks unattended |
| Status authority | On-disk artifact (script-verified) | Wire STATUS echo | wire is unreliable |
| Build state storage | Markdown Phase Status table | YAML frontmatter | zero precedent; markdown proven 15+ builds |
| Low-precision gate | Demote to advisory, keep data | Enforce hard | 100% waive-rate = net-negative |
| Ownership base | `merge-base(original, branch)` | Hardcoded `main` | true fork point (the O3 invariant) |

### Scaling progression

4–6 agents (Apr) → 31 agents (May, GigSheet) → delegation re-baselines safe
unattended at 12–15 (Jun 5) → disk-verify eliminates tail context-death (Jun 6) →
cherry-pick assembly proving at 16/24 (Jun 7–8). 0 merge conflicts throughout.

---

## 6. Lessons learned

### Top recurring failure modes (by frequency across builds)

1. **FC4 — validation responsibility gap** (~10×): missing imports, validators,
   error handling. Fix: spec lists ALL imports + per-route validation rules.
2. **FC1 — naming divergence** (~8×): form fields, blueprint names, CSS classes.
   Fix: Coordinated Behaviors section with exact string literals.
3. **Cross-section contradictions** (~7×): each section internally consistent,
   incompatible across sections. Fix: spec-consistency gate pre-swarm.
4. **FC29 — transaction boundaries** (~6×): missing `db.commit()` / no
   `BEGIN IMMEDIATE` / no try/except/ROLLBACK wrapper. Fix: Transaction Contracts
   section annotating every write function.
5. **FC9 — mock/test data mismatches** (~5×): tests infer field names instead of
   reading the WTForms class. Fix: Form Fields Registry.
6. **FC31 — cross-flow integrity** (~4×): template `btn-move-up` vs JS `.move-up`.
   Fix: flow-trace reviewer mandatory for any HTML+JS+Python feature.

### Durable process lessons

- **Zero-prompt needs all three layers** (instruction rules + allowlist +
  prescriptive rewrites) — none alone suffices.
- **Spec-convergence loop is non-optional** — P0s are always cross-section
  contradictions; human structural verification catches what AI tools miss.
- **Pitfalls injection is mandatory** — without it, agents repeat the same
  mistakes every build.
- **Don't break the autopilot loop early** — finish all phases in one session, or
  the next session's skill-loading fails.
- **Field precision > design-time calibration** — demote gates the field
  overrides; strengthen the high-precision gate in the same change.
- **Verify-first spike before touching a working pipeline** (throwaway repos,
  assertions, then edit production SKILL.md).
- **Assembly fix rate ~5% is acceptable** — optimize recovery speed, don't chase
  0%.
- **Serialize all implicit state when delegating** — sub-agents have zero access
  to orchestrator history.

### Run metrics (across swarm builds)

| Dimension | Range | Median |
|-----------|-------|--------|
| Agents per run | 3–31 | 16 |
| Files per run | 11–116 | ~75 |
| Merge conflicts | 0 | 0 |
| Assembly fix rate | 4–7% | ~5% |
| P1 findings per review | 0–10 | 2–4 |
| Smoke / test pass rate post-assembly | 100% | 100% |
| Self-audit grade | B–A | A− |

### Cross-build contradictions that resolved over time

- **Spec-eval gate:** "keep it hard, 81% bench precision" (06-01) → "field shows
  ~0% precision, demote to advisory" (06-07). Field overrode bench.
- **Assembly strategy:** plan defaulted to per-worker merge-back → field proved
  uniform cherry-pick clean 24/24; merge-back is dead code in divergent-base
  reality.
- **FC29 scope:** initially "multi-table BEGIN IMMEDIATE" → Run 052 showed the
  try/except/ROLLBACK wrapper is part of the same class.

### Auditability gaps still open

- HANDOFF key format drift (`048-W` WARN keys vs `048-D` deferred keys).
- Missing smoke-test / flow-trace report artifacts on some runs (prose claims
  PASS but no file in `docs/reports/<run-id>/`).
- Brief-injection (Run 070) was a valid but un-auditable FC51 mitigation — the
  cherry-pick-spec-into-worktree rule should replace it.

---

## 7. Cross-slice confidence & the flagged contradiction

**High confidence (3+ agents independently agreed):** the spec-eval demotion
story; the FC51/FC52 provenance lineage; the three-layer zero-prompt fix; 31-agent
max; the 0-merge-conflict record across all builds.

**⚠️ Contradiction — FC catalog count.** The autopilot-skill agent reported "52+
FCs", the eval-harness agent "47 FCs", and only the agent that read the canonical
`~/.claude/docs/agent-pitfalls.md` had ground truth: **FC1–FC57**. Resolution: the
live catalog has grown to ~57; the eval harness was built against an older 47-FC
snapshot; "52" was a mid-June checkpoint. **This is a real, actionable gap — the
eval harness is one cycle behind the catalog.**

> Method note (logged to the search-agent playbook): for catalog-size/count
> extractions over a cross-linked repo, name a single canonical artifact and make
> one agent the count-arbiter; treat secondary-surface counts as potentially-stale
> derivations, and treat the disagreement itself as a finding.

---

## 8. Follow-ups surfaced by this extraction

1. **FC51 orchestrator rule** (HANDOFF priority #1) — cherry-pick the spec-update
   commit into worktree bases before spawn, retiring the fragile brief-injection
   stopgap. (The 2026-06-21 `check_spec_provenance.py` BASEREF-FRESH change is the
   detection half of this.)
2. **Close the eval-harness ↔ catalog FC drift** (47 → 57): add scenarios/judges
   for FC48–FC57.
3. **Correct the "15 agents" → "31 agents" claim** wherever the largest-swarm
   figure is asserted from memory.
4. **Artifact-persistence guarantee** — always write smoke-test and flow-trace
   reports to `docs/reports/<run-id>/`, even on PASS.

---

## Source documents

**Skill / agents:** `.claude/skills/autopilot/SKILL.md`,
`.claude/agents/swarm-planner.md`, `.claude/agents/swarm-runner.md`,
`.claude/agents/spec-completeness-checker.md`.

**Tools:** `tools/check_spec_provenance.py`, `tools/verify_delegated_status.py`,
`check_ownership.py`, `eval-harness/spec_eval_gate.py`,
`eval-harness/pitfall_eval.py`, `eval-harness/mc_simulator.py`,
`eval-harness/validate_hardening.py`.

**Solutions:** `2026-04-09-autopilot-swarm-orchestration.md`,
`2026-05-20-autopilot-context-window-optimization.md`,
`2026-06-05-autopilot-context-death-delegation-architecture.md`,
`2026-06-06-autopilot-orchestration-hardening-A-reliability.md`,
`2026-06-07-autopilot-orchestration-hardening.md`,
`2026-06-01-spec-eval-gate-pre-swarm-validation.md`,
`2026-05-21-spec-completeness-checker-pre-swarm-gate.md`,
`2026-04-30-spec-convergence-loop.md`, plus all `*-swarm-build.md` build docs.

**Plans / brainstorms:** the `autopilot-context-death`, `orchestration-hardening`,
`swarm-scale`, `flask-swarm-acid-test`, and `pitfall-eval-harness` series in
`docs/plans/` and `docs/brainstorms/`.

**External:** `~/.claude/docs/agent-pitfalls.md` (FC1–FC57),
`~/.claude/docs/autopilot-tracking-template.md`,
`eval-harness/docs/multi-parallel-llm-mc-research.md`.
