# HANDOFF — Sandbox

**Date:** 2026-06-22
**Branch:** `feat/g1-risk-tiered-firebreak` (working tree clean; **NOT pushed** — local only)
**Phase:** **G1 risk-tiered firebreak — Plan GO ✅ → Step 0 PASS ✅ → Phase 1 CORE built + tested ✅. Checkpointed for review BEFORE activation.**
Latest commit **`ceb8f50`**. Plan: `docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md` (1008 lines). Step 0 results: `docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md`.

**What's built (committed on the feature branch — `66182d9`, `ceb8f50`):**
- `.claude/hooks/firebreak-classify.py` — deterministic classifier, pure stdlib, full decision order (F13 opaque-word → control-plane/F9 → outward → indirection → mcp → fail-closed), Step-0 identity contract, atomic approval-record writer. **51/51** unit tests (`test_firebreak_classify.py`), one per EARS criterion + residual #3.
- `.claude/hooks/firebreak-gate.sh` — cheap entry gate (R6). Fast-paths GREEN, forwards only on envelope-safe markers, carries the Step-0 brace/backslash constraint, inspects `file_path` not `content`. **10/10** tests (`test_firebreak_gate.py`), incl. proof the fast-path does not spawn python.
- Run the suites: `python3 .claude/hooks/test_firebreak_classify.py` and `python3 .claude/hooks/test_firebreak_gate.py`.

**Phase 1 REMAINING — the activation layer (deliberately NOT done; user chose checkpoint-for-review):**
1. Wire the gate into **global `~/.claude/settings.json`** `hooks.PreToolUse` (matcher `Bash|mcp__*|Write|Edit`, command `bash .claude/hooks/firebreak-gate.sh`). Step-0-locked placement; **global change** (no-op without a sentinel).
2. **Orchestrator integration** (autopilot `SKILL.md`): write the sentinel after the provenance gate / before worker spawn, flip `phase→tail` before the tail-runner, run the **positive-control real-spawn probe** (abort if not live), remove the sentinel at run end.
3. **Phase 2:** `.gitignore` (`.claude/firebreak-active.json`, `todos/approvals/`) + approvals-queue schema polish + `resolve-todos` guard.

