---
title: "feat: G3 — Self-Audit Disconfirmer for Verification Diversity"
type: feat
status: completed
date: 2026-06-25
branch: feat/g3-verification-diversity
origin: docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md
governance_ref: docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md
feed_forward:
  risk: "Does an Opus disconfirmer reading the SAME run artifacts produce ORTHOGONAL findings, or just restate the Sonnet confirmer's concerns? Within-family (Opus vs Sonnet) is the WEAK diversity lever (self-preference bias); cross-family (Codex) is the strong one and is the pre-registered escalation."
  verify_first: true
---

# feat: G3 — Self-Audit Disconfirmer for Verification Diversity ✨

## Enhancement Summary

**Deepened on:** 2026-06-25 (7 parallel review/research agents: architecture, simplicity, agent-native,
pattern-recognition, autopilot-integrity, multi-file-sync, external best-practices).

**Key improvements folded in:**
1. **Cut the `disconfirmer_verdict` field + Gate 8d** (user decision) — it was cosmetic (DISPUTE-PASS →
   `_WITH_DEFERRED_RISK` is the *normal* terminal status) and contradicted the "no-LLM-in-dispose-path"
   invariant. The brainstorm's *intent* (a meta-objection can't be silently flattened) is preserved via
   the existing Gates 2/5/7f teeth. Gate 8 collapses from 4 sub-gates to 2 load-bearing ones.
2. **Closed the fail-open holes:** per-finding `D#→W<N>` identity link (was count-only, droppable);
   prescribed D# ingestion in `self-audit-reviewer` Step 2 (was unspecified → vacuous pass); canonical
   CONCUR sentinel + parse-failure fail-closed (truncated write was a silent pass).
3. **Made every Gate 8 check deterministic** (literal-token, mirroring Gate 7f) — removed the phantom
   `DISMISSED` disposition and the undecidable "explicit justification."
4. **Corrected the diversity narrative** (external research): within-family Opus-vs-Sonnet is the *weak*
   lever (self-preference bias is same-family); cross-family Codex promoted from "residual" to
   pre-registered escalation. Efficacy probe upgraded to measure novel-valid AND overcall rate.
5. **Named real omissions:** `verify_delegated_status.py` needs a new `--artifact-kind` (the change is
   NOT markdown-only); Gate 4 reconciliation; explicit spawn args + `bypassPermissions`; decimal
   sub-step `7.5`; all 4 gate-count sites.

**New consideration discovered:** the **disposition monoculture** — the lone Sonnet confirmer still
*disposes* the skeptic's findings — is the primary residual G3 leaves open (detection is diversified,
disposition is not). Elevated from R5 to a named residual.

## Plan Review (Codex — 2026-06-25): GO

External fresh-context Codex review returned **GO, no blockers**. It re-verified the load-bearing
contracts: TAIL_SYNC_POINT accounted for in both solo + swarm paths; `self-audit-reviewer` still uses
`ACCEPTED / PROMOTED / DEFERRED`; the new `disconfirmer.md` is treated as a freshness/run-id check, not a
status-bearing report. Only named residual = the pre-registered R2 (does the Opus disconfirmer produce
*orthogonal* findings vs restate the Sonnet audit) — bounded, verify-first, not a plan blocker. Cleared
for `/workflows:work`.

## Verify-First Result (2026-06-26): GATE PASSED

