# Codex P3 CODE-review handoff (copy-paste to Codex, fresh context)

P3 = the FC-harvest value gate + compounded-darkness dynamic-surface fix (trust-gate step 3).
Built with the hardened template (`docs/codex-review-request-template.md`): one target (the
branch tip), machine-checkable output contract, DoD grounded in commands Codex must run.

```
Work in /Users/alejandroguillen/Projects/sandbox
Branch: feat/p3-harvest-and-darkness-tools
Review target: the current TIP of that branch. Run `git rev-parse feat/p3-harvest-and-darkness-tools`
and review THAT exact commit. Do NOT ask me which commit — the tip is the single
authoritative HEAD; everything to review is on it. If your checkout shows a different tip,
`git fetch` first. The review base is `4da3eff` (origin/master; FC68 already merged there).

ASK (one decision): GO / NO-GO on whether P3 is correctly implemented — specifically whether
tools/verify_harvest.py is a SOUND, deterministic, hard-to-game gate (a hollow or padded
harvest must FAIL; a genuine one must PASS), the compounded-darkness fix is correct, and the
firebreak/SKILL wiring is safe.
This is a CODE review. Do NOT write code. Do NOT ask for confirmation of the commit, branch,
or scope — everything you need is below.

READ THESE FILES FIRST (Codex has no other context):
  - CLAUDE.md  (the sandbox operating contract — firebreak/TRUSTED-tool rules, no -m carve-out)
  - AGENTS.md (if it exists)
  - tools/verify_harvest.py            (the new gate — 328 lines; module docstring states the contract)
  - tools/test_verify_harvest.py       (12 cases — happy + 4 checks + anti-gaming + INPUT_ERROR)
  - the diff:  git diff 4da3eff..HEAD

WHAT THIS IS (3 lines max, self-contained):
  A Path-B swarm run justifies its cost by HARVESTING pitfalls, not by a green build. Run 083
  SELF-certified its harvest (disconfirmer D4 flagged it → 083-W5). verify_harvest.py replaces
  that self-certification with a deterministic tail gate; "correct" = a padded/hollow/gamed
  harvest FAILs and a genuine evidence-backed one PASSes, with no false PASS path.

REVIEW THIS FOR (numbered, specific — not "is it good"):
  1. Anti-gaming soundness of the four checks in verify_harvest.py:
     (a) BREADTH — REAL detection is `^\s*REAL\b`; distinctness + dupe + empty-rc rejection.
     (b) BIJECTION — each REAL root_cause_id maps 1:1 to a `**root_cause_id:**` row in
         BUILD_TRACKING `## FAILURES` (`_failures_section` + `_BT_RC_RE`). Can a finding pass
         without a real tracked failure, or two findings share one row?
     (c) EVIDENCE — `_evidence_resolves` passes if ANY cited path/`file:line` exists on disk.
         Known limitation: it proves a file resolves, NOT that it's relevant. Is that
         acceptable, or a gaming hole (cite any existing file, e.g. README.md)?
     (d) NET-NEW — `_is_net_new`: net-new iff an fc_id names an FC absent from the frozen
         baseline, else a self-declared "net-new" word only when NO in-baseline FC is present.
         KEY question: can an author fake net-new with an invented high FC (e.g. `FC999`) that
         is absent from the baseline but not a real registered class? Is the evidence check
         sufficient mitigation, or should net-new bind to a registry?
  2. Determinism / parse robustness: `_parse_table` deliberately CONTINUES across intervening
     prose (run 083 interleaved a "Note:" — stopping early would silently drop tail rows). Does
     the arity-match + repeated-header-skip guard prevent a stray same-arity table from
     polluting the findings? Any input that yields a nondeterministic or false-PASS parse?
  3. Fail-closed exit-code discipline: PASS=0 / FAIL=1 / INPUT_ERROR=2 / BAD_ARGS=5; argparse's
     native exit-2 is overridden to 5 (so INPUT_ERROR=2 is unambiguous); the top-level `except`
     returns INPUT_ERROR on any unexpected crash (never a false 0). Confirm no path exits 0
     without all four checks holding, and 256-wrap is avoided.
  4. Firebreak + SKILL wiring safety (the plan's must-not-change area):
     - .claude/hooks/firebreak-classify.py adds ONE path (tools/verify_harvest.py) to
       TRUSTED_PIPELINE_SCRIPT_PATHS. Confirm it is TRUSTED-only (a WORKER still DENIED),
       PATH-pinned, and NO new `-m` / name-based carve-out. Classifier suite must stay green.
     - .claude/skills/autopilot/SKILL.md: the gate runs BEFORE the disconfirmer; SKIP when no
       harvest-findings.md (solo/non-harvest run unaffected); FAIL → a HIGH WARN keyed
       `<run-id>-WHARVEST` the self-audit MUST dispose; INPUT_ERROR → fix input + re-run (no
       silent skip); `--root` passed explicitly (FC68 — no cwd self-location). Is the WARN key
       shape consistent with the self-audit/verify-self-audit gate expectations?
  5. compounded-darkness fix (tools/check_compounded_darkness.py): adds `c2-smoke-report.md`
     to the recognized dynamic-surface smoke names (083 D2: the manifest smoke was mislabeled
     DARK). Confirm it does NOT over-broaden — it still requires a PASS|FAIL STATUS, and the
     LIT/DARK default-safe posture is preserved.

GROUND-TRUTH FILES TO CROSS-CHECK (open them; do not trust this summary):
  - tools/verify_harvest.py — the regexes (_REAL_RE, _FC_RE, _FILELINE_RE, _PATH_RE,
    _NETNEW_WORD_RE, _BT_RC_RE), _check() ordering, _render(), main() exit-code mapping.
  - tools/check_compounded_darkness.py — classify_dynamic() name list + _EXECUTED_VERDICTS gate.
  - .claude/hooks/firebreak-classify.py — TRUSTED_PIPELINE_SCRIPT_PATHS (now 5 tools) and how
    TRUSTED-vs-worker identity is decided (confirm worker denial still holds).
  - .claude/skills/autopilot/SKILL.md — the "Verify Harvest" section ordering + WARN handling.

DEFINITION OF DONE — you MUST complete every item and show its result inline:
  [ ] 1. Ran `python3 tools/test_verify_harvest.py | tail -1` — paste it (expect 12/12).
  [ ] 2. Ran `python3 tools/test_check_compounded_darkness.py | tail -1` — paste it (expect 13/13).
  [ ] 3. Ran `python3 .claude/hooks/test_firebreak_classify.py | tail -1` — paste it (expect 283/283).
  [ ] 4. Ran `git diff --name-only 4da3eff..HEAD -- . ':!docs/**'` — paste it; confirm the code/
         config touched is exactly: tools/verify_harvest.py, tools/test_verify_harvest.py,
         tools/check_compounded_darkness.py, tools/test_check_compounded_darkness.py,
         .claude/hooks/firebreak-classify.py, .claude/hooks/test_firebreak_classify.py,
         .claude/skills/autopilot/SKILL.md. (docs/reports/p3/*.md is this handoff — a mandatory
         artifact, not code; do NOT treat its presence as scope creep.)
  [ ] 5. For each disclosed residual below — state blocker? yes/no + why.

DISCLOSED RESIDUALS (I already know about these — judge whether any is a NO-GO):
  - EVIDENCE (check c) proves a cited file RESOLVES, not that it is RELEVANT to the finding.
  - NET-NEW (check d) treats any baseline-absent FC id as net-new; it does not cross-check the
    fc_id against a live FC registry (an invented FC number would read as net-new).
  - `_parse_table` continues across prose by design; a stray same-arity pipe table could in
    principle contribute rows (mitigated by arity-match + repeated-header skip).
  These are the value-of-the-gate boundaries; the gate raises the floor from self-certification
  to evidence-backed, it does not claim to be un-gameable by a deliberately fraudulent author.

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
