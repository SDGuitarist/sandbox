---
title: "Autopilot Orchestration Hardening — Plan A (Reliability Fixes)"
date: 2026-06-06
phase: plan
status: reviewed-ready
swarm: false
source_brainstorm: docs/brainstorms/2026-06-06-autopilot-orchestration-hardening-brainstorm.md
decision_review: docs/brainstorms/2026-06-06-orchestration-hardening-CODEX-DECISION-verification.md
feed_forward:
  risk: "Item 1 changes the run's terminal pass/fail gate; a wrong fix opens a stale-STATUS false-PASS hole (a prior aborted run's PASS artifact at a reused run-id path) OR a false-FAIL (mis-parsing the self-audit status format)."
  verify_first: true
---

# Plan A — Reliability Fixes (Disk-Verify Delegated STATUS + Worker Roster)

**Scope:** Items 1–2 from the Run 068 retrospective brainstorm. Items 3–4 are Plan B.
**Verification decision (resolved by Codex review):** **Hybrid (A)** — automate item 1
with a fixture-driven verifier; verify item 2 with a documented manual repro.

---

## Deepening Findings (2026-06-06)

Four research/review agents (solution-doc, simplicity, architecture, best-practices)
deepened this plan. Material corrections folded in:

1. **[P0] `self-audit.md` has no line-1 STATUS.** Line 1 is a heading
   (`# Self-Audit Report -- Run <run-id>`). The verdict is `**Status:** <PIPELINE_PASS
   | PIPELINE_PASS_WITH_DEFERRED_RISK | PIPELINE_FAIL>` under `## Final Run Status`
   (self-audit-reviewer.md:82-95; confirmed in `docs/reports/068/self-audit.md`).
   `assembly-summary.md` *does* use `STATUS: PASS` on line 1 (swarm-runner.md:146-149).
   → The verifier needs **per-artifact STATUS extraction**, not one "line 1" rule.
2. **[P0] `PIPELINE_PASS_WITH_DEFERRED_RISK` is a PASS.** Run 068 shipped with it.
   The verifier accepts both `PIPELINE_PASS` and `PIPELINE_PASS_WITH_DEFERRED_RISK`
   as pass for self-audit; binary PASS/FAIL was wrong.
3. **[P1] run-id cross-check is free.** Both artifacts already embed the run-id
   (`**Run ID:**` in self-audit; heading in assembly-summary), so a `--run-id` match
   costs zero producer edits. Made load-bearing (was wrongly rejected before).
4. **[P1] `run_start_ts` schema owner is the Step 1 Run State block** (SKILL.md:127-133),
   not the global template. Declared there; written in Step 5.5.
5. **[P2] Single source of truth.** `/verify-self-audit` already adjudicates
   `self-audit.md` (incl. CLAUDE.md Gate 7f DEFERRED+HIGH rules). The verifier must
   confirm only **existence + freshness + run-id + non-FAIL terminal status** and must
   NOT re-adjudicate deferred-risk disposition.
6. **[Simplicity] Roster is 4 columns** (dropped the constant `Spawn Status` column).
7. **[Best-practices] Verifier mechanics:** distinct exit codes 1–5 per failure reason;
   `os.stat().st_mtime_ns >= run_start_ts*1e9` (exact int, `>=`); STATUS parsing
   anchored to line start with exact-token match; fail-closed on every ambiguous path.

---

## Plan Review (Codex, 2026-06-06)

**Outcome: CLEAN — 0 P0, 0 P1.** All P2 items were confirmations, not defects:
- `assembly-summary.md` reliably exists on swarm-runner PASS; `{PASS}` accept-set correct
  (swarm-runner.md:146).
- self-audit accept-set `{PIPELINE_PASS, PIPELINE_PASS_WITH_DEFERRED_RISK}` matches the
  reviewer contract (self-audit-reviewer.md:95).
- Mirror coverage complete (both TAIL_SYNC_POINT comments, tail-runner Output Contract
  note, Step 18w crash branch).
- Single-source-of-truth split clean — no live disagreement path between
  `verify_delegated_status.py` and `/verify-self-audit`.