The feed-forward `verify_first` risk (R2 / Done #4 — does the Opus disconfirmer produce
*orthogonal, valid* findings or restate the Sonnet audit?) was **empirically cleared on
the first pass.** Opus generated candidate findings on historical runs 064/068/069/070
(069 = known-miss, generators hard-blocked from each run's `self-audit.md` + answer-key);
**cross-family Codex** judged validity (Opus never judged its own family). Result:
**Novel-valid 4/4 = 1.00, Overcall 0/25 = 0.00 → PASS** (bars: novel-valid > 0, overcall
< 0.34). The 069 headline known-miss confirmed: the disconfirmer independently re-derived
the FC50 unpinned-entrypoint class the later binding review caught. Zero brief-tuning
iterations used (3 allowed); no cross-family-standing-verifier escalation needed. Full
data + verbatim verdict: `docs/spikes/2026-06-25-g3-disconfirmer-efficacy-probe.md`.

## Code Review (Codex — 2026-06-26): GO

The implementation passed a fresh-context Codex CODE review. Initial pass returned
**NO-GO** with 3 findings (Gate 8c bijection not strict enough — `contains` allowed
merged rows + `D1`/`D10` collision; Gate 8a parse wording too loose; one stale "9 hard
gates" string in `autopilot/SKILL.md`). All fixed in commit `65954b4` (whole-cell Source
equality + merged-row/phantom-citation rejection + non-digit boundary on `#D<n>`; anchored
finding-row regex with an exhaustive accept/fail trichotomy; gate count → 8). A self-review
also caught + un-wrapped the line-wrapped sentinel in the disconfirmer agent. Codex
**RE-REVIEW = GO, no new findings**; invariants and the byte-identical sentinel confirmed.
Trail: `docs/handoffs/2026-06-26-g3-disconfirmer-{code-review,rereview}-codex-handoff.md`.

## Overview

Seat a **dedicated disconfirmer** (an Opus agent with an adversarial brief) at the autopilot's
**terminal verification surface** — immediately *before* the `self-audit-reviewer` step — to break the
**perspective monoculture** the governance scorecard marks ❌ "a risk we embody"
(`docs/governance/2026-06-21-...`, G3 row). The disconfirmer's job is to *prove the run is NOT
shippable*; its findings flow into the **existing WARN-disposition machinery** as mandatory WARNs the
self-audit must dispose, and a **new deterministic Gate 8** in `/verify-self-audit` enforces — by
literal-token, fail-CLOSED checks — that none are silently dropped. One pass, no loop, no LLM in the
dispose path, no LLM verdict with binding force.

**This plan carries forward every decision from** `docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md`,
**with one revision** (the `disconfirmer_verdict` field, cut after deepen-plan — see Sources/Origin).

## Problem Statement / Motivation

Today the terminal verdict is a **single Sonnet `self-audit-reviewer`** confirming a run is shippable.
A lone confirmer shares its own blind spots — no agent's *job is to disagree*. The G1 review loop was
field proof of the failure class: correlated reviewers (Codex + Claude, both "find any allowed input")
ran ~17 passes and could not self-terminate
(`docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md`, Update 2026-06-25, on the
`feat/g1-risk-tiered-firebreak` branch). The disconfirmer antidote is **proven in research fan-outs**
(`~/.claude/docs/search-agent-playbook.md`: SL5/SL8; "opus disconfirmer > sonnet extractors") but has
**never been carried into build-verification**. G3 does exactly that, for one surface.

## Proposed Solution

Five edits. **Four are greppable-markdown; one is a small Python change** (`verify_delegated_status.py`
— see item 5 — so the "markdown-only" framing of the original draft was wrong):

1. **New agent** `.claude/agents/self-audit-disconfirmer.md` (full frontmatter: `name`, `description`,
   `model: opus`, `tools: Read, Write, Grep, Glob`). Reads the run artifacts adversarially, writes
   `docs/reports/<run-id>/disconfirmer.md` with a `**Run ID:** <run-id>` header + timestamp and a
   findings table keyed with *local* IDs (`D1`, `D2`, … — disciplined like WARN keys; the disconfirmer
   never assigns global `<run-id>-W<N>` keys, avoiding FC34 races). No separate verdict field: **CONCUR
   ≡ zero findings (a canonical sentinel line present); DISPUTE ≡ ≥1 finding row.**
2. **Wire it BEFORE the self-audit** in both paths, respecting the `TAIL_SYNC_POINT` contract
   (`SKILL.md` ~992–999 — update the comment's enumeration to list the disconfirmer):
   - Solo: `.claude/skills/autopilot/SKILL.md`, before `### Self-Audit` (~line 1153).
   - Swarm: `.claude/agents/tail-runner.md`, as a **decimal sub-step `Step 7.5`** between Step 7 and
     Step 8 (a renumber would break cross-refs like `SKILL.md:1078`).
   - Spawn with **explicit args** `(run_id, reports_dir, plan_path, build_tracking_path, handoff_path)`
     and **`mode: "bypassPermissions"`** (FC50 — pin the entrypoint, no discovery heuristics), matching
     the Step 8 self-audit spawn block.
3. **Extend `self-audit-reviewer.md`** (stays `model: sonnet` — invariant):
   - **Step 2 (Collect WARNs):** add `disconfirmer.md` as a current-run WARN source — scan its findings
     table and create **one WARN row per `D#`**, with **`Source = disconfirmer.md#D<n>`** (the
     per-finding identity link Gate 8 needs) and the finding's **severity inherited verbatim** into the
     row / Unresolved Risk (so a HIGH finding DEFERRED under an A grade trips the existing Gate 7f for
     free).
   - **Step 4 (template) + Source Reconciliation:** reconcile `disconfirmer.md` (its "WARN Tokens
     Found" count = number of `D#` rows, NOT `WARN/STATUS` token lines) so Gate 4 doesn't trip on the
     new file.
   - (No verdict field, no DISPUTE-PASS status rule — cut with the verdict.)
4. **New Gate 8** in `.claude/skills/verify-self-audit/SKILL.md` (after 7f, before `## Output`) —
   **deterministic, fail-CLOSED, two load-bearing sub-checks** (see below). Bump **all four** gate-count
   sites consistently: frontmatter `description` (~:3), "Run all N checks" preamble (~:26), and the two
   success lines (~:239, ~:241). *(Note the pre-existing mislabel: the file says "9" while defining 7
   gate headings; adding Gate 8 → set all four sites to the literal heading count "8" to resolve it.)*
5. **`tools/verify_delegated_status.py`** — add a new `--artifact-kind disconfirmer`
   (existence + freshness `mtime ≥ run_start_ts` + run-id match; **no `**Status:**` marker** — the
   disconfirmer has no `STATUS:` line). Called at swarm **Step 18w** alongside the existing self-audit
   disk-verify.

### Why this approach (carried from brainstorm)

- **Scope = self-audit only** (not the `/workflows:review` mix, not the spec gates). Highest-leverage
  single surface; bounded "done." *(see brainstorm: Decision 1)*
- **Opus disconfirmer.** Because the confirmer is **Sonnet**, an Opus disconfirmer adds role diversity
  (disconfirm vs confirm) **and** model diversity (Opus vs Sonnet). **But heed the evidence:** Opus and
  Sonnet are the *same family*, so self-preference bias (arXiv 2410.21819) is *not* neutralized by this
  axis — within-family model diversity is the **weak** lever, role diversity is genuine, and **cross-
  family (Codex) is the only strong lever**. Codex is therefore a **pre-registered escalation** (see
  Done #4 / R2), not an open-ended "residual." All Anthropic models here are standard tier (Max-covered;
  never Sonnet-1M). *(see brainstorm: Decision 2, narrative corrected by deepen-plan)*
- **Option-A adjudication.** Disconfirmer runs **first/independent** → findings become mandatory WARNs
  the self-audit disposes → deterministic Gate 8 enforces every finding is linked + disposed. No new
  blocking path, no arbiter, no re-run loop, **no LLM verdict with binding force.** *(see brainstorm:
  Decision 3; the verdict field that would have added binding force is cut.)*
- **Determinism boundary held — now strictly.** The disconfirmer is advisory (LLM findings); ALL
  enforcement is literal-token deterministic in Gate 8. *(see brainstorm: Decision 4)*
- **Before-placement is the bias-correct choice, not just convenient.** Running the disconfirmer
  *blind to* the self-audit verdict avoids anchoring/confirmation bias (arXiv 2412.06593, 2603.18740) —
  CoT does not undo an anchor once seen. It stays an independent reviewer, not an anchored one.

## Technical Approach

### Architecture (one pass, before the audit)

```
... Verify BUILD_TRACKING.md (existing gate)
      │
      ▼
[NEW] self-audit-disconfirmer  (model: opus, adversarial brief, explicit args, bypassPermissions)
      │   reads run artifacts (ground-truth) → writes docs/reports/<run-id>/disconfirmer.md
      │   { **Run ID:** <id> + ts ; findings D1..Dn (or canonical CONCUR sentinel) }
      ▼
self-audit-reviewer (model: sonnet, existing)
      │   Step 2: ingests each D# → one WARN row, Source=disconfirmer.md#D<n>, severity verbatim; disposes
      ▼
/verify-self-audit  (Gates 1–7 + [NEW] Gate 8, deterministic, literal-token, fail-CLOSED)
      ▼
... Done   (swarm: Step 18w disk-verify confirms disconfirmer.md freshness via new --artifact-kind)
```

### Disconfirmer agent brief (the orthogonal lens — the load-bearing part)

- **Mandate:** *"Assume this run should NOT ship. Find the strongest reasons it is not shippable that a
  competent-but-bounded confirming reviewer would miss."*
- **Ground-truth required (else discard):** every finding MUST cite the specific on-disk artifact
  (`file:line` or artifact name) it was derived from. A finding grounded only in a STATUS line / summary
  prose is **invalid** and must not be emitted. *(playbook Ground-truth verifier; debate gains require
  grounded critiques — arXiv 2510.20963)*
- **Positive hunting targets (illustrative, NOT exhaustive — do not turn into an enumerated denylist):**
  scope/convergence creep; artifacts *claimed but absent on disk*; cross-section contradictions; claims
  unbacked by artifacts. Hunting a checklist of *positive* classes improves recall without recreating
  the enumerated-exclusion trap.
- **Current-run scope only:** do NOT surface pre-existing backlog / HANDOFF "Deferred Items (from prior
  work)." A clean run must pass even with a large backlog.
- **One pass, name a class:** findings name a *class* of problem, not whack-a-mole line items. The
  disconfirmer runs **once** — it is not a loop.
- **Output contract (parseable for both an agent and a grep):**
  - Header: `**Run ID:** <run-id>` (bold, matching house style) + an ISO timestamp line.
  - Findings table: `| D# | Category | Why this threatens shippability (with file:line) | Severity |`.
    - `D#` = `D<N>`, integer, **sequential from 1, no gaps, no zero-pad**, as the **first table cell**
      (anchored regex `^\|\s*D\d+\s*\|`) so a stray "D3" in prose can't match.
    - Severity ∈ **exactly `LOW | MEDIUM | HIGH`** (match the existing Unresolved-Risk vocabulary; no
      `MED`).
  - **Canonical no-findings sentinel** (CONCUR): a required literal line `No disconfirmer findings.` and
    zero `D#` rows. (A header-only/truncated write with neither rows nor sentinel ⟹ Gate 8 FAIL — not a
    silent CONCUR.)
  - Tools: `Read, Write, Grep, Glob`. No `STATUS:` output-contract line (completion is enforced
    downstream by Gate 8a fail-closed).

### Gate 8 — deterministic, fail-CLOSED (2 load-bearing sub-checks)

Markdown-instruction checks (consistent with Gates 1–7), via Read/Grep/Glob:
- **8a — Exists, identity, parseable (fail-closed):** `docs/reports/<run-id>/disconfirmer.md` exists
  (Glob) AND its header contains the literal `**Run ID:** <run-id>` AND (the findings table is parseable
  with recognizable `^| D<n> |` rows **OR** the canonical `No disconfirmer findings.` sentinel is
  present). **Missing / mismatched / unparseable ⟹ FAIL** (never pass — the skeptic is mandatory; a
  malformed write is not "zero findings"). *(FC10 fail-closed; FC52 identity)*
- **8c — Per-finding bijection + dismissal token:** for **every** `D<n>` row in `disconfirmer.md` there
  must exist **exactly one** WARN row in `self-audit.md` whose `Source` contains the literal
  `disconfirmer.md#D<n>`. For any such WARN disposed **`ACCEPTED`** (the "dismiss" set — `ACCEPTED` =
  real-but-tolerated; state this explicitly), its Rationale must contain the literal token `#D<n>`
  (presence check only, mirroring 7f's literal-`HIGH`+key pattern — **Gate 8c checks token presence,
  never justification quality**). Disposition-enum + non-empty-rationale validation is NOT repeated here
  (Gate 2 owns it). *(closes the count-parity fail-open; no phantom `DISMISSED` disposition.)*
- **Swarm freshness (Step 18w):** the new `verify_delegated_status.py --artifact-kind disconfirmer`
  disk-verifies `disconfirmer.md` (mtime ≥ run_start_ts + run-id). Solo relies on Run ID match +
  structural in-tail freshness (the disconfirmer runs as a step in the same tail invocation, writing to
  the per-run dir); the manual "copy a prior run's file and edit its Run ID" case is **out of the
  unattended threat model** (declared residual). *(harness-green ≠ live)*

### System-Wide Impact

- **Interaction graph:** new Opus spawn in the Shared Tail, one pass before the existing Sonnet audit.
  Solo runs it inline; swarm runs it inside `tail-runner` (Step 7.5), disk-verified at `SKILL.md` 18w.
- **Error propagation:** disconfirmer crash / empty / malformed output → Gate 8a FAIL → run fails
  (fail-closed). Note: **solo fail-closed is only as strong as the orchestrator reaching `/verify-self-audit`**
  — if context drift skips *both* the spawn and the gate, there is no new backstop (same class as the
  pre-existing self-audit risk; not a regression). Swarm is backstopped by Step 18w disk-verify.
- **State lifecycle:** one new artifact per run, namespaced under `docs/reports/<run-id>/` (FC5/FC34: no
  parallel-run collision). Partial-tail abort after the disconfirmer but before the audit relies on the
  existing run-state guard (no new mechanism added; flagged as a known boundary).
- **API-surface parity:** solo and swarm are the parity surface; `TAIL_SYNC_POINT` forces both edits.
  Drift is the top risk (R1) — the acceptance check asserts *ordering*, not just string presence.

## What Must NOT Change (invariants)

- **Gates 1–7 of `/verify-self-audit` and their semantics** — Gate 8 is additive only.
- **The `self-audit-reviewer` model stays Sonnet** (latent finding: it audits Opus work with a weaker
  model — out of scope; would breach the pre-registered "done"). *(see brainstorm: Latent finding)*
- **No LLM enters the deterministic dispose path, and no LLM verdict has binding force.** Gate 8 is
  literal-token deterministic; the disconfirmer is advisory only. *(strengthened by cutting the verdict.)*
- **No re-run / convergence loop.** Disconfirmer runs exactly once per run.
- **Current-run WARN scoping** — the disconfirmer must not downgrade a clean run with pre-existing
  backlog.
- **Existing WARN-key convention** (`<run-id>-W<N>`) and disposition enum **`ACCEPTED / PROMOTED /
  DEFERRED`** — **VERIFIED** during deepen-plan (`self-audit-reviewer.md:106-112`, `verify-self-audit/SKILL.md:57`).
  No `DISMISSED` value exists; Gate 8c uses `ACCEPTED` as the dismissal set.

## Acceptance Tests (EARS)

Format: `WHEN [condition] THE SYSTEM SHALL [behavior]`. Run all checks against a **fixture run copied to
`/tmp` first — never mutate real run reports.**

### Happy path
- WHEN the disconfirmer finds no blocking issues THE SYSTEM SHALL write `disconfirmer.md` containing the
  literal `No disconfirmer findings.` sentinel and zero `D#` rows, and Gate 8 SHALL pass.
  - Verify: `grep -c 'No disconfirmer findings\.' docs/reports/<run-id>/disconfirmer.md` → `1`
- WHEN the disconfirmer raises findings `D1..Dn` THE SYSTEM SHALL cause `self-audit.md` to contain, for
  each `D<n>`, exactly one WARN row whose Source contains `disconfirmer.md#D<n>`, disposed per the enum.
  - Verify (bijection, not count): for each `D<n>` in `disconfirmer.md`,
    `grep -c "disconfirmer.md#D<n>" docs/reports/<run-id>/self-audit.md` → `1`.
- WHEN both solo and swarm tails run THE SYSTEM SHALL invoke the disconfirmer **before** the self-audit
  in each path.
  - Verify (ordering, not just presence): in `SKILL.md` the `self-audit-disconfirmer` block appears
    before `### Self-Audit`; in `tail-runner.md` `Step 7.5` appears before `Step 8`.
    `grep -n 'self-audit-disconfirmer\|### Self-Audit' .claude/skills/autopilot/SKILL.md` shows the
    disconfirmer line first; same idea for `tail-runner.md` Step 7.5 vs Step 8.

### Error cases
- WHEN `disconfirmer.md` is missing, its `**Run ID:**` mismatches, or its table is unparseable (no `D#`
  rows AND no sentinel) THE SYSTEM SHALL FAIL Gate 8a.
  - Verify: with the file absent, `/verify-self-audit <run-id> docs/reports/<run-id>/` → `STATUS: FAIL`.
- WHEN a `D<n>` finding has no matching `disconfirmer.md#D<n>` WARN row in `self-audit.md` THE SYSTEM
  SHALL FAIL Gate 8c (dropped-finding fail-open closed).
  - Verify: a fixture omitting one `#D<n>` row → `STATUS: FAIL`.
- WHEN a `D<n>` WARN disposed `ACCEPTED` lacks the literal `#D<n>` token in its Rationale THE SYSTEM
  SHALL FAIL Gate 8c.
  - Verify: a fixture ACCEPTED row without `#D<n>` in Rationale → `STATUS: FAIL`.
- WHEN a disconfirmer **HIGH** finding is DEFERRED under an **A** grade without its key cited THE SYSTEM
  SHALL FAIL the existing **Gate 7f** (the inherited-severity teeth).
  - Verify: a fixture with a DEFERRED+HIGH disconfirmer WARN, grade A, no key in Justification → `FAIL`.
- WHEN the disconfirmer (Opus) agent is unavailable THE SYSTEM SHALL fail the run, NOT fall back to a
  pass. *(agent pins standard `opus` via frontmatter — Max-covered, never Sonnet-1M.)*

### Verification commands
- `grep -n 'Gate 8' .claude/skills/verify-self-audit/SKILL.md` — Gate 8 present
- `grep -cn '\b8\b gates\|all 8' .claude/skills/verify-self-audit/SKILL.md` — all 4 count sites updated
- `grep -n 'self-audit-disconfirmer' .claude/skills/autopilot/SKILL.md .claude/agents/tail-runner.md` — both wired
- `grep -n 'model: opus' .claude/agents/self-audit-disconfirmer.md` — Opus pinned, Max-covered
- `grep -n 'artifact-kind disconfirmer\|disconfirmer' tools/verify_delegated_status.py` — new kind added
- `head -8 .claude/agents/self-audit-reviewer.md` — confirm it still says `model: sonnet` (invariant)

## Success Metrics

- First real swarm run (env permitting) produces a fresh `disconfirmer.md`; Gate 8 passes/fails
  deterministically; the run is **not** ungoverned. (Failure mode = a halted run, not a silent pass.)
- **Efficacy probe (the feed-forward risk — upgraded):** run the disconfirmer on a **batch of 3–5
  historical `docs/reports/*/self-audit.md`**, including **≥1 known-miss case** (e.g. a run where a later
  review found a real gap). Report two numbers, validity judged by a **human or a cross-family model
  (never the Opus disconfirmer's own family** — self-preference):
  - **Novel-valid rate** = findings absent from the original audit AND judged valid (must be **> 0**).
  - **Overcall rate** = invalid findings / total findings (must be **< a pre-chosen threshold** — an
    "assume not shippable" prior trivially inflates novelty, so overcall must be bounded).
  - If Novel-valid = 0 OR Overcall exceeds threshold after ≤3 brief-tuning passes → **trigger the Codex
    cross-family escalation** (NOT a bigger single model, NOT a loop — single-model capacity is not the
    bottleneck; verifier *diversity* is. arXiv 2509.17995 / 2506.18203).

## Dependencies & Risks / Mitigation

- **R1 — TAIL_SYNC drift (highest):** editing only one of solo/swarm, or wiring the disconfirmer in the
  wrong *order*. *Mitigation:* the EARS **ordering** check (not just `grep -l` presence); update the
  `TAIL_SYNC_POINT` comment enumeration; treat as P1 in review.
- **R2 — Non-orthogonality / within-family ceiling (the feed-forward risk):** Opus may restate Sonnet
  (self-preference, and the hardest misses — cross-section contradictions — are the regime where even a
  strong verifier plateaus, arXiv 2509.17995). *Mitigation:* the upgraded efficacy probe (novel-valid +
  overcall) gates this; cross-family Codex is the **pre-registered** next move if it fails.
- **R3 — Fail-open regression:** a future edit lets a missing/malformed artifact pass. *Mitigation:*
  Gate 8a is explicitly fail-closed incl. parse-failure; EARS error-cases pin it.
- **R4 — Latency/token cost:** a second tail pass (Opus) per unattended run. *Mitigation:* one pass only,
  no loop; note in the compound doc for cost tracking.
- **R5 (PRIMARY RESIDUAL) — Disposition monoculture:** G3 diversifies *detection* but the **same lone
  Sonnet confirmer still disposes** the disconfirmer's findings — the orthogonal lens hands its verdict
  back to the monoculture it was meant to diversify, and nothing checks whether a disposition was
  *correct* (only that it exists and is token-linked). Diversifying *disposition* is explicitly out of
  scope for G3 and is the real residual it leaves open. *(declared, not solved.)*
- **R6 — Sequencing limitation:** running *before* the audit means the disconfirmer critiques the **run**,
  not the audit's **disposition judgment**; catching audit-judgment errors would need an after-pass (a
  loop) — explicitly rejected. Declared residual (subsumed by R5).

## Pre-registered "Done" (stopping discipline — from the G1 retro)

Done =
1. `self-audit-disconfirmer.md` agent exists (`model: opus`, full frontmatter, explicit args,
   `bypassPermissions`) and runs **before** the self-audit in **both** paths (ordering-verified);
2. its findings are ingested as WARNs (`Source = disconfirmer.md#D<n>`, severity verbatim) the
   self-audit disposes;
3. Gate 8 (8a + 8c, fail-closed, literal-token) + `verify_delegated_status.py --artifact-kind
   disconfirmer` (swarm) enforce existence, identity, parseability, and the per-finding bijection;
4. the efficacy probe (3–5 historical reports incl. a known-miss) shows **Novel-valid > 0** and
   **Overcall < threshold**; if not, the Codex cross-family escalation is triggered.

**Tell-to-stop:** if a change "adds another reviewer" without changing the *perspective distribution*,
adds a re-run loop, gives an LLM verdict binding force, or creeps to the review mix / spec gates — stop
and re-scope. Hard pass-cap on brief-tuning iterations: **3**; beyond it, write a "why isn't it
orthogonal?" diagnosis and escalate to cross-family, do not tweak again.

## File-by-file change list (pseudo)

- `.claude/agents/self-audit-disconfirmer.md` — NEW. `name`/`description`/`model: opus`/`tools: Read,
  Write, Grep, Glob`; adversarial brief + output contract above.
- `.claude/skills/autopilot/SKILL.md` — insert disconfirmer spawn block (explicit args,
  `bypassPermissions`) before `### Self-Audit` (~1153); update the `TAIL_SYNC_POINT` comment enumeration.
- `.claude/agents/tail-runner.md` — insert disconfirmer as **Step 7.5** (decimal, not renumber) before
  Step 8; mirror solo; update its `TAIL_SYNC_POINT` comment copy.
- `.claude/agents/self-audit-reviewer.md` — Step 2 gains the disconfirmer-`D#`-ingestion rule
  (`Source = disconfirmer.md#D<n>`, severity verbatim); Step 4 / Source Reconciliation gains the
  `disconfirmer.md` row (count = `D#` rows). **No verdict field.** Stays `model: sonnet`.
- `.claude/skills/verify-self-audit/SKILL.md` — add `### Gate 8` (8a + 8c); bump all **four** gate-count
  sites (~:3, ~:26, ~:239, ~:241) to "8".
- `tools/verify_delegated_status.py` — add `--artifact-kind disconfirmer` (existence + freshness +
  run-id; no `**Status:**` marker); call it at `SKILL.md` Step 18w.
- (test fixtures) `/tmp` copies of a real run's `docs/reports/<run-id>/` for the EARS error-cases —
  never mutate real run reports.

## Sources & References

### Origin
- **Brainstorm:** [docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md](docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md)
  — carried decisions: scope=self-audit-only; Opus disconfirmer (role+model diversity, confirmer is
  Sonnet); Option-A adjudication (mandatory WARNs + deterministic teeth, no loop).
  - **REVISED decision (deepen-plan, 2026-06-25):** the brainstorm's dedicated `disconfirmer_verdict`
    field is **cut**. It was cosmetic (DISPUTE-PASS → the *normal* `_WITH_DEFERRED_RISK` status) and
    contradicted the "no-LLM-in-dispose-path" invariant (a soft form of the rejected unilateral-block).
    The intent ("a meta-objection can't be silently flattened") is preserved by routing findings through
    the existing Gates 2/5/7f. User-approved.

### Internal references (verified during planning + deepen-plan)
- `.claude/agents/self-audit-reviewer.md` — `model: sonnet`; WARN table `| # | Key | Source | WARN
  Description | Disposition | Rationale |` (:102); enum `ACCEPTED/PROMOTED/DEFERRED` (:106-112); keys
  `<run-id>-W<N>` (:63-66); pipeline statuses (:72-77), `_WITH_DEFERRED_RISK` = "expected for most runs."
- `.claude/skills/verify-self-audit/SKILL.md` — Gates 1–7 (7a–7f), markdown-instruction, no schema file;
  Gate 2 enum/rationale (:57,65-70); Gate 4 reconciliation (:88-99); Gate 7f literal-token (:220-234);
  count sites (:3,:26,:239,:241).
- `.claude/skills/autopilot/SKILL.md` — Shared Tail; solo spawn (~1154); swarm Step 17w/18w disk-verify
  (`verify_delegated_status.py`, :967-999); `TAIL_SYNC_POINT` asymmetric (:992-999).
- `.claude/agents/tail-runner.md` — swarm tail Steps 7–10; self-audit spawn `subagent_type:
  "self-audit-reviewer"`, `mode: "bypassPermissions"` (:197-204); "no discovery heuristics" (:33-39).
- `tools/verify_delegated_status.py` — current `--artifact-kind self-audit` checks `**Status:**` (no
  disconfirmer kind yet).
- `docs/reports/070/self-audit.md` — ground-truth sample.

### Prior-art learnings (gotchas designed around)
- `docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md` (g1) — field proof + stopping
  discipline; positive hunting targets, not enumerated exclusions.
- `docs/solutions/2026-06-25-g1-firebreak-activation-arc.md` (g1) — gate-wiring; positive-control probe;
  harness-green ≠ live; disk authority.
- `docs/solutions/2026-04-30-spec-convergence-loop.md` — diversity-as-blind-spot-coverage; human pass.
- `docs/solutions/2026-05-13-sandbox-autonomy-hardening.md` — current-run WARN scoping.
- `~/.claude/docs/agent-pitfalls.md` — FC10, FC34/FC5, FC50, FC52, FC11.
- `~/.claude/docs/search-agent-playbook.md` — Disconfirmer + Ground-truth-verifier roles.

### External research (deepen-plan, independent/academic — vendor claims excluded)
- Self-preference bias in LLM-judges (within-family): arXiv 2410.21819, 2506.02592.
- Self-correction without external feedback degrades: arXiv 2310.01798 (ICLR 2024).
- Same-model debate ≈ self-consistency; diversity/grounded critiques drive gains: arXiv 2510.20963.
- Anchoring/confirmation bias (vindicates blind before-placement): arXiv 2412.06593, 2603.18740.
- Critique precision/recall benchmarks (efficacy-probe design): arXiv 2402.13764, 2402.14809, 2501.14492.
- Verifier ceiling on hard problems; ensemble-of-diverse > single-strong: arXiv 2509.17995, 2506.18203,
  2502.20379.

## Feed-Forward

- **Hardest decision:** Whether the disconfirmer's meta-objection needed its own binding `disconfirmer_verdict`
  field. The brainstorm said yes; deepen-plan showed the field was cosmetic *and* contradicted the
  determinism invariant (binding LLM verdict). Resolved by **cutting it** and preserving the intent via
  the existing Gates 2/5/7f teeth — diversity of *detection* with deterministic, non-LLM enforcement.
- **Rejected alternatives:** (a) the learnings research's **re-run loop** — re-entry into the G1
  convergence trap; (b) a binding verdict / unilateral-BLOCK disconfirmer — puts an LLM back in the
  dispose path; (c) bumping the self-audit-reviewer to Opus — scope creep (latent finding); (d)
  diversity-by-downgrade (Sonnet/Haiku disconfirmer) — weaker skeptic, and moot (confirmer is Sonnet).
- **Least confident (verify first):** Whether an Opus disconfirmer on the *same* artifacts yields
  *orthogonal*, *valid* findings or restates the Sonnet audit — and the evidence says within-family is
  the weak lever. The upgraded efficacy probe (novel-valid + overcall, cross-family-judged) is the gate;
  cross-family Codex is the pre-registered escalation.

## Codex Handoff Prompt (Plan Review — paste into a fresh Codex context)

```
You are reviewing an IMPLEMENTATION PLAN (not code) for a fresh, skeptical second opinion before any
code is written. Repo: ~/Projects/sandbox, branch feat/g3-verification-diversity.

Plan: docs/plans/2026-06-25-feat-g3-self-audit-disconfirmer-plan.md
Origin brainstorm: docs/brainstorms/2026-06-25-g3-verification-diversity-brainstorm.md

What it does: an Opus "disconfirmer" agent runs BEFORE the Sonnet self-audit-reviewer in the autopilot
tail; its findings become mandatory WARNs the self-audit disposes (Source=disconfirmer.md#D<n>); a new
deterministic fail-CLOSED Gate 8 (8a existence/identity/parseable + 8c per-finding bijection & dismissal
token) enforces them. One pass, no loop, NO LLM verdict with binding force, no LLM in the dispose path.
Scope = self-audit surface only. This plan has already been through a 7-agent deepen-plan pass; the
disconfirmer_verdict field was CUT.

Verified facts to assume: /verify-self-audit is pure markdown-instruction gates (no schema); disposition
enum is exactly ACCEPTED/PROMOTED/DEFERRED (no DISMISSED); WARN keys <run-id>-W<N>; solo (SKILL.md
~1153) and swarm (tail-runner Step 7.5) kept in sync by TAIL_SYNC_POINT (BOTH must be edited);
self-audit-reviewer stays model: sonnet; verify_delegated_status.py needs a new --artifact-kind
disconfirmer (this is the one non-markdown change).

Look hardest for, and return as P0/P1/P2 with file:line + concrete fix + a GO/NO-GO:
1. TAIL_SYNC drift / wrong ORDER (disconfirmer must precede the audit in both paths).
2. Fail-OPEN holes — any path where missing/stale/malformed/partial disconfirmer.md still PASSes,
   including solo (no Step 18w) freshness and partial-tail-abort.
3. Determinism leaks — any LLM judgment that ends up enforced (Gate 8 must be literal-token only).
4. The per-finding bijection (8c) — is the disconfirmer.md#D<n> identity link actually unforgeable and
   greppable? Any way the Sonnet reviewer can drop/duplicate a finding and still pass?
5. The verify_delegated_status.py extension — sound? (new kind has no **Status:** marker.)
6. Whether cutting the verdict field lost any LEGITIMATE capability the brainstorm wanted.
7. Cross-section contradictions between plan, brainstorm, and the verified contracts.
8. Convergence/stopping-discipline gaps; whether the efficacy probe (novel-valid + overcall) is sound.

Return a prioritized findings list + GO/NO-GO for proceeding to /workflows:work.
```