**Two bugs found & fixed during Phase-1 testing** (worth a reviewer's eye): a trusted learnings-writer could write an escaping path (`dev-notes/../.ssh/x`) — now denied for everyone outside the sanctioned set; the `bash` gate marker collided with the `"Bash"` tool name (every Bash call force-forwarded) — now requires a trailing space.

## Current State

Today's session (manual) produced three governance/knowledge artifacts and one
completed brainstorm, all committed and pushed to master:

1. **Master extraction** of all unattended-swarm/autopilot/guardrails/evals work —
   `docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md`.
2. **Governance analysis** scoring the autopilot system against Google DeepMind's
   *Three Layers of Agent Security* (June 2026) — surfaced 5 gaps (G1–G5) —
   `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md`
   (+ source PDF in the same dir).
3. **G1 brainstorm** (refined, 2 review passes, plan-ready) —
   `docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md`.

**G1 in one line:** a risk-tiered firebreak that enforces CLAUDE.md's existing
"Forbidden Actions" contract (currently unenforced under
`dangerouslySkipPermissions`) by classifying actions and **deferring** the
binding/irreversible tail to the `todos/` approval queue, keeping the safe
majority unattended.

## Decisions already locked in the G1 brainstorm

- **Escalation = defer-and-continue** via the existing `todos/` + `resolve-todos`
  queue (human = async batch reviewer, not a 2am babysitter).
- **Classifier = deterministic denylist (v1) → hybrid w/ AI advisory (Phase 2).**
  Deterministic always dispositive; AI only ever flags blind spots.
- **Merge-to-`main` = RED** (deferred for approval; v1 does NOT redesign assembly).
- **RED tier** = git force/shared-push + merge-to-main + prod-DB destructive +
  out-of-repo deletes + external sends + deploy + external-MCP-writes (default-deny)
  + package removal. **GREEN** = everything local in the worktree **+ the sanctioned
  learnings-propagation out-of-repo writes** (carve-out — must not be deferred).

## PLAN phase output (2026-06-21, session 2 — DONE)

1. **Spike GREEN (riskiest assumption verified first).** Empirically confirmed on
   claude 2.1.173 that a **PreToolUse hook fires AND blocks above
   `dangerouslySkipPermissions`** — for both the main session and a Task-spawned
   subagent. Mechanism viable; no fallback (agent-brief/tool-wrapper) needed.
   Residual = worktree-subagent firing + hook placement → gated as Step 0.
   Proof: `docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md`.
2. **Plan written, passed both gates** (plan-quality-gate = GO, ears-validator =
   PASS), then **deepened by 5 adversarial reviewers** (security, architecture,
   simplicity, data-integrity, performance) and **thinned to a safety-complete v1**.
3. **Both brainstorm open questions resolved:** (Q1) human-only approval via a
   glob-isolated `todos/approvals/` queue (NOT extending `resolve-todos`, which runs
   unattended); (Q2) no new run status needed.
4. **Deepening Review changed the design** (table R1–R8 at top of plan):
   - **R1** hook placement flipped **project → GLOBAL** + positive-control probe.
   - **R2** the graceful **deferred-merge wiring CUT from v1** — the swarm-runner
     merge is LOCAL and autopilot never pushes, so "merge-to-main" wasn't actually
     irreversible; the draft's pointer-commit reproduced FC51 base-drift and risked
     a silent false-`PIPELINE_PASS`. v1 merge-RED fires only on a `master`/shared
     target and just defers + one HANDOFF line.
   - **R3/R4** threat model restated honestly (guards honest mistakes + bounds
     outward blast radius, NOT adversarial-proof) + evasion hardening (git `-C`
     normalization, indirection-defer, outward allowlist incl. `gh api`/`npm
     publish`/`nc`/`ssh`, `mcp__*` read-only allowlist).
   - **R5** queue hardened: gitignore `todos/approvals/`, collision-free atomic
     uuid filenames (the `NNN` sequence races across 31 workers).
   - **R6** token-grep fast-path (python cold-start tax ≈ 7–12 min/run).
   - **R8** `/approve` skill deferred to v2; `resolve-todos` guard stays.
5. **User decisions (2026-06-21):** fully cut the status-mapping sliver (no v1
   status engineering for a deferred master-merge); next phase = Plan Review (Codex).
6. **v1 scope = Step 0 → Phase 1 → Phase 2.** v2 (deferred, documented): graceful
   merge disposition, `/approve` skill, AI advisory pass.
7. **Second-review pass (4 user-requested fixes + self-run review → F1–F5,
   commit `0f79883`/`356b542`):**
   - **F1** protect the firebreak **control plane** (hook config/scripts, sentinel,
     `todos/approvals/`) from the workers it governs; matcher extended to
     `Write`/`Edit`; positive-control probe spawns a **real** `isolation:"worktree"`
     + `bypassPermissions` agent.
   - **F2** cover interpreter/direct-script indirection
     (`python`/`python3`/`.venv/bin/*`, `node`, `ruby`, `./script`) vs a vetted
     `test_allowlist`; **declared residual** stated honestly (pytest runs
     worker-authored files = unbounded egress escape; v1 ≠ adversarial sandbox).
   - **F3** learnings carve-out re-keyed to **realpath target + learnings-writer
     identity** (orchestrator/tail-runner), not command shape.
   - **F4** all v2 merge-defer content (`/approve`, pointer commits,
     `PIPELINE_PASS_WITH_DEFERRED_RISK`) **isolated** out of the v1 body into a v2
     appendix.
   - **F5 (root fix from the self-run 2nd review):** key authority on a
     **TRUSTED-IDENTITY allowlist** (orchestrator/swarm-runner/tail-runner), **not
     `agent_id` presence** — the original rule would have **denied the mandatory
     learnings write** and **deferred the swarm-runner's local merge to `master`**
     on every run. Struck "merge" from the shared-push RED row (local merge =
     GREEN; only push/force-push is RED). Gate forwards-on-suspicion; **Step 0 now
     asserts `agent_id`/`agent_type` is present + unforgeable** (else fall back to
     blanket control-plane deny).
   - **Residual risks (now explicit/gated):** (a) the trusted-identity model rests
     on Step 0 proving `agent_type` is unforgeable; (b) the allowlisted-interpreter
     egress escape is a declared bound (real isolation needs OS/network egress
     control — out of scope for v1).
8. **Third/fourth/fifth review passes → F6–F13 (commits `8696bae` / `1458f5a` /
   `388cfaf` / `4ed63fe`), each driven by a Codex or self-run adversarial pass:**
   - **F6** every v1 guarantee (outward AND control-plane) holds for **DIRECT worker
     tool calls only** — an allowlisted interpreter runs worker-authored code
     in-process, invisible to the PreToolUse hook.
   - **F7/F12** `test_allowlist` = hardcoded `KNOWN_TEST_FRAMEWORKS`
     recognized-framework allowlist (plan-text-injection control, NOT a safety claim;
     a bad plan can't promote `python3 deploy.py` to a "test").
   - **F8** Step 0 validates hook metadata for **all four roles** (orchestrator /
     swarm-runner / tail-runner / worker) as an **empirical harness-contract check,
     NOT cryptographic unforgeability**.
   - **F9** env-indirected control-plane write destinations defer (scoped — plain
     worktree-relative writes incl. `> "$out"` stay GREEN).
   - **F10** **autopilot DOES push to a shared remote** — the pre-spawn
     spec-provenance gate (SKILL.md 9w.9.5) **conditionally** `git push`es a spec-only
     commit to `origin/<default-branch>`. Scoped out by ordering: firebreak active =
     **sentinel-present (sentinel-write → run-end)**; sentinel written AFTER the
     provenance gate → push not classified. (Replaced the false "never pushes" claim.)
   - **F11** the direct-call boundary has **named residuals**, not absolute protection.
   - **F13 (latest, Codex P0):** classifier **fail-closes on opaque command-word/verb**
     (`$(printf curl)`, `git $(printf push)`, `sudo $(printf curl)`, `c{u,}rl`) —
     shell-tokenize → defer if argv[0]/dispatcher-verb still contains an expansion;
     recurse exec-wrappers. **Honest downgrade:** set enumeration is leaky → F13
     *reduces, does not close*.
   - **THREE declared direct-call residuals (the current honest threat model):**
     #1 allowlisted-interpreter escape, #2 inherited-`$VAR` redirect to a control-plane
     path, #3 F13 unlisted-dispatcher/exec-wrapper leak. All stated consistently.
   - **Review trail:** Codex returned **NO-GO** once (F10 window contradiction +
     resolve-todos overclaim + shared-master wording — all fixed) and a **P0** on the
     opaque-command-word escape (→ F13). Self-run security reviews caught the F5
     identity inversion and the F13 "closes" overclaim. Handoff record:
     `docs/handoffs/2026-06-21-g1-firebreak-plan-claude-code-handoff.md`.

## Key Artifacts (this session)

| Item | Location |
|------|----------|
| **G1 PLAN (deepened, v1 thinned)** | **docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md** |
| **G1 spike (riskiest assumption, GREEN)** | **docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md** |
| Codex Plan-Review prompt (GO/NO-GO) | "Codex Handoff Prompt" section in the plan above |
| Codex NO-GO review record | docs/handoffs/2026-06-21-g1-firebreak-plan-claude-code-handoff.md |
| G1 brainstorm (plan input) | docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md |
| Governance scorecard (G1–G5) | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |
| Framework source PDF | docs/governance/three-layers-of-agent-security-deepmind-2026-06.pdf |
| Master extraction (system reference) | docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md |
| Existing approval-queue pattern | todos/ + .claude/skills/resolve-todos/ |
| Permission bypass switch | .claude/settings.local.json (`dangerouslySkipPermissions`) |
| Forbidden Actions contract | CLAUDE.md ("Forbidden Actions", "Bash Command Rules") |

## Deferred Backlog (priority order)

0. **[ACTIVE → CONFIRMING CODEX GO/NO-GO] G1 risk-tiered firebreak** — plan through
   6 review passes (R1–R8, F1–F13), Codex NO-GO + P0 both addressed, build-ready
   pending Step 0. Next: re-run Codex GO/NO-GO; on GO → `/workflows:work` on v1
   (Step 0 → Phase 1 → Phase 2). Commit `4ed63fe`.
1. **FC51 orchestrator rule** — ensure the converged spec is at the worktree base
   before swarm spawn (cherry-pick the spec-update commit into worktree bases, OR
   inline-inject spec sections into briefs). Live fragility that bit Run 070.
   (Partly addressed by the 2026-06-21 `check_spec_provenance.py` BASEREF-FRESH
   change — that's the *detection* half; the orchestrator *repair* rule remains.)
2. **Track A `P-extract`** — refactor `swarm-runner.md` cherry-pick prose into a
   shared callable so Track A (FC51) earns a real EXERCISED fixture row. Overlaps #1.
3. **Suite adoption decision** — wire `validate_hardening.py` in as a blocking gate.
   Proposal: docs/proposals/validate-hardening-on-fixtures.md.
4. **Eval-harness ↔ catalog FC drift** — harness covers 47 FCs; catalog is at
   FC1–FC57. Add scenarios/judges for FC48–FC57. (Surfaced 2026-06-21.)
5. **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in
   `callsheets.generate`. File: todos/070-pending-p2-callsheets-generate-redundant-double-query.md
6. **G2–G5** (from the governance scorecard) — in-flight AI monitor (G2),
   monoculture mitigation in verification roles (G3), per-run-nonce ledger
   hardening (G4), delegation-as-authority-transfer (G5).

## Stashes (untouched, local)

3 stashes on `master`: `stash@{0}`/`{1}` are superseded cpaa WIP (safe to drop);
`stash@{2}` is unmerged venue-scraper proxy/`html_mode` work for
`feat/lead-scraper-expansion` (keeper — fix `claude-sonnet-4-20250514` →
`claude-sonnet-4-6` on revival).

## Recovery SHAs (older, if ever needed)

| Ref (deleted) | Tip SHA | Where it lives now |
|---------------|---------|--------------------|
| `feat/film-production-pm` | `9b432bf` | 2nd-parent lineage of `49deb17` on master |
| `test/fc52-9w95-rewire-real-swarm` | `998854e` | reflog / GC window (~30d) |

## Codex Handoff Prompt — Phase 1 CODE REVIEW (run this next)

```
You are reviewing Phase 1 of the G1 risk-tiered firebreak in the Sandbox repo,
branch feat/g1-risk-tiered-firebreak (local, not pushed; latest commit ceb8f50).

CONTEXT (read these first):
- Plan:  docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md — start with
  "1. The classifier", "The RED tier — v1", "Acceptance Tests (EARS)", and the
  "Deepening Review — Changelog" (R1–R8, F1–F13).
- Step 0 results: docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md
  (identity contract: orchestrator=no agent_id/type; trusted=agent_type in
  {swarm-runner,tail-runner}; worker=else. Gate must match ONLY envelope-safe
  markers; brace/backslash obfuscation handled in python, not raw-JSON grep).

CODE UNDER REVIEW (only these — activation layer is intentionally NOT built yet):
- .claude/hooks/firebreak-classify.py     (deterministic classifier)
- .claude/hooks/firebreak-gate.sh         (cheap entry gate, R6)
- .claude/hooks/test_firebreak_classify.py (51 cases)
- .claude/hooks/test_firebreak_gate.py     (10 cases)
Run: python3 .claude/hooks/test_firebreak_classify.py ; python3 .claude/hooks/test_firebreak_gate.py
Both must print "N/N passed".

REVIEW FOR (P0/P1/P2, with file:line and a failing input where possible):
1. SOUNDNESS — can a WORKER get a RED action to ALLOW? Probe the decision order
   (F13 short-circuits first), the shell tokenizer (shell_words / resolve_argv0 —
   exec-wrapper recursion, VAR= stripping, dispatcher-verb opacity), git
   normalization (-C/-c/--git-dir), F9 escaping/opaque write dests, control-plane
   realpath matching, the learnings carve-out (identity + sanctioned target + no
   ../symlink escape), and mcp read-only allowlist. Find evasions.
2. GATE COMPLETENESS — is the gate's marker set a true SUPERSET of classifier
   denials? Any RED command/path the gate fast-paths (never forwards) so the
   classifier never sees it? (We know the residual: an absolute non-home,
   non-recognized-verb Bash write — is there worse?) Also check no other marker
   collides with envelope structural fields the way `bash`→`"Bash"` did.
3. FAIL-CLOSED & RECORD INTEGRITY — unparseable envelope, classifier exception,
   atomic write (temp+os.rename), filename RED-<run>-<cat>-<uuid>.md, deny still
   fires when the record write fails.
4. HONESTY — does the code match the plan's THREE declared residuals (interpreter
   escape, inherited-$VAR redirect, F13 unlisted dispatcher/wrapper)? Any
   guarantee that's broader in the comments than in the code?
5. The two fixes made during testing (escaping learnings path; `bash ` marker) —
   are they correct and complete, or do they mask a deeper issue?

OUT OF SCOPE: global ~/.claude/settings.json wiring, the orchestrator/SKILL.md
sentinel+probe integration, Phase 2 (.gitignore + resolve-todos guard). Those are
the post-review activation steps.

Return: verdict (GO / GO-WITH-FIXES / NO-GO) + a P0/P1/P2 findings table.
```

After Codex returns: triage P0/P1/P2, apply fixes (re-run BOTH suites green),
run my own adversarial second pass (~/.claude/docs/mandatory-review-workflow.md),
THEN proceed to the activation layer (global wire + orchestrator integration)
as a separate, explicitly-approved step. Decision to push the branch is the
user's — not pushed yet.
