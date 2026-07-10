# HANDOFF — Sandbox · NEXT = LAUNCH run 081 (lesson-studio scale-validation swarm)

## ⬅⬅ LAUNCH — NEXT SESSION (start here) ⬅⬅

**A ~30-agent autopilot SWARM is queued and launch-ready.** Spec is convergence-complete
(3 Codex rounds clean + human P0 pass, zero P0s) and `status: active`.

**Before you start:** this is a token-heavy unattended run — run it in a session started with
`--dangerously-skip-permissions` (Alex enables it in the launch terminal; the flag is also in
`.claude/settings.local.json`). Complete ALL phases in ONE session — do NOT break the loop to
save context (breaking causes skill-loading failures next session).

**To launch:**
1. Read the spec: `docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md`
   (swarm: true, agents: 30, namespace `studio/`, all 6 contract sections + EARS).
2. Invoke the autopilot swarm on that plan (per `.claude/skills/autopilot/SKILL.md`). The skill
   assigns the run-id (**081**), re-inits `BUILD_TRACKING.md` (current root copy is the stale
   run-080 one — already captured in `docs/reports/080`; safe to overwrite), runs the 9w.9
   ghost-file gate (`studio/` verified free), injects agent-pitfalls into every worker brief
   (MANDATORY — `~/.claude/docs/agent-pitfalls.md`), and spawns.

**Why this run exists (the REAL deliverable = validation, NOT the app):** first live exercise
at ≥20-agent scale of the governance stack — G1 firebreak on a real swarm, today's FC58
path-pin + 080-W5 compounded-darkness gate, G3 self-audit chain, and Step 1.52 context
telemetry. The app is a throwaway vehicle chosen to maximize coordination-seam surface.

**Honest-status guardrails (do NOT overclaim):**
- A **MISSING** Step 1.52 telemetry boundary row at ≥20 agents = **instrument FAILURE**
  (harden trigger), NEVER a pass.
- Read a "clean" run **skeptically**: 30 agents may VALIDATE RESILIENCE without reproducing
  the context-death path — report that honestly (attempted-not-reproduced), don't dress it up.
- Success criteria + the two hardest seams (4-way lessons FK; enroll→invoice transaction) are
  in the plan's "Scale-Validation Acceptance" + Feed-Forward.
- `dangerouslySkipPermissions` billing: stay on Max subscription, NOT the 1M-Sonnet variant.

**Provenance:** brainstorm `docs/brainstorms/2026-07-09-scale-validation-swarm-vehicle-brainstorm.md`;
human P0 pass `docs/reviews/2026-07-10-lesson-studio-human-p0-pass.md`; validate-at-scale plan
`docs/plans/2026-07-07-chore-validate-orchestrator-context-telemetry-at-scale-plan.md`.

---

# (prior handoff — Steps 1–4 DONE · [079-W3] CLOSED · Step 5 governance COMPLETE)

**Date:** 2026-07-02
**Branch:** `master` @ `f0590fc` (clean, in sync with origin, single worktree). Run-080 KNOWLEDGE is on master; the throwaway `shelftrack/` app CODE was on `feat/shelftrack-reading-list`, now DELETED (Step 4).
**Phase:** **Steps 1–4 all COMPLETE. `[079-W3]` CLOSED (G1+G3 confirmed live, firebreak active through the tail; FC58 resolved for pipeline scripts). Run-080 honest status = `PIPELINE_PASS_WITH_DEFERRED_RISK` (NOT clean PASS — see below). Master-hygiene MINIMAL unblock done; Step-4 teardown done (worktree + 5 branches removed). **UPDATE 2026-07-04→09: Step-5 governance audit essentially COMPLETE — no speculative builds. G2 SHELVED (zero observed worker stalls); G4 STAYS DEFERRED (consciously-accepted residual, revisit trigger unfired); context-death pivot → telemetry ALREADY EXISTS (SKILL.md Step 1.52, since 2026-06-08), validate-at-scale plan written; `[080-W2 HIGH]` RESOLVED (`docs/reports/080/review-summary.md`). NEXT = pick from the menu in the "NEXT" section (G5 evidence-check · `[FC58-PATHPIN]` · `[080-W5]` · master declutter). Discipline saved: memory `feedback_evidence-check-framework-backlog`.**

## Honest validation status