- The residual stale-artifact hole is accepted as an explicit, documented tradeoff
  (sound for a single-host sandbox; revisit trigger recorded). Ship the per-run nonce
  only if eliminating every false-PASS path becomes the goal.

Codex verdict on the work prompt: **"No changes needed."**

---

## Plan Quality Gate

### 1. What exactly is changing?

**Item 1 — Disk-verify delegated STATUS (the terminal-gate fix).**

The orchestrator delegates two heavy phases to fresh-context agents and currently trusts
each agent's **echoed (wire) STATUS line** as the verdict:

- **Steps 11w–16w handler** trusts the **swarm-runner** wire STATUS (artifact:
  `docs/reports/<run-id>/assembly-summary.md`, `STATUS: PASS` on line 1).
- **Step 18w** trusts the **tail-runner** wire STATUS (artifact:
  `docs/reports/<run-id>/self-audit.md`, `**Status:**` under `## Final Run Status`).

Today, if an agent does all its work but **forgets to echo its Output Contract**,
Step 18w fails a successful run ("TAIL AGENT INCOMPLETE: no STATUS line"). The fix moves
authority to the **on-disk artifact**, with the wire STATUS demoted to a logged hint.

Changes:

1. **Declare `run_start_ts` in the Step 1 Run State block** (SKILL.md:127-133) and
   **capture it (epoch seconds) in Step 5.5**, written via Edit alongside `run_id`.
   This is the freshness reference the staleness check needs. *(New — nothing records
   run start time today.)*
2. **New shared script `tools/verify_delegated_status.py`** — the single deterministic
   disk-verify routine. Inputs: `--artifact <path> --artifact-kind self-audit|assembly
   --run-start-ts <epoch> --run-id <id> [--wire-status <text>]`. Exit `0` = PASS,
   distinct non-zero per failure reason (see Design Detail). The artifact on disk is
   authoritative; the wire STATUS is logged but never changes the verdict.
3. **Rewrite Step 18w** to invoke the script against `self-audit.md`
   (`--artifact-kind self-audit`) instead of parsing the wire STATUS. Rewrite the
   existing "no STATUS line → FAIL" crash branch (SKILL.md:734-735) to defer to the
   script's artifact-existence result.
4. **Update the Steps 11w–16w handler** to invoke the script against
   `assembly-summary.md` (`--artifact-kind assembly`) **only on a PASS wire STATUS**.
   Blocking-FAIL classes (`contract-check:` / `merge-conflict:`) **short-circuit before
   any disk-verify** — they abort via wire STATUS + BUILD_TRACKING `final_status` and
   `assembly-summary.md` may not exist (swarm-runner.md:88-107). This preserves the
   existing escalation ordering (SKILL.md:682-686).
5. **Mirror in `tail-runner.md`** Output Contract note + **update BOTH TAIL_SYNC_POINT
   comments** (SKILL.md:745, tail-runner.md:49) to record that, after this change, the
   **swarm** tail trusts the on-disk artifact while the **solo** tail still trusts its
   own inline STATUS — a deliberate verification-authority asymmetry.

**Item 2 — `worker-roster.md` at spawn (write-only insurance).**

In **Step 10w**, immediately after the single-message parallel swarm spawn and
**before** awaiting any completion, write `docs/reports/<run-id>/worker-roster.md`
mapping each worker: `Role | Agent ID | Branch | Worktree Path`. Worktree branches are
named `worktree-agent-<agentId>`, not by role, so this mapping otherwise lives only in
volatile orchestrator context and is lost on a mid-spawn context death.

### 2. What must NOT change?

- **Solo path tail.** Solo runs the Shared Tail inline and produces `self-audit.md`
  itself — there is no *delegated* STATUS to verify. Solo verification is untouched.
- **Blocking failure classes.** `contract-check:` / `merge-conflict:` still abort the
  swarm-runner without merge/cleanup and end the run at the handler. Disk-verify never
  runs on a blocking-FAIL wire STATUS and never weakens a FAIL.
- **Self-audit adjudication ownership.** `/verify-self-audit` remains the sole authority
  on deferred-risk disposition. The new script reads the terminal status only; it does
  not re-check Gate 7f rules.
