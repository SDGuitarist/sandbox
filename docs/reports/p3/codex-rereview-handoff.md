# Codex P3 CODE re-review handoff (round 2 — copy-paste to Codex, fresh context)

Your round-1 review returned NO-GO with 3 findings (`codex-fix-result.md` records the fixes).
This asks Codex to confirm ONLY that the three fixes are correct + complete + fail-closed, with
no scope creep and suites green. Hardened template (`docs/codex-review-request-template.md`).

```
Work in /Users/alejandroguillen/Projects/sandbox
Branch: feat/p3-harvest-and-darkness-tools
Review target: the current TIP of that branch. Run `git rev-parse feat/p3-harvest-and-darkness-tools`
and review THAT exact commit. Do NOT ask me which commit — the tip is the single authoritative
HEAD; everything to review is on it. If your checkout shows a different tip, `git fetch` first.
The review base is `4da3eff`; your round-1 tip was `840772f` and the fixes are on top of it.

ASK (one decision): GO / NO-GO on whether the THREE prior NO-GO findings are now correctly and
completely fixed, fail-closed, with no scope creep beyond the reviewed files.
This is a CODE review. Do NOT write code. Do NOT ask for confirmation of the commit, branch, or
scope — everything you need is below.

READ THESE FILES FIRST (Codex has no other context):
  - CLAUDE.md
  - AGENTS.md (if it exists)
  - docs/reports/p3/codex-fix-result.md              (what I changed + why + evidence)
  - tools/verify_harvest.py                          (the gate)
  - tools/test_verify_harvest.py                     (now 17 cases)
  - .claude/skills/autopilot/SKILL.md                (the "Verify Harvest" gate section)
  - .claude/skills/verify-self-audit/SKILL.md        (Gate 2 — the WARN-key enforcer, lines ~48-56)
  - the diff:  git diff 840772f..HEAD

REVIEW THIS FOR (numbered, specific):
  1. Fix #1 (WARN key): SKILL now instructs `<run-id>-W<N>` (next unused sequential index) instead
     of the fixed `<run-id>-WHARVEST`. Confirm this matches EXACTLY the shape verify-self-audit
     Gate 2 requires (sequential from 1, no zero-padding, no gaps), and that the malformed-key
     fail-closed guarantee is Gate 2 itself (a bad key FAILs the self-audit). Is the "choose <N>"
     instruction unambiguous for the orchestrator?
  2. Fix #2 (row-scoped BIJECTION): `_failure_rows()` splits `## FAILURES` on `^#{3,}` headings into
     per-block SETS of root_cause_ids; the check enforces (a) every REAL rc in ≥1 block, (b) no rc
     spanning >1 block, (c) NEW: no block declaring ≥2 distinct REAL rcs. Confirm one tracked row
     can no longer satisfy two findings, AND that legitimate 1-row-per-finding layouts (real 083
     format: `### ` block + one `**root_cause_id:**`) still PASS. Any parse input that defeats the
     row split or yields a false PASS/FAIL?
  3. Fix #3 (thresholds): `--min-real`/`--min-netnew` < 1 now rejected via `p.error()` → EXIT_BAD_ARGS
     (5) before any check runs. Confirm a zero/negative floor can no longer yield PASS, and the
     exit code is BAD_ARGS (5), not a false 0/1.
  4. Scope / must-not-change: the code/config diff is limited to tools/verify_harvest.py,
     tools/test_verify_harvest.py, .claude/skills/autopilot/SKILL.md. Confirm
     .claude/hooks/firebreak-classify.py is UNTOUCHED — verify_harvest.py stays TRUSTED-only +
     path-pinned and workers still DENIED (classifier suite still 283/283). The four original gate
     checks' other behavior (breadth/evidence/net-new, exit-code discipline) is unchanged.
  5. Regression proof: the new tests actually fail closed — a merged multi-ID FAILURES row FAILs
     BIJECTION (a global-findall would have PASSED it), and zero/negative thresholds exit 5.

GROUND-TRUTH FILES TO CROSS-CHECK (open them; do not trust this summary):
  - tools/verify_harvest.py — `_failure_rows`, the BIJECTION block in `_check`, and the threshold
    guard in `main()`.
  - tools/test_verify_harvest.py — the `bt_text` fixture override + the 3 new cases.
  - .claude/skills/verify-self-audit/SKILL.md — Gate 2 key-format rule (the fail-closed mechanism).

DEFINITION OF DONE — you MUST complete every item and show its result inline:
  [ ] 1. Ran `python3 tools/test_verify_harvest.py | tail -1` — paste it (expect 17/17).
  [ ] 2. Ran `python3 tools/test_check_compounded_darkness.py | tail -1` — paste it (expect 13/13).
  [ ] 3. Ran `python3 .claude/hooks/test_firebreak_classify.py | tail -1` — paste it (expect 283/283).
  [ ] 4. Ran `git diff --name-only 840772f..HEAD -- . ':!docs/**'` — paste it; confirm ONLY the
         three reviewed code files (docs/reports/p3/*.md are mandatory artifacts, not code).
  [ ] 5. For each disclosed residual below — state blocker? yes/no + why.

DISCLOSED RESIDUALS (I already know about these — judge whether any is a NO-GO):
  - `_failure_rows` assumes the real `### `-per-failure BUILD_TRACKING layout; a single-heading
    layout with ≥2 REAL rcs would FAIL the shared-row check (correctly stricter).
  - EVIDENCE (relevance) and NET-NEW (registry) boundaries from round 1 are unchanged by this fix.
  - Running the gate on the historical docs/reports/083 FAILs BIJECTION on one untracked REAL
    finding (RC-firebreak-cwd-root-drift) — a pre-existing 7-REAL-vs-6-rows data gap, flagged
    identically by the old logic; not introduced here.

RETURN EXACTLY THIS FORMAT (nothing that stalls; no preamble):
  Line 1: `VERDICT: GO`  or  `VERDICT: NO-GO`
  Then a table — one row per review item (1..5):
    | Item | OK? (RESOLVED/ISSUE) | File:section checked | One-sentence evidence |
  Then: `RESIDUALS: none block` or `RESIDUALS: <key> blocks because <reason>`.
  Then the DoD checklist above, each box checked with its pasted result.
  If NO-GO, ALSO append a ready-to-paste Claude Code fix handoff, EXACTLY:
    ----- CLAUDE CODE HANDOFF -----
    Work in /Users/alejandroguillen/Projects/sandbox
    Branch: feat/p3-harvest-and-darkness-tools
    Live HEAD: <the tip sha you reviewed>
    Fix these NO-GO findings in order (each: file, exact change, why):
      1. ...
    Definition of done: <what must be true + which test/grep proves each fix>.
    After fixing: run <commands>, then do a second self-review and report residual risks.
    -------------------------------

DO NOT:
  - ask which commit/branch/scope (it is the tip of feat/p3-harvest-and-darkness-tools);
  - propose or write code unless the verdict is NO-GO (then only in the handoff block);
  - return prose without the VERDICT line and the table;
  - stall for input — if a file you expect is missing, name it and treat it as a NO-GO reason.
```