- **G1 — PASS (run 080).** Real worktree worker probe denied 3 RED actions; deterministic no-canary verdict. Confirmed again on run 080 (previously confirmed run 079).
- **G3 — PASS (run 080, under active firebreak).** disconfirmer → self-audit → Gate-8 chain ran live with firebreak ACTIVE at phase=tail. Run 079's G3 ran firebreak-OFF (FC58 forced early teardown); run 080 ran firebreak-ON. [079-W3, HIGH] CLOSED.
- **FC58 — RESOLVED.** verify_delegated_status.py and firebreak-activate.py ran GREEN under the TRUSTED_PIPELINE_SCRIPTS carve-out. No manual workaround required. First time the tail ran with the firebreak active start-to-finish.
- **Run 080 status:** PIPELINE_PASS_WITH_DEFERRED_RISK (self-audit verdict; verify-self-audit 8/8 gates PASS). 0 P1 review findings, 2 P2 deferred per plan. NOTE: the "10/10 tests" cover the prior Film-PM build (`app.*`), NOT ShelfTrack — ShelfTrack's own dynamic coverage is the post-teardown smoke re-run below (**16/16 PASS**).

## What Was Accomplished (run 080, 2026-06-30)

**ShelfTrack — 4-agent swarm Flask reading-list app (throwaway validation vehicle):**
- 4 agents (scaffold / models / auth / books) built a functional multi-user reading list
- IDOR fully mitigated: ownership-baked SQL WHERE (id AND user_id) on all 5 book routes
- CSRF on all POST forms including base.html logout; session.clear() on login+logout; SECRET_KEY fail-closed
- Assembly contract check caught 8 missing flash('error') categories → fixed inline (7f08f0e)
- Smoke FIREBREAK_DEFERRED (expected/non-blocking — re-run after Step 18w teardown)
- Tests 10/10 PASS (Film PM prior-build tests preserved; ShelfTrack namespace clean)

**G1+G3 coexistence re-validation:**
- G1 positive-control probe PASS (Step 9w.9.6): real worktree worker denied, no canary
- FC58 confirmed RESOLVED: TRUSTED_PIPELINE_SCRIPTS carve-out allows pipeline python under phase=tail
- G3 disconfirmer (Opus) ran BEFORE self-audit (Sonnet); Gate 8 (bijection) validated
- Tail ran start-to-finish with firebreak ACTIVE: first ever clean tail under G1+G3 simultaneous governance

## Master-hygiene MINIMAL unblock (2026-07-01/02)

Run 080 hit the root cause of the ghost-file block: **film-PM (run 070) squats the shared
top-level `app/` namespace**, and worker worktrees root on master, so `app/models/`
shadowed ShelfTrack's `app/models.py`. Fix (commit `127571e`, pushed; zero data risk):
- `git rm --cached -r app/` — untracked film-PM's `app/` (144 files stay on disk).
- `/app/` added to `.gitignore` (stops re-tracking + stops worker worktrees inheriting it).
- **Build Namespace Convention** added to `CLAUDE.md` + SKILL.md 9w.9 (FC59): every build
  writes its OWN top-level dir (e.g. `shelftrack/`), never shared `app/`.
- Recovery point: tag **`archive/pre-hygiene-2026-07-01`** (pushed to origin).
- **Run-080 knowledge preserved on master:** `docs/reports/080/` (19 files), the solution
  doc, plan, and brainstorm were brought from the feat branch to master so the coexistence
  proof + honest self-audit survive even after the throwaway branch is deleted (Step 4).

**NOT done (deliberately deferred):** the full ~50-dir master declutter. Master still
carries dozens of prior build outputs AND real projects with data (`lead-scraper` = 150
`leads.db` backups incl. `DO-NOT-DELETE`, `eval-harness`, etc.). A real declutter must be a
deliberate, per-dir decision using `git rm --cached` ONLY (never `rm -rf` — would destroy
gitignored data), archive-tagged first. See Deferred Items `[MASTER-DECLUTTER]`.

## Key Artifacts (run 080)

| Item | Location |
|------|----------|
| Solution doc | docs/solutions/2026-06-30-shelftrack-run-080-g1-g3-coexistence-revalidation.md |
| Plan | docs/plans/2026-06-30-shelftrack-reading-list.md |
| Self-audit | docs/reports/080/self-audit.md |
| Disconfirmer | docs/reports/080/disconfirmer.md |
| Firebreak probe (G1 PASS) | docs/reports/080/firebreak-probe.md |
| Assembly summary | docs/reports/080/assembly-summary.md |
| BUILD_TRACKING (run 080) | on branch `feat/shelftrack-reading-list` (transient per-run file; durable record is in the solution doc + reports/080) |
| Agent-pitfalls update | ~/.claude/docs/agent-pitfalls.md (2026-06-30 entry) |

