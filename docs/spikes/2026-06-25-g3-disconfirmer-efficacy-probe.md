# G3 Disconfirmer — Efficacy Probe (verify-first gate)

**Date:** 2026-06-25
**Branch:** `feat/g3-verification-diversity`
**Plan:** `docs/plans/2026-06-25-feat-g3-self-audit-disconfirmer-plan.md` (feed_forward.verify_first = true)
**Status:** CANDIDATES GENERATED (by Opus) — **AWAITING CROSS-FAMILY (Codex) VALIDITY JUDGMENT**

## What this is

The plan's pre-registered "Done #4" and its single named residual (R2): does an Opus
disconfirmer reading the SAME run artifacts produce **orthogonal, valid** findings, or
just **restate** what the Sonnet self-audit already flagged? Within-family (Opus vs
Sonnet) is the *weak* diversity lever (self-preference bias is same-family), so the
plan forbids the Opus family from judging its own validity. This doc holds the
generated candidates; **a cross-family model (Codex) or a human must score them.**

## Probe design (so the numbers mean something)

- **Batch:** runs **064, 068, 069 (designated known-miss), 070** — chosen for rich
  preserved per-run artifacts and a spread of build types (solo-ish, swarm, large
  31-agent swarm). 069 is the known-miss: it carries `known-integration-defects.md`,
  `binding-review-verdict.md`, and `codex-binding-review-handoff.md` — a *later binding
  review found real gaps the self-audit did not fully prevent.*
- **Faithful pre-audit state:** each generation agent read the run's **build-time**
  artifacts ONLY and was hard-blocked from reading:
  - that run's `self-audit.md` (it did not exist when the disconfirmer runs — reading
    it would fake the novelty score), and
  - for 069, the post-hoc "answer key" (`known-integration-defects.md`,
    `binding-review-verdict.md`, `codex-binding-review-handoff.md`); for 070,
    `meta-analysis.md`.
  The `ARTIFACTS READ:` line on each result records what each agent actually opened.
- **Generator:** Opus, one pass each, real disconfirmer mandate + output contract +
  ground-truth rule (`.claude/agents/self-audit-disconfirmer.md`).
- **Imperfect-replay caveat (declared):** root `BUILD_TRACKING.md` / `HANDOFF.md` are
  current-state, not each run's historical snapshot. Mitigation: agents were scoped to
  the **preserved per-run `docs/reports/<run-id>/` artifacts** (068 and 069 even have a
  `BUILD_TRACKING-final.md` snapshot in-dir, which those agents used). No agent was
  given the live root files.

## Pre-registered thresholds (set BEFORE Codex judges — do not move)

