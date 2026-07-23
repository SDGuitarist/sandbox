Work in /Users/alejandroguillen/Projects/sandbox
Branch: feat/p1p2-unattended-swarm-wave-barrier
Review target: the current TIP of that branch. Run `git rev-parse feat/p1p2-unattended-swarm-wave-barrier`
and review THAT exact commit. Do NOT ask me which commit — the tip is the single authoritative HEAD;
everything to review is on it. If your checkout shows a different tip, `git fetch` first.

ASK (one decision): GO / NO-GO on whether §1 of the plan is correctly implemented, with
single-wave behavior byte-for-byte unchanged and the three fixed constraints preserved.
This is a CODE review. Do NOT write code. Do NOT ask for confirmation of the commit, branch,
or scope — everything you need is below.

READ THESE FILES FIRST (you have no other context):
  - HANDOFF.md  (the "§1 Implementation (Session 1) — DONE" table + the honest gaps)
  - CLAUDE.md   (esp. "Mandatory Spec Coverage Sections" and the new §3.5 push policy)
  - AGENTS.md (if it exists)
  - docs/plans/2026-07-22-p1p2-unattended-swarm-wave-barrier-plan.md  (revision 5 — §1 is the spec)

WHAT THIS IS (self-contained):
  This branch encodes an UNATTENDED multi-wave swarm "wave-barrier" loop into the autopilot
  SKILL so a >=20-agent swarm can eventually run hands-off. §1 is the implementation: two new
  Python tools (wave_artifact.py, verify_wave.py) + SKILL/agent prose that runs a per-wave
  loop with a blocking integrated gate, all while the firebreak stays ACTIVE (no toggle).
  "Correct" = matches plan §1 deliverables, AND single-wave autopilot behavior is unchanged,
  AND the fixed constraints hold (no firebreak classifier LOGIC change; worker base ref
  unchanged; only the two approved tool-path allowlist adds; no `-m`/name carve-out).

REVIEW THIS FOR:
  1. Gaps — does the diff implement every §1 deliverable (plan §1 items 1-8), or is something missing/wrong?
  2. Wrong assumptions — do the tools assume anything untrue about git, the firebreak, or the plan's §5/§7 contracts?
  3. Scope / must-not-change — is SINGLE-WAVE behavior byte-for-byte unchanged (all wave logic gated on waves>1 / wave_index)? Is the firebreak classifier LOGIC untouched (data-only allowlist)? Worker base ref unchanged? Only the 2 approved tool paths added? No `-m`/name carve-out?
  4. Feed-Forward "least confident" (plan §9) — verify_wave being AUTHORITATIVE (truth derived from --plan/--spec + live git + re-read evidence, never a caller roster) and the forged-verdict guard. Is it actually authoritative, or can a forged artifact pass?
  5. Bugs / regressions / security — the atomic writes (temp + os.replace), the §7 reject-set completeness in verify_wave, and any path/injection issue in the tools.

GROUND-TRUTH FILES TO CROSS-CHECK (open them; do not trust this summary):
  - .claude/hooks/firebreak-classify.py — TRUSTED_PIPELINE_SCRIPT_PATHS now has 6 entries (2 new: tools/wave_artifact.py, tools/verify_wave.py). Confirm NO other logic changed and NO `-m` carve-out.
  - .claude/hooks/test_firebreak_classify.py — 2 new file-path ALLOW cases; suite must be 284/284.
  - tools/wave_artifact.py + tools/test_wave_artifact.py — emit (atomic wave.md, §6 schema, prev-artifact sha) + state (atomic transition-state).
  - tools/verify_wave.py + tools/test_verify_wave.py — --validate-schema (§4) / --wave K (§7) / --reconcile (§7).
  - .claude/agents/swarm-planner.md, .claude/agents/swarm-runner.md — wave-mode additions; confirm single-wave paths are explicitly preserved.
  - .claude/skills/autopilot/SKILL.md — "Multi-Wave Barrier Loop (Path B)" section; confirm the encoded step order matches plan §5 and the trigger no-ops for waves absent/1.
  - .claude/skills/tail-resume/SKILL.md — Step 0 Wave-Resume + Step 2b --reconcile fail-closed.