- **Artifact producers.** `self-audit.md` / `assembly-summary.md` are read, not changed.
  No edits to `self-audit-reviewer.md` or `swarm-runner.md` output *content* (only the
  handler that consumes the swarm-runner's STATUS changes).
- **Wire STATUS** stays as a logged hint. We only stop treating a *missing/garbled*
  wire STATUS as automatic FAIL when the on-disk artifact proves completion.
- **Item 2 is write-only.** No consumer reads `worker-roster.md` in this plan. (A
  future recovery consumer is explicitly deferred.)

### 3. How will we know it worked?

See `## Acceptance Tests` (EARS). Item 1 is proven by a deterministic fixture harness
covering all nine verifier cases (4 PASS: self-audit `PIPELINE_PASS` no-wire,
`PIPELINE_PASS_WITH_DEFERRED_RISK`, self-audit `PIPELINE_PASS` with contradicting wire,
assembly `PASS` with contradicting wire; 5 FAIL: missing, stale, run-id mismatch,
`PIPELINE_FAIL`, no-status-token). Item 2 is proven by a documented manual repro plus
opportunistic confirmation on the next real swarm build.

### 4. What is the most likely way this plan is wrong?

Two ways now, both narrowed by deepening:

- **False-FAIL via format mis-parse (was P0):** parsing the wrong line/token for
  `self-audit.md`. Mitigated by per-artifact extraction + a `PIPELINE_PASS_WITH_DEFERRED_RISK`
  fixture locking in the real format.
- **False-PASS via stale artifact at a reused run-id path:** the guard rests on
  `mtime ≥ run_start_ts` (+ run-id match), which closes the normal stale case (a prior
  aborted run's artifact has an *older* mtime). **ACCEPTED RESIDUAL RISK (not closed):**
  a prior run's artifact with a *future-dated* mtime under the *same reused run-id*
  would still pass — run-id match cannot distinguish it (run-ids are reused) and mtime
  cannot either (future-dated). This is consciously accepted, NOT fully mitigated. The
  only complete fix is a per-run nonce embedded by the producer agents
  (`self-audit-reviewer.md`, `swarm-runner.md`); that is deliberately **out of scope for
  Plan A** because it edits the artifact producers (which Plan A holds invariant — see
  §2). Acceptance rationale: the residual requires a backwards system clock on a
  single-host sandbox, which is near-impossible in this environment. **Revisit trigger:**
  ship the per-run nonce (new plan) if autopilot ever runs on multi-host / networked-FS
  infrastructure, or if any clock-skew anomaly is observed. No acceptance test covers
  this case — a green suite does NOT imply it is closed (see Acceptance Tests note).

---

## Design Detail

### `tools/verify_delegated_status.py` decision logic

The artifact on disk is the source of truth. Return **PASS (exit 0)** only when ALL
hold; otherwise return a distinct non-zero code with a reason on stderr:

| Check | Pass condition | Fail exit |
|-------|----------------|-----------|
| Exists & readable | `os.stat`/open succeeds | `2` EXIT_MISSING |
| Fresh | `st_mtime_ns >= run_start_ts*1e9` (`>=`) | `3` EXIT_STALE |
| Run-id match | embedded run-id == `--run-id` | `6` EXIT_RUNID_MISMATCH |
| Status parses | a recognized terminal status token found | `4` EXIT_NO_STATUS |
| Status is non-FAIL | see per-kind accept-set below | `1` EXIT_FAIL_STATUS |

**Per-artifact STATUS extraction (`--artifact-kind`):**
- `self-audit`: find the `**Status:**` line under `## Final Run Status`. Accept-set =
  {`PIPELINE_PASS`, `PIPELINE_PASS_WITH_DEFERRED_RISK`}. `PIPELINE_FAIL` → fail.
- `assembly`: first line matching `^\s*STATUS:\s*(\S+)`. Accept-set = {`PASS`}.

**Wire STATUS is logged, never decisive.** A fresh, run-id-matching, non-FAIL artifact
is PASS even if `--wire-status` says FAIL (the wire is the known-unreliable channel —
letting it veto would reintroduce the false-FAIL this plan kills). A missing/stale/FAIL
artifact is FAIL even if the wire says PASS. *(This matches Codex's resolved matrix:
disk always wins in both directions. The best-practices "wire-can-veto" suggestion was
deliberately NOT adopted — flagged for Codex review.)*

**Mechanics (best-practices):** `st_mtime_ns` integer compare; exit codes kept in 1–255
(256 wraps to 0 = false pass); STATUS regex anchored with `re.MULTILINE`, exact-token
(`token == "PASS"`, not substring, so `BYPASS` can't match); top-level
`try/except` → non-zero so an unexpected crash never reads as success.

### Invariants (do not weaken during implementation)

These three are the load-bearing contract of item 1. An implementation that violates any
of them is wrong even if the tests pass:

1. **`tools/verify_delegated_status.py` checks only terminal status, freshness, and
   run-id.** It never re-adjudicates anything else.
2. **`/verify-self-audit` remains the sole authority for deferred-risk adjudication**
   (CLAUDE.md Gate 7f / DEFERRED+HIGH rules). The verifier treats
   `PIPELINE_PASS_WITH_DEFERRED_RISK` as a pass token and stops there — it does not
   inspect WARN dispositions.
3. **The wire STATUS never vetoes a fresh, run-id-matching disk artifact.** Disk wins in
   both directions; the wire is logged context only.

### Why a script (honest rationale)

The script earns its keep because a **terminal pass/fail gate decided by LLM prose
re-interpretation is fragile**, and the codebase already invokes Python and trusts exit
codes at a gate (Step 9w.8 / `spec_eval_gate.py`, SKILL.md:485-501). It centralizes the
*decision routine* in one tested place. Note: it does **not** collapse the TAIL_SYNC_POINT
duplication (that comment marks the whole Shared Tail, not this check) — both call sites
still carry their own one-line "invoke the script with this artifact-kind" instruction.

### Item 2 roster schema (4 columns)

`docs/reports/<run-id>/worker-roster.md`:

```
# Worker Roster — run <run-id>
| Role | Agent ID | Branch | Worktree Path |
|------|----------|--------|---------------|
| routes | <agentId> | worktree-agent-<agentId> | <path> |
```

Written in Step 10w right after the single-message parallel spawn, before the wait.

---

## Acceptance Tests (EARS)

### Happy path

- WHEN the verifier is given a fresh (`mtime ≥ run_start_ts`), run-id-matching
  `self-audit` artifact whose `**Status:**` is `PIPELINE_PASS` and **no** wire STATUS,
  THE SYSTEM SHALL exit `0` (PASS). *(The forgotten-Output-Contract case that motivated
  item 1.)*
- WHEN the same artifact's status is `PIPELINE_PASS_WITH_DEFERRED_RISK`,
  THE SYSTEM SHALL exit `0` (PASS). *(Run 068's real terminal state.)*
- WHEN a fresh, run-id-matching `self-audit` artifact's status is `PIPELINE_PASS` **and
  the wire STATUS contradicts it** (e.g. `--wire-status "FAIL — agent crashed"`),
  THE SYSTEM SHALL exit `0` (PASS) — the on-disk artifact is authoritative and the wire
  STATUS NEVER vetoes a fresh, matching disk artifact. *(This is the core terminal-gate
  guarantee: a truncated/garbled tail-runner wire line must not fail a genuinely
  complete run.)*
- WHEN a fresh, run-id-matching `assembly` artifact has `STATUS: PASS` on line 1 and the
  wire STATUS says FAIL, THE SYSTEM SHALL exit `0` (PASS) — disk is authoritative.
- WHEN Step 10w completes the parallel spawn, THE SYSTEM SHALL write
  `docs/reports/<run-id>/worker-roster.md` with one row per spawned agent
  (Role, Agent ID, Branch, Worktree Path) before any completion is processed.

### Error cases

- WHEN the artifact is absent or unreadable, THE SYSTEM SHALL exit `2` regardless of
  wire STATUS.
- WHEN the artifact's status is PASS but `mtime < run_start_ts` (stale / prior aborted
  run at a reused run-id), THE SYSTEM SHALL exit `3`.
- WHEN the embedded run-id ≠ `--run-id`, THE SYSTEM SHALL exit `6`.
- WHEN a fresh, run-id-matching `self-audit` artifact's status is `PIPELINE_FAIL`,
  THE SYSTEM SHALL exit `1` even if the wire STATUS says PASS.
- WHEN no recognized status token is found, THE SYSTEM SHALL exit `4` and name the
  missing status as the reason.

> **Intentionally NOT covered (accepted residual risk):** there is no test for a
> *future-dated* stale artifact under a *reused* run-id (see Plan Quality Gate Q4). That
> case defeats both the mtime and run-id guards and is consciously accepted, not closed.
> A passing test suite therefore does **not** imply the stale case is fully mitigated —
> closing it requires the deferred per-run nonce (out of Plan A scope).

### Verification Commands

```
# Item 1 — deterministic harness (uses os.utime for stale/fresh, no sleeps):
python3 tests/test_verify_delegated_status.py
# Expect: "9/9 passed" and exit 0.

# Item 1 — spot-check a fresh self-audit PASS fixture:
python3 tools/verify_delegated_status.py --artifact <fix>/self-audit-pass.md \
  --artifact-kind self-audit --run-start-ts 1000 --run-id 069 ; echo "exit=$?"   # 0

# Item 1 — stale artifact must fail with code 3:
python3 tools/verify_delegated_status.py --artifact <fix>/self-audit-stale.md \
  --artifact-kind self-audit --run-start-ts 9999999999 --run-id 069 ; echo "exit=$?" # 3

# Item 1 — fresh self-audit PASS must PASS even when the wire STATUS contradicts it:
python3 tools/verify_delegated_status.py --artifact <fix>/self-audit-pass.md \
  --artifact-kind self-audit --run-start-ts 1000 --run-id 069 \
  --wire-status "FAIL — agent crashed" ; echo "exit=$?"   # 0 (disk wins; wire never vetoes)
```

### Item 2 — manual repro (per Codex recommendation)

1. Run a swarm build that spawns ≥3 agents.
2. Confirm `worker-roster.md` is written immediately after spawn, **before** any worker
   completion arrives.
3. Force an interruption after the roster is written but before the first completion is
   processed (simulated mid-spawn context death).
4. From disk only, verify the roster has one row per agent with
   role → agentId → branch → worktree-path, branches named `worktree-agent-<agentId>`,
   and that the mapping reconstructs swarm state without orchestrator memory.

**Pass criteria (EARS):** WHEN Step 10w completes the spawn and an interruption occurs
before the first completion arrives, THE SYSTEM SHALL allow full reconstruction of every
spawned agent's role → agentId → branch → worktree-path mapping from
`worker-roster.md` on disk alone, without accessing in-memory orchestrator state.

---

## Files in Scope

- `.claude/skills/autopilot/SKILL.md` — Step 1 Run State block (declare `run_start_ts`,
  :127-133), Step 5.5 (capture it, :236-246), Step 10w (roster write, ~:588), Steps
  11w–16w handler (:645-691), Step 18w + crash branch (:722-735), solo TAIL_SYNC_POINT
  comment (:745).
- `.claude/agents/tail-runner.md` — Output Contract note (:196-216), TAIL_SYNC_POINT
  comment (:49).
- `tools/verify_delegated_status.py` — **new**, shared disk-verify routine.
- `tests/test_verify_delegated_status.py` + fixtures — **new**, the harness.
- **Read-only reference (do not edit):** `.claude/agents/self-audit-reviewer.md`
  (:82-95, status format) and `.claude/agents/swarm-runner.md` (:146-149, blocking
  aborts :88-107) — used to confirm formats the verifier parses.

---

## Feed-Forward

- **Hardest decision:** How to define "stale" given that run-ids are *reused* (Step 5.5
  derives run-id from a solution-doc count, so a prior aborted run leaves a PASS artifact
  at the same reused path). Chose `mtime ≥ run_start_ts` (new `run_start_ts` at Step 5.5)
  + a free run-id cross-check, over a per-run nonce embedded by producers. **This leaves
  a consciously ACCEPTED RESIDUAL RISK** (not a silent deferral): a future-dated stale
  artifact under the same reused run-id defeats both guards. Accepted because it requires
  a backwards clock on a single-host sandbox (near-impossible here); the per-run-nonce
  fix is out of Plan A scope (it edits the producer agents Plan A holds invariant).
  Revisit trigger: multi-host/networked-FS infra, or any observed clock-skew anomaly.
- **Rejected alternatives:** (1) Trust the on-disk artifact blindly — reopens the
  false-PASS hole. (2) One generic "line 1" parser for both artifacts — **wrong**, the
  two artifacts have different STATUS formats (caught in deepening as a P0). (3) Let the
  wire STATUS veto a disk PASS (best-practices suggestion) — reintroduces the false-FAIL
  the plan exists to kill; disk always wins. (4) Re-adjudicate deferred-risk in the new
  script — creates a second source of truth vs `/verify-self-audit`. (5) A `Spawn Status`
  roster column — constant-valued, no reader. (6) Full failure-injection harness for
  item 2 — would mostly test a fake context-death simulator (Codex).
- **Least confident:** Whether the LLM orchestrator will reliably *invoke the script and
  trust its exit code* over re-deciding from the wire STATUS in prose. The SKILL.md
  instructions must say "exit 0 = PASS, any non-zero = FAIL, do not second-guess,"
  consistent with how it already gates on `spec_eval_gate.py`'s exit code.
- **Open call for the post-plan reviewer:** the simplicity reviewer recommended *cutting*
  the dedicated test harness (assuming a 3-`if` script) and *cutting* the swarm-runner
  handler application (YAGNI). Both were **kept** because the deepening P0s grew the
  verifier's branch count (two formats, three tokens, run-id + freshness) and because the
  brainstorm explicitly scoped both call sites. Codex should confirm or overrule.

---

## Codex Handoff Prompt (after self-review — use when ready)

```
Read these files first for project context:
  - CLAUDE.md
  - docs/brainstorms/2026-06-06-autopilot-orchestration-hardening-brainstorm.md
  - docs/plans/2026-06-06-autopilot-orchestration-hardening-A-reliability-plan.md
  - .claude/agents/self-audit-reviewer.md (status format the verifier parses)
  - .claude/agents/swarm-runner.md (assembly-summary STATUS + blocking aborts)

Review this plan for:
1. Gaps — especially the staleness model. The plan now labels the future-mtime
   reused-run-id case as a CONSCIOUSLY ACCEPTED RESIDUAL RISK (Plan Quality Gate Q4 +
   Feed-Forward + an Acceptance Tests note), with the per-run nonce held out of scope
   because it edits the producer agents. Is that acceptance rationale sound (single-host
   sandbox → backwards clock near-impossible), and is the revisit trigger
   (multi-host/networked-FS, or any observed clock skew) the right line? Or does the hole
   warrant shipping the nonce now despite the producer-edit scope cost?
2. Wrong assumptions — does assembly-summary.md always exist on a swarm-runner PASS? Are
   the self-audit `**Status:**` accept-set ({PIPELINE_PASS, PIPELINE_PASS_WITH_DEFERRED_RISK})
   and the assembly accept-set ({PASS}) correct and complete?
3. The two deliberate calls: (a) disk-always-wins over a contradicting wire STATUS
   (wire never vetoes) — right for a gate whose whole point is wire unreliability?
   (b) keeping both the harness and the swarm-runner handler application despite the
   simplicity reviewer's YAGNI flag.
4. Single-source-of-truth: is "verifier reads terminal status only; /verify-self-audit
   owns deferred-risk adjudication" cleanly separated, or can they still disagree?
5. Did the plan miss any mirror site (it updates both TAIL_SYNC_POINT comments + the
   tail-runner Output Contract note + the Step 18w crash branch)?
6. Plan Quality Gate — does it answer what's changing, what must not change, how we'll
   know, and the most likely way it's wrong?

Output: findings ordered by severity + an updated Claude Code work prompt if needed.
```