## Deferred Items

- **[080-W2, HIGH] — RESOLVED (2026-07-04).** The missing on-disk review report now exists: `docs/reports/080/review-summary.md`. It consolidates the recorded review (2 inline reviewers: security flow-trace + learnings researcher; scope: ShelfTrack security; verdict **0 P1, 2 P2 both deferred** = 080-W6/W7) into the canonical location/format, backed by self-audit.md + disconfirmer.md + contract-check.md (FC35 14/14) + the solution-doc flow-trace table (5 routes PASS). **Provenance is explicit in the artifact:** it is a *reconstruction from the durable record*, NOT a fresh independent re-review — the ShelfTrack source is gone (deleted throwaway branch; only `shelftrack/__pycache__/` remains on master), so findings are reproduced, not re-derived. The original review was static-only; dynamic coverage came later via the post-teardown smoke re-run (16/16, see [080-W4]). Verdict is now artifact-backed. **Standing process fix for future governance runs:** use the full review roster AND write `review-summary.md` DURING the run, not inline-only. [080-W2] CLOSED.
- **[080-W4, HIGH] — RESOLVED (2026-07-01, post-teardown).** test_smoke.py was re-run after Step 18w firebreak teardown: **16/16 PASS**, including the IDOR-404 ownership check (user B → 404 on user A's book), register/login/CRUD/filter/logout. Found+fixed one test-harness bug (missing `os.unlink` → app's `not os.path.exists` init guard was skipped → "no such table"); app code was correct. Dynamic coverage of ShelfTrack now EXISTS and PASSES. Evidence: docs/reports/080/smoke-rerun-postteardown.md. [SMOKE-080] CLOSED.
- **[080-W5, MEDIUM] — RESOLVED (2026-07-09).** Built the deterministic compounded-darkness gate: `tools/check_compounded_darkness.py` reads the three surfaces' on-disk artifacts (spec-eval verdict file, spec-provenance STATUS, smoke STATUS), classifies each LIT/DARK by allowlisting its "real verdict" state, and prints `STATUS: COMPOUNDED_DARKNESS` iff all three are DARK. **Observability-only — always exits 0, never blocks.** Wired into BOTH tail paths BEFORE the disconfirmer (SKILL.md "Compounded-Darkness Check" step + tail-runner Step 7.4; TAIL_SYNC_POINT comments updated); writes `docs/reports/<run-id>/compounded-darkness.md` so the self-audit can dispose the WARN. Added to the FC58 pinned allowlist (runs under the active tail firebreak). Validated on real 080 data: current state = OK (dynamic lit by the post-teardown smoke rerun); original in-run tail state (dynamic FIREBREAK_DEFERRED) = COMPOUNDED_DARKNESS — the tool would have caught the exact 080-W5 pattern. Tests: 12/12 unit (`tools/test_check_compounded_darkness.py`); firebreak 282/282 + soundness + superset green.
- **[FC58-PATHPIN, P2] — RESOLVED (2026-07-09).** Path-pinned the FC58 carve-out: replaced basename set `TRUSTED_PIPELINE_SCRIPTS` with repo-relative-path set `TRUSTED_PIPELINE_SCRIPT_PATHS` (`tools/verify_delegated_status.py`, `tools/check_spec_provenance.py`, `.claude/hooks/firebreak-activate.py`); added `python_script_target()` (resolves python's real `.py` target past `-W`/`-X` value-flags, `None` for `-c`/`-m`) + `_is_pinned_pipeline_script()` (resolves target vs `repo_root`). Retires residual A (basename from any path) and residual B (`-W` flag-value mis-pick) — both now DEFER. Benches: classifier 281/281, soundness 319R+129G, superset 297/297. Live-safe (all SKILL.md invocations are repo-relative python/python3 from repo root). Todo 074 → `complete`. **Supersedes the "basename-match only" invariant** (was its pre-registered follow-up).
- **[ShelfTrack-DEFERRED-HARDENING]** Deferred items in the plan (throwaway vehicle — these are intentional, not oversights): password min 6 chars, SESSION_COOKIE_SECURE FLASK_ENV conditioning, login rate limiting, HTTPS/HSTS. Not production-ready by design.
- **[AUTO-MEMORY-DEFERRED] — RESOLVED (2026-07-01, post-teardown).** MEMORY.md index pointer + memory file `shelftrack-run-080-g1-g3-coexistence.md` written after firebreak teardown (the firebreak had correctly deferred these out-of-repo writes during the governed tail).
- **[G3-RESIDUAL-DISPOSITION]** Disposition monoculture — lone Sonnet still disposes disconfirmer findings. No independent verification of disposition correctness. Candidate future G-gate. Prefer after coexistence is confirmed (it now is — CLOSED means this is the next priority).
- **[MASTER-DECLUTTER, deferred]** Master carries ~50 top-level dirs from ~80 prior runs — a mix of throwaway builds (bookmark-manager, todo.py, error-test-app, …) and REAL projects with data (`lead-scraper` = 150 `leads.db` backups incl. `leads.backup-SAFE-DO-NOT-DELETE.db`; `eval-harness`; likely `gigsheet`/`venue-scraper`). Only film-PM `app/` was untracked so far (it caused the active block). A full "clean master to infra+docs" pass is worthwhile before scaling G2/G4/G5 builds, but MUST: (1) archive-tag first, (2) use `git rm --cached` ONLY — NEVER `rm -rf` (would destroy gitignored `.db` data, incl. lead-scraper production data — four prior data-loss incidents), (3) get per-dir keep/untrack sign-off from Alex (real-vs-throwaway needs his knowledge). Do NOT bulk-automate.

## Step Sequence

**Steps 1–4 DONE. `[079-W3]` CLOSED.**

- ✅ **Step 1 — FC58 fix cycle** (merged): TRUSTED_PIPELINE_SCRIPTS carve-out + hybrid lifecycle + 14 tests (279/279); reviewed SAFE/mergeable.
- ✅ **Step 2 — hook repoint**: global firebreak hook → main-repo classifier; live-probe verified.
- ✅ **Step 3 — coexistence re-validation (run 080)**: `[079-W3]` CLOSED; firebreak active through the tail; honest status `PIPELINE_PASS_WITH_DEFERRED_RISK`.
- ✅ **Master-hygiene (minimal)**: film-PM `app/` untracked, `/app/` gitignored, namespace convention (FC59), recovery tag `archive/pre-hygiene-2026-07-01`; run-080 knowledge preserved on master.
- ✅ **Step 4 — teardown**: removed `sandbox-g1` worktree; deleted 5 branches — `feat/g1-risk-tiered-firebreak`, `feat/g3-verification-diversity`, `feat/g1-g3-live-validation`, `feat/fc58-firebreak-trusted-indirection` (all merged), `feat/shelftrack-reading-list` (throwaway, knowledge preserved). 2 also removed from origin. Master = single worktree, clean.
  - NOTE: other stale local branches + old `swarm-0**-assembly` branches remain — optional future cleanup (`git branch -a`).

### ⬅ NEXT — Step-5 governance audit COMPLETE (G2 shelved · G4 deferred · G5 evaporated · telemetry planned); pick from the menu
**G5 EVIDENCE-CHECKED 2026-07-09 → EVAPORATES (already built).** All three delegation dimensions already live in the record: **authority** = `run_id`+`run_start_ts` enforced by `tools/verify_delegated_status.py` (existence+freshness+run-id; docstring literally "moves authority to" the deterministic check); **responsibility** = line-1 `STATUS: PASS/FAIL` + cross-boundary imports/exports contract + Phase Status table; **accountability** = AGENT_STATUS `#|Agent|Commit|Status` (named agent + git commit hash, non-repudiable) + FAILURES log + post-review trace-to-agent. No OBSERVED accountability-vacuum failure (all 20+ pitfall classes are technical seam bugs). The only genuine authority-hardening gap (tamper-proof nonce vs a reused run-id) IS G4 — deferred, trigger unfired. **All three Step-5 governance items now resolved by local evidence; Step 5 is DONE.** Scorecard G5 row updated. Fourth consecutive framework-backlog item to evaporate under local evidence-check (G2 · G4 · telemetry-pivot · G5) — `feedback_evidence-check-framework-backlog` now 4/4.

**Menu for the next session (in recommended order):**
- ~~**`[FC58-PATHPIN]` (todo 074)**~~ — DONE 2026-07-09 (commit `fb20a11`). Path-pinned the FC58 carve-out; both residuals retired.
- ~~**`[080-W5, MED]`**~~ — DONE 2026-07-09. Deterministic compounded-darkness gate built + wired into both tail paths. See resolved deferred-item entry above.
1. **`[MASTER-DECLUTTER]`** — needs Alex: per-dir keep/untrack sign-off + archive-tag + `git rm --cached` ONLY (production data on disk). The last remaining backlog item; requires human input, do NOT bulk-automate.

**No autonomous backlog items remain** — every concrete P2/MED hardening item (G2/G4/G5, FC58-PATHPIN, 080-W5) is now resolved. Next substantive work is either MASTER-DECLUTTER (needs Alex) or a new build that exercises the accumulated telemetry/gates at ≥20 agents (validate-at-scale plan: `docs/plans/2026-07-07-chore-validate-orchestrator-context-telemetry-at-scale-plan.md`).

Scorecard context (`docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md`):
- **G2**: in-flight AI monitor — **SHELVED 2026-07-04.** Brainstormed + evidence-checked: **zero observed worker stalls** across all runs (no such failure class in agent-pitfalls); the real in-flight liveness failure is **orchestrator context death** (runs 050, 061), which a worker-watching monitor does NOT catch. Building the worker-liveness monitor = YAGNI / simulation-vs-building trap. If revisited, start from the Fork section of `docs/brainstorms/2026-07-04-g2-inflight-liveness-monitor-brainstorm.md`: pivot #1 (orchestrator context-death watchdog / "Tier 2 Pre-Review Resume checkpoint" — the evidenced pain) or pivot #2 (cross-worker semantic divergence — the real worker-level failure). Do NOT rebuild the worker-liveness design.
- **G4**: per-run-nonce ledger — **EVIDENCE-CHECKED 2026-07-07 → STAYS DEFERRED.** Not an open design question: it is a *consciously accepted, pre-registered residual risk* from the 2026-06-06 orchestration-hardening work (`verify_delegated_status.py` already does existence + freshness `mtime≥run_start_ts` + run-id match). The residual (future-dated stale artifact under a reused run-id) requires a backwards clock on a single-host sandbox; the fix (per-run nonce embedded by producers) was held out of scope. **Pre-registered revisit trigger: multi-host / networked-FS infra OR observed clock-skew anomaly.** Trigger has NOT fired (single-host, local-FS). Building it now = solving a non-triggered residual. See `docs/solutions/2026-06-06-autopilot-orchestration-hardening-A-reliability.md` §ACCEPTED RESIDUAL RISK.
- **G5**: delegation-as-authority — not yet examined (evidence-check its premise first, given G2+G4 both evaporated).

**Context-death pivot (from G2 Fork #1) — BRAINSTORMED 2026-07-07.** Evidence check found the ORIGINAL pain (tail-phase context death, runs 050/061) is **SOLVED** by the June 1–5 delegation architecture (tail-runner + swarm-runner + no-read discipline; run 069 survived 24 agents, no `PAUSED_FOR_CONTEXT` post-June-5). The "Tier 2 Pre-Review Resume checkpoint" was consciously *superseded*, not just unbuilt. What remains is a **narrow UNMEASURED gap**: pre-tail orchestrator saturation at 20–30 agents (deepening + spawn run inline, can't delegate) — runs 068/069/070 have `context_proxy_chars: 0` so the critical boundaries (Step 7w/10w) were never instrumented. **Recommended posture = MEASURE, don't build. **PLANNED 2026-07-07 → the telemetry ALREADY EXISTS.** verify-first archaeology found `Step 1.52: Orchestrator Context Instrumentation (M29)` in `.claude/skills/autopilot/SKILL.md:144-182`, added 2026-06-08 (commit `06cefe4`, from run-070 meta-analysis). It already updates `context_proxy_chars` at every boundary (end of Step 6, 9w.6, 10w, each 11w-16w, pre-17w) + a >70% advisory WARN, observability-only. Runs 068/069/070 show `0` because they PREDATE it; 079/080 (post-instrumentation) capture it. So the brainstorm's proposal was redundant. **Genuine residuals:** (1) unexercised at ≥20 agents (079/080 were 3-4 agents); (2) EVIDENCED fragility — Step 1.52 is model-followed prose, and run 050 proves the orchestrator DROPS manual bookkeeping under context pressure (it failed to fill BUILD_TRACKING during that context death), so the warning may fail exactly when needed. Plan = MINIMAL validate-at-scale (`docs/plans/2026-07-07-chore-validate-orchestrator-context-telemetry-at-scale-plan.md`): no build; the next ≥20-agent build is the validation run; a MISSING boundary row = instrument FAILURE (harden trigger), never a pass; a >70% WARN = size-a-Gap-1-fix trigger. Brainstorm: `docs/brainstorms/2026-07-07-orchestrator-pretail-context-telemetry-brainstorm.md`.

Before scaling more builds, consider the remaining deferred item: `[MASTER-DECLUTTER]` (full ~50-dir master cleanup — `git rm --cached` ONLY, never `rm -rf`; production data on disk). (`[080-W2]` review artifact is now RESOLVED — `docs/reports/080/review-summary.md`.)

**Session meta-finding (2026-07-04→07):** 2 of 3 Step-5 governance items (G2, G4) evaporated under local evidence, and the 3rd pivot's original pain is already solved. The scorecard's G-items derive from an *external framework* (DeepMind three-layers) arguing for capabilities in the abstract; the local engineering record already addresses or consciously-defers most. Lesson: evidence-check each G-item's *local* premise before brainstorming it.

## Three Questions

1. **Hardest decision?** 404 vs 403 for non-owner book access. Chose 404 to avoid leaking resource existence. Enforced by returning 0 rows from ownership-scoped SQL — no conditional logic needed in the route.
2. **What was rejected?** Ownership check as a separate Python step after fetch (TOCTOU-adjacent, forgettable). Flask-Login (over-engineering). SQLAlchemy (stdlib sqlite3 is explicit and matches the template).
3. **Least confident going in?** That every book route would independently scope by user_id without cross-agent coordination. Review flow-trace confirmed they all did. Pre-registration in Feed-Forward + spec Authorization Matrix was sufficient.

## Prompt for Next Session

```
Read HANDOFF.md "NEXT" section first. This is sandbox, on master (e5be782, clean,
pushed, single worktree).

Steps 1-4 DONE + Step-5 governance audit essentially COMPLETE. The 2026-07-04→09
session audited the Step-5 scorecard items and NONE needed a speculative build — the
win was disproving the premises cheaply:
  - G2 in-flight monitor → SHELVED (zero observed worker stalls in any run).
  - G4 per-run-nonce → STAYS DEFERRED (consciously-accepted residual; revisit trigger =
    multi-host/networked-FS or clock-skew, NOT fired on this single-host sandbox).
  - context-death pivot → telemetry ALREADY EXISTS (SKILL.md Step 1.52 / M29, added
    2026-06-08); wrote a validate-at-scale plan, no build.
  - [080-W2] → RESOLVED (docs/reports/080/review-summary.md; reconstructed-from-record).
The discipline that did this is saved as memory feedback_evidence-check-framework-backlog:
ALWAYS evidence-check a framework/backlog item's LOCAL premise (observed? already built?
consciously deferred w/ unfired trigger?) BEFORE brainstorming or building it.

Honest-status guardrails (do NOT repeat prior overclaims):
  - run 080 = PIPELINE_PASS_WITH_DEFERRED_RISK, NOT clean PASS.
  - FC58 "resolved" is scoped to TRUSTED pipeline scripts.
  - the Step 1.52 telemetry is UNEXERCISED at >=20 agents; a MISSING boundary row on a
    big build = instrument FAILURE (harden trigger), never a pass.

NEXT — pick from the menu (recommended order):
  1. G5 (delegation-as-authority) — last Step-5 item. EVIDENCE-CHECK its local premise
     FIRST (likely evaporates like G2/G4; either way it closes Step 5). Scorecard:
     docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md
  2. [FC58-PATHPIN] todo 074 — concrete P2, path-pin TRUSTED_PIPELINE_SCRIPTS. Ship-a-thing.
  3. [080-W5, MED] — compounded-darkness gate signal (spec-eval + provenance + tests all dark).
  4. [MASTER-DECLUTTER] — needs Alex: per-dir sign-off + archive-tag + git rm --cached
     ONLY (NEVER rm -rf — lead-scraper has 150 production leads.db backups on disk).

INVARIANTS (don't touch designs): firebreak classifier = deny-known-bad; FC58 carve-out
is TRUSTED-only + python-only + allowlist PATH-PINNED to exact repo-relative script paths
(basename-match RETIRED 2026-07-09, todo 074); self-audit-
reviewer stays model: sonnet; Gate 8 fail-closed + literal-token, no binding LLM verdict;
builds namespace under their OWN top-level dir, never shared app/ (FC59). Recovery tag if
hygiene needs rollback: archive/pre-hygiene-2026-07-01.

Governance scorecard: docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md
Run-080 solution doc: docs/solutions/2026-06-30-shelftrack-run-080-g1-g3-coexistence-revalidation.md
Self-audit (honest grades): docs/reports/080/self-audit.md
```