DEFINITION OF DONE — complete EVERY item and show its result inline:
  [ ] 1. Ran `python3 .claude/hooks/test_firebreak_classify.py | tail -1` — paste it (expect 284/284 passed).
  [ ] 2. Ran `python3 tools/test_wave_artifact.py | tail -1` — paste it (expect 15/15).
  [ ] 3. Ran `python3 tools/test_verify_wave.py | tail -1` — paste it (expect 32/32).
  [ ] 4. Confirmed single-wave is unchanged: in SKILL.md/swarm-runner.md/swarm-planner.md the wave logic is gated on waves>1 / wave_index — cite the guard lines. State whether a single-wave run's behavior could differ.
  [ ] 5. Confirmed the firebreak allowlist add is data-only (no logic change, no `-m`/name carve-out) — cite the diff hunk in firebreak-classify.py.
  [ ] 6. Judged verify_wave's authoritativeness: try to describe ONE forged artifact that would still PASS --wave K. If you find one, that is a NO-GO with the exact reject-set gap.
  [ ] 7. Checked each disclosed residual below — for each, state blocker? yes/no + why.

DISCLOSED RESIDUALS (I already know about these — judge whether any is a NO-GO):
  - verify_wave --reconcile has light unit coverage (1 degenerate 1-wave test); the multi-wave chain/ancestor reject cases (test_reconcile_chain_break / _earlier_wave_ancestor / _final_wave_is_head / _count_mismatch from plan §8) are left for the live run. --wave K has 17 git-fixture cases.
  - The §4 schema parser PINS concrete spec formats it reads: Cross-Boundary Wiring Table (`Symbol | Producer File | Consumer File | Build-Order-Sensitive | Import Path`), Coordinated Behaviors `**Members of <token>:** a, b`, Export Names `Defined By` (for out-of-roster). Real wave-mode specs must emit these (documented in swarm-planner.md).
  - `ambiguous` = same symbol produced by two different agents; file-level unmapped refs surface as `missing`/`unresolved`; `out-of-roster` is a distinct check via Export Names `Defined By`.
  - No live governed autopilot run yet (P4, gated) — tools were unit-tested against temp repos + an activated firebreak sentinel, not a real session.
  - SKILL Path B is orchestration PROSE, not executable code.

RETURN EXACTLY THIS FORMAT (no preamble, nothing that stalls):
  Line 1: `VERDICT: GO`  or  `VERDICT: NO-GO`
  Then a table — one row per §1 deliverable / review item:
    | Item | OK? (RESOLVED/ISSUE) | File:section checked | One-sentence evidence |
  Then: `RESIDUALS: none block`  or  `RESIDUALS: <which> blocks because <reason>`.
  Then the DoD checklist above, each box checked with its pasted result.
  If NO-GO, ALSO append a ready-to-paste Claude Code fix handoff, EXACTLY:
    ----- CLAUDE CODE HANDOFF -----
    Work in /Users/alejandroguillen/Projects/sandbox
    Branch: feat/p1p2-unattended-swarm-wave-barrier
    Live HEAD: <the tip sha you reviewed>
    Fix these NO-GO findings in order (each: file, exact change, why):
      1. ...
      2. ...
    Definition of done: <what must be true + which test/grep proves each fix>.
    After fixing: run the 3 test suites above, then do a second self-review and report residual risks.
    -------------------------------

DO NOT:
  - ask which commit/branch/scope (it is the tip of feat/p1p2-unattended-swarm-wave-barrier);
  - propose or write code unless the verdict is NO-GO (then only inside the handoff block);
  - return prose without the VERDICT line and the table;
  - stall for input — if a file you expect is missing, name it and treat it as a NO-GO reason.