- **Novel-valid rate** = (# findings absent from that run's `self-audit.md` AND judged
  valid) / runs probed. **Pass = > 0** (the plan's bar). Practically: at least one
  genuinely novel + valid finding across the batch.
- **Overcall rate** = (# invalid findings) / (total findings). An "assume not
  shippable" prior trivially inflates novelty, so this is the guardrail.
  **Pre-registered cap = overcall < 0.34** (≥ ~2 of every 3 findings must be valid).
- **Verdict logic:** PASS only if Novel-valid > 0 **AND** Overcall < 0.34. If it fails
  after ≤ 3 brief-tuning passes, the plan's escalation is **cross-family Codex as the
  standing verifier** — NOT a bigger single model, NOT a re-run loop. (Stopping
  discipline: hard pass-cap on brief tweaks = 3.)

## Held-out comparison files (Codex: judge novelty/validity against these)

| Run | Held-out self-audit (novelty baseline) | Extra answer key (known-miss) |
|-----|----------------------------------------|-------------------------------|
| 064 | `docs/reports/064/self-audit.md` | — |
| 068 | `docs/reports/068/self-audit.md` | `docs/reports/068/spec-eval-waiver.md` (already read by agent) |
| 069 | `docs/reports/069/self-audit.md` | `docs/reports/069/known-integration-defects.md`, `docs/reports/069/binding-review-verdict.md` |
| 070 | `docs/reports/070/self-audit.md` | `docs/reports/070/meta-analysis.md` |

A finding is **novel** if its *class* is not already disposed in that run's
`self-audit.md` WARN table / "What Was Missed". A finding is **valid** if it is
grounded in the cited artifact and is a real shippability threat (not a misread).

---

## Candidate findings (verbatim Opus output — NOT yet validity-judged)

### Run 064

ARTIFACTS READ: deepening-applied.md, gate-verification.md, review.md, spec-completeness-check.md, spec-consistency-check.md

| D# | Category | Why this threatens shippability (with file:line) | Severity |
|----|----------|--------------------------------------------------|----------|
| D1 | Core feature non-functional / smoke test failed | Primary write path persists nothing. review.md:28-40 (P1-1): `create_prompt`/`update_prompt` use `autocommit=True`+explicit `BEGIN`/`commit()`, silently dropping data in Python 3.14; wizard save returns 302 but writes nothing; smoke test FAILED ("Component content is encrypted — content appears plaintext: NULL", review.md:40). Fix is only a pending todo (review.md:56). | HIGH |
| D2 | Gate overridden against the repo's own mandatory contract | gate-verification.md:18-29 dismisses 36 missing route paths as "a format preference, not a content gap." CLAUDE.md "Mandatory Spec Coverage Sections" §1 explicitly requires "route path" in the Export Names Table. completeness-check.md:129 ("STATUS: FAIL -- 36 omissions"). CLEARED disposition contradicts the governing contract. | HIGH |
| D3 | Gate clearance rests on unverified commit claims contradicted by on-disk re-check | gate-verification.md:11-16 asserts the 3 consistency FAILs were "All fixed in d837097" / "would PASS on re-check." No reconciliation artifact proves this; consistency-check.md (labeled a re-check, line 5) STILL reports the same 3 FAILs (lines 22-24, 64), one HIGH runtime import error (line 61). Clearance unbacked by — and contradicted by — the artifact. | HIGH |
| D4 | Cross-section contradiction: hardening pipeline blessed the exact bug review later flagged | deepening-applied.md:13-16 PRESCRIBED the explicit `BEGIN`/`COMMIT` pattern; consistency-check.md:37 (Check #26) declared both functions "correctly specified and correctly implemented... PASS." review.md:23-40 proves that pattern silently loses data. Convergence signal is false. | HIGH |
| D5 | Second unresolved P1 — admin pages crash | review.md:60-78 (P1-2): `industry_models.py` Fernet-encrypts a plaintext admin field the spec lists as plain text; `get_guidance_for_industry` `InvalidToken`-crashes on seeded guidance. Fix only pending todo (review.md:80). review.md:191: "must be fixed before the run can be considered clean" — not fixed. | MEDIUM |

### Run 068

ARTIFACTS READ: assembly-summary.md, BUILD_TRACKING-final.md, contract-check.md, deepening-applied.md, gate-verification.md, ownership-gate.md, smoke-test.md, spec-completeness-check.md, spec-consistency-check.md, spec-eval-waiver.md, spec-eval-harness-fix.md, test-results.md

| D# | Category | Why this threatens shippability (with file:line) | Severity |
|----|----------|--------------------------------------------------|----------|
| D1 | All behavioral verification rests on absent/unversioned artifacts | The only proof the app works is `smoke_test_068.py`, which smoke-test.md:5 states is "(gitignored)" — not on disk, so 54/54 PASS and "Feed-Forward Risk: VERIFIED" (smoke-test.md:53) are unreproducible. test-results.md:6-8 confirms "No pytest suite prescribed... No app/ test files exist." Zero retained, inspectable behavioral evidence. | HIGH |
| D2 | Spec-eval gate never passed — human waiver dispositions real defects as "non-defect" without independent test | spec-eval-waiver.md:2-3: `gate_result: FAIL` overridden by `WAIVED_BY_HUMAN`. Residual failures include reproducible behaviors: spec-eval-harness-fix.md:38-39 ("agent chose SQLAlchemy ORM instead of raw sqlite3, hallucinated a Claude API call, missed `import re`"). Rests on the untested assertion (harness-fix.md:44-45) that the real swarm "would not make these single-shot errors." | HIGH |
| D3 | Cross-section contradiction undermines the "credible harness" the waiver depends on | spec-eval-harness-fix.md:13 claims the fix "Added eval-harness/requirements.txt; provisioned `.venv`." BUILD_TRACKING-final.md:57-58 still records "`eval-harness/.venv` does not exist... deps were hand-installed into root `.venv` to run the gate at all (ENV_ERROR)." If 175/195 came from a hand-patched env, the "credible harness" basis for the waiver is unverified. | HIGH |
| D4 | Transaction-boundary defect CLASS escaped every pre-swarm gate | contract-check.md:61-65 (contact_models `executescript()` implicit-commit, inline-fixed 5742bc9) and BUILD_TRACKING-final.md:109 (debrief_models nested `with conn:`, P2 89c2148). Yet spec-completeness-check.md:56 asserts "Transaction Contracts (FC29) | PASS | 14 write functions annotated, 0 unannotated" and consistency passed 45/45. Gates rubber-stamped a spec against which 40% of model modules still produced transaction defects. | MEDIUM |
| D5 | Dashboard "total revenue" KPI has a contradictory definition the smoke test rubber-stamped | smoke-test.md:39 labels 88000 cents "total revenue (paid only)", but paid alone = 50000+30000 = 80000 ($800), not $880. $880 only reconciles if tips fold in (assembly-summary.md:24). Same 8000 tips also shown separately (smoke-test.md:42). Smoke "verified" only by asserting the precomputed number. | MEDIUM |
| D6 | Unenforced cost control on the LLM gate | spec-eval-harness-fix.md:52-53: "the last run already cost $2.77 vs a $1.00 cap that is not actually enforced mid-run." A spend cap that does not stop the run; ran 2.77x over budget on one gate invocation. | LOW |

### Run 069 (designated known-miss)

ARTIFACTS READ: assembly-summary.md, BUILD_TRACKING-final.md, contract-check.md, gate-verification.md, ownership-gate.md, smoke-test.md, spec-completeness-check.md, spec-consistency-check.md, spec-eval-waiver.md, test-results.md, worker-brief.md, worker-roster.md

| D# | Category | Why this threatens shippability (with file:line) | Severity |
|----|----------|--------------------------------------------------|----------|
| D1 | Deliverable non-functional at build, gated PASS (cross-section contradiction) | `create_app()` raises `ImportError: cannot import name 'ingest'` (smoke-test.md:13-18; test-results.md:36-41 → 22 of 31 tests ERROR in conftest). Yet assembly-summary.md:1 declares STATUS: PASS and lines 9-11 reclassify the dead-on-arrival app "non-blocking." smoke-test.md:18: "All smoke routes were unreachable." PASS is a definitional override. | HIGH |
| D2 | Post-fix "green" claimed but no backing artifact | BUILD_TRACKING-final.md:227-228 asserts "Tests passing (post-fix) 30/31" / "Smoke tests passing (post-fix) 12/12" (commit 56a3b35), but the on-disk test-results.md / smoke-test.md still record the pre-fix FAIL state and were never re-run/updated. Shippability rests on prose numbers with no corresponding green artifact. | HIGH |
| D3 | Gate false-PASS by scope-narrowing the exact FC50 entrypoints the gates exist to catch | The two app-killing defects are unpinned route→orchestration calls (BUILD_TRACKING-final.md:82,115 — both "FC50 unpinned orchestration entrypoint"). spec-completeness-check.md:14-16 returned FC3 Cross-Boundary Wiring PASS / "0 missing"; contract-check.md:63-72 carves `ingest_source`/`run_replay` out of scope. CLAUDE.md mandates the completeness checker enforce orchestration-entrypoint rows (FC50 guard) — it passed a spec that omitted them. | HIGH |
| D4 | "Zero conflicts" is false integration assurance (wrong base + disjoint cherry-pick) | ownership-gate.md:18-33: all 24 worktrees rooted on master line (f90aed8), NOT the feat HEAD; real deps were untracked working-dir files ("exists on disk, but not in branch", line 33). assembly-summary.md:15-20 assembles by cherry-picking each worker's disjoint new files → "Zero conflicts." Git never exercised cross-agent integration; the 0-conflict count (assembly-summary.md:11) is meaningless — runtime integration in fact failed with 3 P1s. | HIGH |
| D5 | Spec-eval waiver's core rationale is falsified by the run's own failures | spec-eval-waiver.md:36-39 waives a real gate FAIL (44/155 claims failed) arguing single-shot divergences "have low predictive value for the real swarm" — citing invented names/signatures as harmless. The real swarm then committed the identical failure mode: B3 guessed `ingest`, C6 guessed `run_replay` arity (BUILD_TRACKING-final.md:82,246-248). Human override rests on a disproven assumption. | MEDIUM |
| D6 | Core determinism guarantee unverified; generating tool itself broken | Product is a deterministic event-replay simulator, but its anchor test is skipped (test-results.md:30-32) because `GOLDEN_PROJECTION_HASH` is absent, and the tool meant to produce it is broken: BUILD_TRACKING-final.md:132 "tools/compute_golden.py ... has a CSRF bug preventing the golden corpus hash step." Determinism — the whole value prop — ships unproven. | MEDIUM |
| D7 | Unresolved spec ambiguity shipped under "converged" label | spec-consistency-check.md:52,71-72 (WARN #40) leaves undecided whether dashboard reads projection tables via exported `station_state(conn)` functions or direct SQL — "If it expects these as exported functions, build will fail." Dispositioned LOW, deferred to E1 agent's discretion, never resolved in the frozen spec. | LOW |

### Run 070 (large 31-agent swarm)

ARTIFACTS READ: assembly-summary.md, contract-check.md, gate-verification.md, ownership-gate.md, review-summary.md, smoke-test.md, spec-completeness-check.md, spec-consistency-check.md, test-results.md, worker-roster.md, swarm-assignment-section.md

| D# | Category | Why this threatens shippability (with file:line) | Severity |
|----|----------|--------------------------------------------------|----------|
| D1 | Green tests exercise a non-production code path | All 18 smoke + 10 critical-flow tests run against `DATABASE=:memory:`, which triggers a special-cased shared-connection branch existing ONLY for in-memory DBs: "Production file-based databases unaffected and retain the original behavior" (smoke-test.md:21-22; test-results.md:12-17). The ship path (file-based SQLite, contract-check.md:48 default `filmpm.db`) takes a DIFFERENT, untested branch. 28/28 green proves the path you will NOT deploy. | HIGH |
| D2 | Ownership gate tautological; masks as-delivered defect rate | ownership-gate.md:1 ("All 16 agents passed... STATUS: PASS") rendered meaningless because the orchestrator patched two owned files AFTER the gate: assembly fix 38714db edits database.py + test_critical_flows.py (assembly-summary.md:50, :16-28). 2 of 16 deliverables shipped broken and needed orchestrator surgery — ~12.5% as-delivered defect rate invisible behind a green ownership/0-conflict gate. | HIGH |
| D3 | Test oracle edited to agree with implementation | 3 of 10 critical-flow tests had assertions REWRITTEN during assembly to match the code (test-results.md:19-37). Fix 2 deleted DOOD assertions for days 2/4 (coverage removed); Fix 4 changed `pytest.raises(Exception)` to `assert result is None`. "10/10 PASS" is partly self-certifying: the oracle was moved to the answer. | HIGH |
| D4 | Unresolved cross-section spec contradiction shipped, risk never disconfirmed | 3 retained WARNs where two authoritative sections disagree on return-dict keys (spec-consistency-check.md:15-17, 52-54). WARN 6: callsheet_models reading the Wiring Table's 3-key `get_location` would omit `contact_name, contact_phone, permit_status`. Review only verified `name/address/nearest_hospital` are consumed (review-summary.md:47-50) — never checked the 3 dropped fields render. | MEDIUM |
| D5 | Known functional breakage shipped as PASS with no covering test | review-summary.md:179-189 (P2-1): budget allocate form "likely broken in UI" — `GET /budget/<pid>` context lacks `departments`, so `<select name="department_id">` cannot populate. No fix; only coverage is `GET /budget/1 (200)` (smoke-test.md:39), which never exercises the allocate form. | MEDIUM |
| D6 | Review conclusions rest on unverified ("presumably") inspection | Reviewer signed off owned-file behavior it did not read: "`locations/routes.py` presumably similar. Assessment: acceptable" (review-summary.md:160). A verdict built on "presumably" is unbacked; the locations inline-UPDATE + FTS5 single-writer pattern was never confirmed. | MEDIUM |
| D7 | Known prior-build regression knowingly shipped | review-summary.md:84-90, 191-202 (P2-2): the run-063 fix removing the redundant double `get_schedule_entries` call was REGRESSED — the converged spec re-introduced the route-level pre-check (callsheets/routes.py:70-73) duplicating the model's internal call. | LOW |

---

## Codex scoring task (cross-family — paste into a fresh Codex context)

```
You are the cross-family validity judge for an efficacy probe. Repo: ~/Projects/sandbox,
branch feat/g3-verification-diversity. An Opus "disconfirmer" generated the candidate
findings in docs/spikes/2026-06-25-g3-disconfirmer-efficacy-probe.md for historical runs
064, 068, 069, 070. Do NOT trust the Opus family to judge itself — that is why you are here.

For EACH finding (D#) in each run, decide:
  - VALID? (grounded in the cited artifact AND a real shippability threat — open the cited
    file:line and check; mark INVALID if it misreads the artifact or is not a real threat)
  - NOVEL? (its problem CLASS is NOT already disposed in that run's held-out self-audit.md
    WARN table / "What Was Missed". Compare against:
       064: docs/reports/064/self-audit.md
       068: docs/reports/068/self-audit.md
       069: docs/reports/069/self-audit.md  + known-integration-defects.md + binding-review-verdict.md
       070: docs/reports/070/self-audit.md  + meta-analysis.md
    For 069 specifically: did the disconfirmer (which was BLOCKED from the answer-key files)
    independently surface the same class of defect the later binding review caught? That is
    the headline known-miss test.)

Then compute, against the plan's PRE-REGISTERED thresholds (do not move them):
  - Novel-valid rate = (# findings that are NOVEL and VALID) / 4 runs.  PASS bar: > 0.
  - Overcall rate = (# INVALID findings) / (total findings).  PASS cap: < 0.34.
  VERDICT = PASS iff Novel-valid > 0 AND Overcall < 0.34, else FAIL.

Return: a per-D# table (run, D#, VALID y/n, NOVEL y/n, one-line justification with the
file:line you checked), the two computed rates, and the PASS/FAIL verdict. If FAIL, name
which findings dragged overcall up and whether a brief tweak (≤3 allowed) could fix it, or
whether to adopt Codex as the standing cross-family verifier (the plan's escalation).
```

## Codex Verdict — 2026-06-26 (cross-family judge) — **PASS** (raw, verbatim)

> Scored against the probe's fixed thresholds: **PASS.** 0 invalid findings, and ≥1
> novel + valid finding in every run.

| Run | D# | VALID | NOVEL | Justification |
|-----|----|-------|-------|---------------|
| 064 | D1 | y | y | review.md:28-40,56 — Python 3.14 autocommit/BEGIN bug drops writes, wizard save non-functional; 064 self-audit does not dispose this class. |
| 064 | D2 | y | n | gate-verification.md:18-29 + completeness-check.md:129 — forced override of 36 missing route paths; 064-W5 / What Was Missed already dispose this gate-override class. |
| 064 | D3 | y | n | gate-verification.md:11-16 contradicts on-disk re-check consistency-check.md:22-24,64; same override class as 064-W5 / What Was Missed. |
| 064 | D4 | y | n | deepening-applied.md:13-16 + consistency-check.md:37 bless the BEGIN/COMMIT pattern review.md:23-40 proves loses data; same cross-section class as 064-W5. |
| 064 | D5 | y | y | review.md:60-78,191 — unresolved admin-page crash / InvalidToken with pending todo; no 064 self-audit item disposes it. |
| 068 | D1 | y | y | smoke-test.md:5,53 only proof is a gitignored script; test-results.md:6-8 no normal suite/artifact; no 068 self-audit covers artifact provenance. |
| 068 | D2 | y | n | spec-eval-waiver.md:2-3 + harness-fix.md:38-45 — gate failed, human-waived; 068-W3 already disposes that waiver class. |
| 068 | D3 | y | y | harness-fix.md:13 vs BUILD_TRACKING-final.md:57-58 — live harness-credibility contradiction; not in 068-W1/W2/W3 or What Was Missed. |
| 068 | D4 | y | y | contract-check.md:61-65 + BUILD_TRACKING-final.md:109 — transaction-boundary defects passed pre-swarm gates; no 068 self-audit disposes the class. |
| 068 | D5 | y | y | smoke-test.md:39,42 + assembly-summary.md:24 — KPI definition inconsistent (88000 vs paid+tips); not covered by 068-W1/W2/W3. |
| 068 | D6 | y | y | harness-fix.md:52-53 — gate blew its $1 cap unenforced; no 068 self-audit disposal of budget-control failure. |
| 069 | D1 | y | n | smoke-test.md:13-18 + test-results.md:36-41 — app dies on import; not novel (known-integration-defects.md:10-30 + binding-review-verdict.md:18-42 capture it). |
| 069 | D2 | y | y | BUILD_TRACKING-final.md:227-228 claims post-fix green while on-disk artifacts are still pre-fix failure set; no 069 item disposes this stale-artifact class. |
| 069 | D3 | y | y | **HEADLINE KNOWN-MISS** — BUILD_TRACKING-final.md:82,115 + completeness-check.md:14-16 + contract-check.md:63-72 FC50 unpinned-entrypoint gap; independently matches known-integration-defects.md:10-30 / binding-review-verdict.md:18-42. |
| 069 | D4 | y | y | ownership-gate.md:18-33 + assembly-summary.md:11,15-20 — "zero conflicts" with later runtime P1s; not in 069-W1/W2/W3/W4 or What Was Missed. |
| 069 | D5 | y | y | spec-eval-waiver.md:36-39 + BUILD_TRACKING-final.md:82,246-248 — waiver rationale undercut by run's own B3/C6 failures; not the falsified-predictive-value class. |
| 069 | D6 | y | n | test-results.md:30-32 + BUILD_TRACKING-final.md:132 — golden anchor skipped (hash absent); 069-W3 already disposes the class. |
| 069 | D7 | y | n | spec-consistency-check.md:52,71-72 retained spec ambiguity; 069-W2 / What Was Missed already dispose the low-WARN class. |
| 070 | D1 | y | y | smoke-test.md:21-22 + test-results.md:12-17 — tests only exercise :memory: branch, not file-backed ship path; no 070 item disposes the coverage gap. |
| 070 | D2 | y | y | ownership-gate.md:1 + assembly-summary.md:16-28,50 — gate passed while orchestrator patched owned files; no 070 item disposes the tautology/as-delivered-defect class. |
| 070 | D3 | y | y | test-results.md:19-37 — assertions rewritten to fit implementation; not disposed by 070-W1..W4 or What Was Missed:46-50. |
| 070 | D4 | y | n | spec-consistency-check.md:15-17,44-55 — same key-abbreviation/shadowing class 070-W1..W3 accept; What Was Missed:48-50 calls it out. |
| 070 | D5 | y | y | review-summary.md:179-189,162-169 — budget allocate form lacks departments list, likely broken UI; no 070 item disposes that defect class. |
| 070 | D6 | y | y | review-summary.md:160,183-189 — "presumably similar" inspection for locations/routes.py; unverified-reasoning class not disposed in 070-W1..W4. |
| 070 | D7 | y | n | review-summary.md:191-200 — redundant get_schedule_entries regression; 070-W4 / What Was Missed:48-50 already dispose this duplicate-query class. |

**Rates:** Novel-valid = **4/4 = 1.00** (bar: > 0) · Overcall = **0/25 = 0.00** (cap: < 0.34).
**Verdict: PASS.** 14 of 25 findings novel, 25/25 valid. 069 headline known-miss confirmed:
D3 independently surfaced the FC50 unpinned-entrypoint class later caught by the binding review.

## Outcome

The verify-first / R2 gate is **CLOSED — PASS**, on the first generation pass (zero
brief-tuning iterations of the 3 allowed; no Codex-as-standing-verifier escalation
needed). The within-family worry (Opus restating Sonnet) did **not** materialize on this
batch: the disconfirmer's findings were both grounded and predominantly orthogonal to
what the historical self-audits disposed. This is the empirical backing for plan Done #4.

**Authority note:** candidates were generated by Opus and judged by a cross-family model
(Codex) per the plan's anti-self-preference rule — Opus never scored its own family.
