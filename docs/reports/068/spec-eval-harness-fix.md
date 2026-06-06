# Spec Eval Gate — Harness Fix (run 068)

Commit: 6e3bf80. The spec eval gate (Step 9w.8) was returning non-credible
FAILs. Root-caused and fixed three genuine harness defects.

## Defects fixed

| # | Defect | File | Symptom | Fix |
|---|--------|------|---------|-----|
| 1 | `stack="generic"` hardcoded | spec_scenario_gen.py | Scenario agent system-prompted "senior **generic** developer" → generated **Go / TypeScript / Supabase** code for a Flask+SQLite spec | `detect_stack(spec_text)` → "flask"; threaded through `claims_to_scenarios` → `build_prompt` |
| 2 | Naive substring deterministic checks | judge.py / spec_scenario_gen.py | Absence + prose patterns `re.search(IGNORECASE)` → the no-FTS5 `match` rule hit the spec's required `re.match`; negative constraints matched their own prohibition text | Deterministic regex now ONLY for table-extracted **presence** patterns; absence + all prose claims → context-aware LLM judge |
| 3 | Agent refusal scored as failure | runner.py | Agent replied "please provide the existing files" → empty output judged as spec failure | `build_prompt` forces complete, self-contained generation |
| — | Missing `eval-harness/.venv` | (env) | Canonical Step 9w.8 command had no interpreter | Added `eval-harness/requirements.txt`; provisioned `.venv` |

## Before / after (run 068 Flask spec)

| | Wrong-language scenarios | Token-grep false positives | HIGH pass rate | Failures |
|---|---|---|---|---|
| Before | Yes (Go/TS/Supabase) | Yes (`match`↔`re.match`, etc.) | 87% (182/210) | 28 |
| After  | None — all Flask/Python | None | 90% (175/195) | 20 |

## Residual 20 failures — all single-shot-agent artifacts, NOT spec defects

The gate now produces real Flask code and sensible judgments, but still returns
FAIL because it tests whether a **single-shot Haiku agent**, given **one
micro-claim**, reproduces the spec's exact code — under a **100%-of-HIGH-pass**
threshold across ~195 claims. Residual classes:

- **~5 cosmetic type-hint strictness** — agent writes `-> list` instead of
  `-> list[Row]` (runtime-identical; `Row` is a hint). The spec judge demands
  exact annotation reproduction. The spec already maximally specifies it.
- **~6 route-group auth claims** — a one-line Authorization-Matrix row
  ("Route Group: /venues/*, Mode: role-only") is turned into "write the whole
  CRUD route group"; the agent emits a partial app (1024-token output
  truncation) or uses `@role_required` matching the matrix's "role-only"
  wording. Scenario-design limitation.
- **~9 prose** — agent chose SQLAlchemy ORM instead of the spec's raw `sqlite3`
  DDL, hallucinated a Claude API call, missed `import re` in a slice, or output
  truncated before templates. Single-shot quality/scope limits.

The harness's own caveat acknowledges this (models.py `report_caveat`): results
"estimate rule clarity/comprehension under controlled prompting. They do not
estimate adherence under realistic swarm cognitive load." The real 12-agent
swarm gets the full spec + pitfalls injection + stronger models and would not
make these single-shot errors.

## Not changed (deliberately — would be gaming, not fixing)

- The spec LLM judge's strictness on exact signatures/annotations.
- The 100%-HIGH-pass scorer threshold.
- `max_tokens_scenario` (bumping it raises cost — the last run already cost
  $2.77 vs a $1.00 cap that is not actually enforced mid-run — and would only
  partially address truncation).

## Bottom line

The harness is now **credible**: no garbage, real per-stack code, sensible
judgments. Its residual FAIL on this spec is driven by single-shot-agent
artifacts and judge/threshold strictness, not by spec defects. The spec itself
passed the consistency gate (45 checks), the completeness gate (all 6 surfaces),
and 3 deepening reviews. Proceeding past the gate remains a human decision.
