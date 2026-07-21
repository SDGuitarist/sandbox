---
title: "Run 082 — Max-Value Unattended Autopilot Limit-Test (manual autopilot-swarm)"
type: feat
status: active
date: 2026-07-21
last_revised: 2026-07-21
deepened: 2026-07-21  # 7-agent deepen (learnings, pitfalls, sqlite, assembly, architecture, data-integrity, simplicity)
origin:
  - docs/brainstorms/2026-07-20-dynamic-workflows-scale-test-brainstorm.md
  - docs/plans/2026-07-20-feat-dynamic-workflows-max-scale-swarm-test-plan.md  # superseded (engine UNLAUNCHABLE)
  - docs/solutions/2026-07-21-workflow-engine-cannot-carry-firebreak-identity.md
run_id: "TBD-at-launch"   # the skill computes run-id = count(docs/solutions)+1 AT LAUNCH (currently would be 083). Do NOT hardcode 082 (its report dir already exists from the spike). All <R> paths use the computed id.
swarm: true
autonomy_class: autopilot-swarm
executor: autopilot-skill   # NOT the Workflow engine (UNLAUNCHABLE — see origin solution doc)
feed_forward:
  risk: "The value is the PITFALL HARVEST + governance stress, not the agent count. Two failure modes, both surfaced by the deepen: (1) a run that completes GREEN but teaches nothing (hollow) — the V1 harvest gate as first written was a date-stamp presence check, gameable; (2) padding the count with clone resources / consumer clusters so 'biggest' is manufactured, not earned. Mitigation: an evidence-backed verify-harvest gate, deliberately-coupled (not cloned) resources, and letting the count fall out of DISTINCT contradiction types."
  verify_first: true
---

# Run 082 — Max-Value Unattended Autopilot Limit-Test

## Enhancement Summary (deepened 2026-07-21)

7 parallel research/review agents (first-party-weighted: solution docs + agent-pitfalls). Key changes vs the first draft:
1. **Decomposition rescheduled** from infeasible parallel model/routes/tests clusters → **layered merge-barrier waves** (siblings can't see each other; worktrees root on `origin/default`).
2. **Tests de-padded**: per-resource test clusters CUT (your clean runs — lesson-studio 30, GigSheet 31 — never used them); tests consolidated into a Wave-0-owned `smoke.py` + a small integration layer.
3. **V1 harvest gate hardened** from a date-stamp grep → an evidence-backed, traceable, anti-circular `verify-harvest` gate (baseline diff + BUILD_TRACKING provenance + ≥2 net-new floor).
4. **C2 given an owner + teeth**: `smoke.py` is a Wave-0 deliverable; "exercised" defined; asserts on values + atomic rollback + concurrency stock-race.
5. **run_id collision fixed**: skill computes the id at launch; 082 no longer hardcoded.
6. **Coupling pinned, not prose**: 6-section spec authored pre-spawn by porting lesson-studio §5/§6; SQLite transaction traps pinned; FK on-delete policy per edge; shared symbols Wave-0-owned.
7. **SIZING resolved → path B** (see §Sizing Decision): B = add NEW contradiction TYPES (state-machine, uniqueness, soft-delete, 2nd transaction), not clones. **Count-reality correction (2026-07-21, spec phase):** the honest Path-B decomposition is **~22 agents (19 build + 3 tail), BELOW 31** — swarmlimit has too few distinct resources to clear 31 without padding, and I1(>31) is non-gating with a hard "never pad" rule. **Alex's call (A + doc-cleanup):** accept ~22, value-over-count; B is justified on contradiction-type RICHNESS (denser harvest surface per agent) + 3-barrier wave stress, NOT on clearing the record. The "clears 31" framing is retired. A (drop the 4 added types) remains the fallback only if B can't converge to zero P0s.
8. **Codex round-2 (2026-07-21):** verify-harvest dedupes by `root_cause_id` (one root cause = one credited item) + distinct-FAILURES-row bijection; independent EARS added for all four Path-B types (happy + negative); firebreak teardown residual on hard crash made explicit (safe-closed, self-heals); C2 now disk-verifies `<R>/c2-smoke-report.md` (exercised set + planned/exercised deltas), not the exit code.

## Goal (corrected framing)

Run the **biggest *high-value* unattended autopilot-swarm build we can**, in a **throwaway app**, where
"value" = **how hard it stresses the unattended pipeline** (governance, coordination, assembly, tail) and
**how many durable pitfalls it harvests** (each pitfall makes every future run safer — that is the
compounding). The app is disposable; **the stress-and-harvest is the deliverable.** **The count is NOT
the point and this run does NOT attempt to clear the 31-agent record** (GigSheet Run 050): the honest
Path-B size is ~22 agents, and I1(>31) is non-gating — never padded, because a raw count teaches the
pitfalls engine nothing. "Biggest" here means highest-VALUE limit-test (governance stress + pitfall
harvest), consistent with the first-party rule that value ≠ agent count.

This replaces the Workflow-engine execution of Run 082, proven **UNLAUNCHABLE** (the JS engine cannot carry
the firebreak identity — origin solution doc). The manual autopilot skill runs **all** governance natively,
so the risk budget goes into limit-testing and harvesting, not gate reconstruction.

## Sizing Decision (CHOSEN: B — Alex, 2026-07-21; count-reality corrected at spec phase)

The deepen's simplicity pass, checked against Alex's OWN clean scale runs, found the honest de-padded
decomposition is **below the 31 record.** The first draft's ~44 was manufactured by a per-resource tests
cluster (absent from lesson-studio/GigSheet) + four clone-FK resources (invoices/payments/shipments/
returns re-instantiate `orders→order_items` with no new contradiction type). Per the **"first-party data
beats generic best-practice"** rule, his own run data won here — so the count is NOT padded back.

**CHOSEN — B: add NEW contradiction TYPES, not clones.** Distinct stressors: a soft-delete rule, a
status **state-machine** with illegal-transition guards, a **uniqueness-across-resources** constraint,
and a **second, structurally-different** cross-resource transaction (`process_return` touching
returns+shipments+products.stock+payments-refund). Higher value-per-agent; accepted the added convergence
risk. The whole plan below is written for B.

**⚠️ Count-reality correction (spec phase, 2026-07-21).** Authoring the actual spec showed the honest
Path-B roster is **~22 agents (19 build + 3 tail), NOT >31** — swarmlimit simply has fewer distinct
resources than lesson-studio's 14, so the 4 new TYPES rode existing resources without lifting the count
past 31. Rather than pad (forbidden; I1 is non-gating), **Alex chose A + doc-cleanup: accept ~22,
value-over-count.** B stands on contradiction-type RICHNESS + 3-barrier wave stress, and the "clears 31 /
biggest by count" framing is **retired**. If clearing 31 is ever wanted, it must be EARNED with more
*distinct* types (e.g. coupon/discount pricing, purchased-only reviews) as a deliberate future run — not
bolted on here. See spec §Projected Roster.

Rejected: **A-as-fallback** (drop the 4 added types) — kept only if path-B can't converge to zero P0s
pre-spawn. **C** (layered 3-wave tests-layer to ~38) — the tests layer is padding the simplicity pass
flagged; not chosen.

## App Shape & Coupling (vehicle optimized for stress, not baseline)

**`swarmlimit/`** — Flask + SQLite, app-factory, blueprint-per-resource. Resources chosen for **DISTINCT**
contradiction types (not clones). Core distinct stressors (keep all): `users→orders` (owner FK + role+own
auth), `orders+order_items+products` (multi-FK atomic transaction), `products→suppliers` (transitive
ownership chain), `categories↔products` (M2M), `audit_logs` (cross-cutting write on every mutation). For
path B adds four NAMED, independently-testable stressors (each proved by its own EARS below):
- **State-machine:** `shipments.status` legal path `pending→shipped→delivered` (+ `→returned` ONLY via `process_return`); any other transition → **409, status unchanged**.
- **Cross-resource uniqueness:** an `ext_ref` that must be globally unique across BOTH `orders` AND `returns` (no single resource owns it); a return reusing an order's `ext_ref` → **409**.
- **Soft-delete:** `products.deleted_at` — a soft-deleted product is excluded from `GET /products` and rejected by `create_order`, while historical `order_items` referencing it are **preserved** (soft, not cascade-hard).
- **Second transaction:** `process_return` atomically creates the return, advances `shipments.status→returned`, restocks `products.stock`, and writes a `payments` refund row — all-or-nothing.

**Coupling is pinned in the spec, not prose** (see §6-Section Spec). The `create_order` and `process_return`
transactions are the load-bearing stressors; the shared surface (auth decorator, error schema, audit
writer, PK-column contracts, transaction helper) is **Wave-0-owned and imported by every consumer** — else
the FKs/auth degrade to independent CRUD and surface no cross-section contradiction.

**Immutable planned manifest** (`<R>/planned-manifest.json`, frozen pre-spawn): resources + every endpoint
(method+path) + the two cross-resource transaction contracts + a content hash. `<R>` = `docs/reports/<run-id>/`
(skill-computed id; assert the dir is **absent** before writing — closes the run_id-collision false-green).

## Decomposition — layered merge-barrier waves (corrected; the DAG requires merge order, not parallel siblings)

Parallel siblings can't import each other (worktrees root on `origin/<default>`). The ONLY visibility
mechanism is merge-to-base-then-next-wave. So:

- **Wave 0 — shared surface (single-owner, ~2 agents):** app-factory + DB core (`get_db()` with
  `isolation_level=None`, `PRAGMA foreign_keys=ON`/`journal_mode=WAL`/`busy_timeout` per-connection),
  `transaction()` context manager (`BEGIN IMMEDIATE` + try/except/ROLLBACK), blueprint registry, shared
  error/response schema, auth core (`@require_owner(field=...)`), `audit_logs.record(actor_id, action,
  entity_type, entity_id)` (frozen signature, class-A, post-commit only), and **`smoke.py`** (the
  manifest-equality + value + atomicity + race + Path-B `--case` harness; it WRITES `<R>/c2-smoke-report.md`
  — line-1 `STATUS: PASS|FAIL`, recording the exercised (method,path) set, the `planned_minus_exercised` and
  `exercised_minus_planned` deltas, and any non-2xx — so C2 is disk-verifiable, not exit-code-only). Build → ownership-gate → **merge to base → push to
  `origin/<default>` → provenance re-verify (9w.9.5)**. Hard barrier. EARS gate: `swarmlimit/smoke.py`
  **compiles cleanly** (`python -m compileall swarmlimit`, parse check) against the base before any
  Wave-1 spawn; else abort + tear down firebreak.
- **Wave 1 — MODEL layer (all resources parallel):** each owns `swarmlimit/<resource>/model.py`. Cross-resource
  model imports minimal; tightly-coupled pairs co-assigned to one agent. Ownership-gate → merge → push →
  re-verify. Barrier.
- **Wave 2 — ROUTES layer (all resources parallel):** each owns `<resource>/routes.py`; model layer is now at
  the base so `routes→model` and cross-resource `orders→users/products` resolve at spawn. Barrier.
- **Wave 3 — integration/smoke tests (small):** cross-resource integration tests (exercise `create_order` /
  `process_return` across four resources) — a real cross-cluster consumer, NOT per-resource unit tests.
- **Tail (~6):** disconfirmer (Opus) → self-audit (Sonnet) → verify-self-audit (8 gates) → **verify-harvest**.

**Each Wave→Wave transition MUST push the merged layer to `origin/<default>` and re-run 9w.9.5 before the
next spawn** (FC52-BASEREF-FRESH-071 — the next wave roots on origin, not the local branch). This is the
single highest-risk seam; it is also the V2 limit probe (below).

## Brief Injection Matrix (per-cluster, beyond the 10 general classes + 6 bash rules)

`pitfalls-injection-validator` MUST pass pre-spawn confirming each brief carries its row:

| Cluster | Inject |
|---|---|
| Wave-0 shared | FC5 audit format (success AND failure paths), FC50 orchestration-entrypoint signatures, FC48 ghost-file, FC16 idempotent DDL, the SQLite pins |
| model | FC46 phantom-FK (`REFERENCES` + `ON DELETE` on every `*_id`), FC29+FC6 (no `conn.commit()` in helpers; `BEGIN IMMEDIATE` needs try/except/ROLLBACK), FC35 M24 model-layer ownership scoping, FC63 return-shape pinned, stock-guard SQL (`UPDATE ... WHERE stock>=:qty` + `rowcount==1`) |
| routes | FC50 entrypoint lookup (read Full Signature, never guess), FC63 assert return shape, FC35 route 403 after 404, audit is post-commit only |
| integration/smoke | FC63 assert on VALUES (no `{'`/`[object Object]`, integer ids), FC49 tempfile not `:memory:`, forced-failure atomicity + concurrency race, the 10 Path-B `--case`s + the `<R>/c2-smoke-report.md` writer |

**Path B constructs** (state-machine, `ext_ref` uniqueness, soft-delete, `process_return`) are pinned in the
spec and injected into their OWNING clusters — model owns the constraint/guard, routes owns the 409/exclusion;
`pitfalls-injection-validator` confirms each Path-B owner's brief names its guard.

## Governance — native (the simplification vs the Workflow plan)

`/autopilot` + `swarm: true` runs the full pipeline natively (verified live in the Phase-0 spike): 6
Mandatory Spec sections; 9w.5/9w.6/9w.7/9w.9/9w.9.5/9w.9.6; real `swarm-<run>-<role>` identities (the thing
the engine couldn't emit); assembly (blocking contract-check, ownership gate, `--no-ff`) → tail-runner →
disconfirmer(Opus) → self-audit → verify-self-audit (8 gates, Gate 8 bijection) → terminal disk-verify →
firebreak teardown. Required Artifacts: BUILD_TRACKING.md, self-audit, solution doc, HANDOFF.md, learnings,
plus this run's disk-verified gate artifacts: `<R>/c2-smoke-report.md`, `<R>/harvest-verification.md`.

## Firebreak Teardown — guarantee + residual (made explicit, not "airtight")

Teardown is guaranteed on every **handled** abort/throw path via the tail's `finally` (verified live in the
Phase-0 spike; `deactivate` is idempotent). **It is NOT airtight against a hard crash.** Residual, stated
plainly: a SIGKILL / OOM / host power-loss BETWEEN `activate` and the `finally` leaves the sentinel on disk —
nothing removes it at crash time. This residual is **bounded and safe-closed, never fail-open**: a stale
sentinel only OVER-gates (every subsequent tool call is classified/deferred, never trusted-through), and it
self-heals because `firebreak-activate.py activate` clears any stale sentinel at the START of the next run
(verified: "clear any stale sentinel first"); a human can also run `firebreak-activate.py deactivate` any
time. Honest claim: **no handled path leaks the sentinel; an unhandled crash can, until the next `activate`
or a manual `deactivate` clears it — over-gating in the interim, never under-gating.**

## 6-Section Spec (authored + converged BEFORE spawn — non-optional)

Port **lesson-studio's §5 Transaction Contracts + §6 Authorization Matrix** as the template (proven to
converge clean on this exact coupling). Pin, minimum:
- **Transaction taxonomy (3-class):** `create_order`/`process_return` OWN one `transaction()`; in-tx helpers
  (`add_item_in_tx(conn,...)`, `decrement_stock_in_tx(conn,...)`) take caller `conn`, do NOT commit; audit
  is the route's post-commit call, never inside a transaction.
- **Stock guard:** `UPDATE products SET stock=stock-:qty WHERE id=:pid AND stock>=:qty` + require
  `rowcount==1` else raise → rollback; `CHECK(stock>=0)` DB backstop. Re-read inside the transaction (TOCTOU-safe).
- **FK on-delete per edge:** CASCADE for parts (`order_items.order_id`), RESTRICT for financial/fulfillment
  (`invoices.order_id`, `payments.invoice_id`) and referenced parents (`products.supplier_id`).
- **Auth matrix:** 404-not-403 for `role+own` reads via ownership-scoped getters; transitive ownership
  (invoice owned via `orders.user_id`) stated per derived resource; route/validation/auth bijection.
- **Path B pins:** the `shipments` legal-transition table (allowed `from→to` set; all others → 409);
  `ext_ref` UNIQUE across orders+returns (enforced by a Wave-0-owned uniqueness check, since no single
  resource owns it); `products.deleted_at` soft-delete semantics (exclusion filter in EVERY read getter;
  `create_order` rejects deleted products; history preserved); `process_return`'s 3-class transaction
  contract (owner + in-tx helpers, `refund ≤ original payment` guard → rollback).

**Convergence loop (pre-spawn blocker):** Claude Code (structure) → Codex (contradictions) → NotebookLM
(data) → fix → Codex clean → **human structural verification** (P0s survive all 3 AI passes — non-optional).
Only then 9w.5/9w.6/contract/smoke. If ~N coupled clusters can't reach zero P0s, **reduce coupling until
they can** — a clean smaller run beats a contradictory bigger one.

## Pitfall-Harvest — evidence-backed, gated (V1, the value capture)

The first-draft V1 (`grep -c "$(date +%F)"`) was gameable — a date stamp passed it. Hardened:
- **Baseline pre-run:** freeze `agent-pitfalls.md` failure-class-ID set + line count into `<R>/pitfalls-baseline.txt` (Wave-0 artifact).
- **Structured harvest record** (mandated Update Log entry): `fc_id` (FCnn|NEW) · `status` (net-new|new-variant|confirmed) · **`root_cause_id`** (a stable slug naming the underlying defect, e.g. `RC-<resource>-<short-slug>`; two rows describing the SAME underlying issue MUST share it) · `evidence` (path:line in a **specific** BUILD_TRACKING FAILURES row / gate-verification / smoke-output / ownership-violation) · `originating_agent` (`swarm-<run>-<resource>-<layer>`) · `what_it_teaches`.
- **`verify-harvest` gate** (mirrors verify-self-audit; writes `<R>/harvest-verification.md STATUS: PASS|FAIL`), asserting ALL of: (a) **≥5 items with DISTINCT `root_cause_id`** — rows sharing a `root_cause_id` collapse to ONE credited item BEFORE the count, so one underlying issue split across many rows cannot pad the total (8 rows on 3 root causes = 3 → FAIL); (b) **each item binds to a DISTINCT BUILD_TRACKING FAILURES row** (one FAILURES row backs at most one harvested item — a single failure event cannot spawn five "findings"); (c) every `evidence` path resolves to a real failure/retry/miss token (a "confirmed" whose only evidence is "was injected" is REJECTED — anti-gaming core); (d) **≥2 of the 5 distinct-root-cause items are net-new/new-variant** (anti-circularity — can't just re-confirm the injected list).
- A run that harvests < 5, or un-traceable findings, reports **low-value/hollow** even if green — and the self-audit must include a root-cause note on why so much coupled surface yielded so little (that note is itself a harvest).

## Deliberate Limit Probe (V2 — falsifiable, with an observable)

**Pre-registered hypothesis:** the ownership-gate cherry-pick assembly + the Wave→Wave provenance-re-verify
seam has never run at this fan-out across 3–4 sequential merge barriers; predict a specific failure — e.g. a
later-wave cluster roots on a base missing the prior wave because it wasn't pushed to `origin/<default>`
before spawn (FC52). **Observable:** `<R>/assembly-order.log` shows a wave spawned against a base whose
`git rev-parse origin/<default>` lacks the prior wave's merge SHA. Record held / near-miss / broke + the
pitfall. Context/budget death stays a **separate minimal loop** (Run 081: 430K-char proxy = 215% of protocol
budget but 54% of the real 800K window — don't abort the valuable run on a context warning; reserved
tail-budget floor guarantees the harvest runs).

## Acceptance Tests (EARS; `<R>=docs/reports/<run-id>/`, skill-computed id)

### Happy Path
- WHEN the run completes THE SYSTEM SHALL have run unattended with **0 human interventions** (A1, gating). — BUILD_TRACKING shows no human-intervention events.
- WHEN Wave 0 completes THE SYSTEM SHALL verify its artifacts are merged+pushed to `origin/<default>` AND `swarmlimit/smoke.py` **compiles cleanly** (parse check) against the base before any Wave-1 spawn; on failure abort + tear down firebreak. — `python -m compileall swarmlimit` against base → exit 0. (Parse-only, not a full import: `swarmlimit/smoke.py` is in-package so `compileall` covers it, and it avoids the FC8/repo-Bash `python -c` prohibition; a full import that executes `create_app`→route registration can't resolve until routes exist post-assembly.)
- WHEN each Wave→Wave transition occurs THE SYSTEM SHALL push the merged layer to `origin/<default>` and re-run 9w.9.5 before the next spawn. — `<R>/assembly-order.log` shows every wave's base contains the prior wave's merge SHA.
- WHEN 9w.5/9w.6 pass THE SYSTEM SHALL write `STATUS: CLEARED` to `<R>/gate-verification.md` and only then spawn. — `grep -m1 STATUS <R>/gate-verification.md` → CLEARED.
- WHEN assembly completes THE SYSTEM SHALL run `smoke.py`, which WRITES `<R>/c2-smoke-report.md` recording the exercised (method,path) set + planned-vs-exercised deltas, and the tail SHALL **disk-verify that artifact** (not the exit code alone): C2 passes iff line-1 `STATUS: PASS` AND both deltas are empty AND no non-2xx (C2, gating). — `python -m swarmlimit.smoke --manifest <R>/planned-manifest.json` then `grep -m1 STATUS <R>/c2-smoke-report.md` → `PASS` AND `grep -A2 'planned_minus_exercised' <R>/c2-smoke-report.md` shows both delta sets empty.
- WHEN `create_order` succeeds THE SYSTEM SHALL commit orders+order_items+stock atomically **and record audit POST-commit** (audit is class-A, never inside the transaction — FC5/FC6; corrected from an earlier "…+audit atomically" wording that contradicted the injection matrix + Wave-0 spec); values assert integer ids and NO `{'`/`[object Object]` in rendered JSON. — smoke value assertions pass.
- WHEN two `create_order` calls race the last unit of stock THE SYSTEM SHALL let exactly one succeed, the other raise `insufficient stock`, final stock non-negative and correct. — smoke concurrency case.
- WHEN a forced failure fires AFTER the first writes but BEFORE commit THE SYSTEM SHALL leave all four tables (orders, order_items, products.stock, audit_logs) unchanged. — smoke rollback case with before/after counts.
- **(Path B — state-machine)** WHEN a shipment is advanced along a legal transition (`pending→shipped`, then `shipped→delivered`) THE SYSTEM SHALL update `status` and write an audit row. — `python -m swarmlimit.smoke --case state-machine-legal; echo $?` → 0.
- **(Path B — uniqueness)** WHEN an `ext_ref` is unique across orders+returns THE SYSTEM SHALL accept the create and persist it. — `python -m swarmlimit.smoke --case uniqueness-ok; echo $?` → 0.
- **(Path B — soft-delete)** WHEN a product is soft-deleted THE SYSTEM SHALL set `deleted_at`, exclude it from `GET /products`, and preserve historical `order_items` referencing it. — `python -m swarmlimit.smoke --case soft-delete; echo $?` → 0.
- **(Path B — 2nd transaction)** WHEN `process_return` succeeds THE SYSTEM SHALL atomically create the return, set `shipments.status=returned`, restock `products.stock`, and write a `payments` refund — all four visible together. — `python -m swarmlimit.smoke --case process-return; echo $?` → 0.
- WHEN verify-self-audit runs THE SYSTEM SHALL pass all 8 gates incl. Gate 8 bijection. — `grep -m1 STATUS <R>/verify-self-audit.md` → PASS.
- WHEN verify-harvest runs THE SYSTEM SHALL confirm ≥5 **distinct-`root_cause_id`** pitfalls (≥2 net-new/variant), each bound to a **distinct** BUILD_TRACKING FAILURES row (V1, value gate). — `grep -m1 STATUS <R>/harvest-verification.md` → PASS.
- WHEN the run completes THE SYSTEM SHALL report the actual agent count (I1, non-gating). — BUILD_TRACKING RUN_METRICS.

### Error Cases
- WHEN 9w.6 FAILs twice THE SYSTEM SHALL abort before any spawn. — no worker in BUILD_TRACKING.
- WHEN a worker diff contains an out-of-assignment file THE SYSTEM SHALL abort that merge + write `<R>/ownership-violation.md STATUS: FAIL`.
- WHEN the contract-check FAILs twice THE SYSTEM SHALL abort without merge and tear down the firebreak. — `test ! -f .claude/firebreak-active.json`.
- WHEN any gate aborts THE SYSTEM SHALL still deactivate the firebreak (finally). — `test ! -f .claude/firebreak-active.json`.
- WHEN self-audit claims PIPELINE_PASS with undisposed WARNs or A-grade with unjustified DEFERRED+HIGH THE SYSTEM SHALL fail (Gates 5/7f).
- WHEN harvest < 5 or findings untraceable THE SYSTEM SHALL report low-value/hollow (V1 fail) + a root-cause note in self-audit.
- WHEN `docs/reports/<run-id>/` pre-exists at launch THE SYSTEM SHALL abort (run_id-collision guard). — `test ! -d docs/reports/<run-id>` before manifest freeze.
- **(Path B — state-machine)** WHEN an illegal shipment transition is attempted (`delivered→pending`, or `pending→delivered` skipping `shipped`) THE SYSTEM SHALL return 409 and leave `status` unchanged. — `python -m swarmlimit.smoke --case state-machine-illegal; echo $?` → 0 (asserts 409 + status unchanged).
- **(Path B — uniqueness)** WHEN a return reuses an existing order's `ext_ref` THE SYSTEM SHALL return 409 and create no return row. — `python -m swarmlimit.smoke --case uniqueness-collision; echo $?` → 0 (asserts 409 + `count(returns)` unchanged).
- **(Path B — soft-delete)** WHEN `create_order` references a soft-deleted product THE SYSTEM SHALL reject (400/409) and create no order. — `python -m swarmlimit.smoke --case soft-delete-order; echo $?` → 0 (asserts rejection + no partial rows).
- **(Path B — 2nd transaction)** WHEN `process_return` fails mid-transaction (refund exceeds the original payment) THE SYSTEM SHALL roll back all four writes (no return, no status change, no restock, no refund). — `python -m swarmlimit.smoke --case process-return-rollback; echo $?` → 0 (before/after counts unchanged on all four tables).

## Success Metrics

**Hard gate:** **A1** (zero-touch) ∧ **C2** (smoke `planned==exercised==passing` + atomic + race) ∧ **V1**
(≥5 distinct-`root_cause_id` pitfalls, ≥2 net-new, distinct FAILURES-row bijection, verify-harvest PASS) ∧ **V2** (pre-registered limit pushed, observable recorded).
**Instrumentation (non-gating):** **I1** actual count (pass iff >31; **failing I1 does NOT fail the run** —
never pad to clear it) · **C1** governance ran (all gates fired, zero surviving cross-section P0s).

## Dependencies & Risks
- **P0 — hollow run.** Mitigation: verify-harvest gate + distinct-not-clone coupling + de-padded sizing.
- **P0 — governance false-green** (missed gate / stale run-id dir / date-stamp harvest). Mitigation: native pipeline + verify-self-audit + run_id-collision guard + evidence-backed harvest.
- **P0 — C2 machinery unowned.** Mitigation: `smoke.py` is a Wave-0 single-owner deliverable, frozen pre-Wave-1.
- **P1 — decomposition infeasibility** (parallel siblings). Mitigation: layered merge-barrier waves + push-to-origin-before-next-wave.
- **P1 — coupling degrades to independent CRUD.** Mitigation: shared symbols Wave-0-owned + imported (Export Names + Wiring rows).
- **P1 — data corruption masking signal** (unpinned transaction/stock/FK-delete). Mitigation: port lesson-studio §5/§6 + the 4 P0 pins.
- **P1 — bash rules / pitfalls injection** per brief (validator pre-spawn).
- **P1 — `smoke.py` is a large single-owner Wave-0 deliverable** (manifest-equality + value + atomicity + race + 10 Path-B `--case`s + the C2 report writer). If it is wrong or incomplete, C2 AND every Path-B proof are unverifiable. Mitigation: frozen + import-checked against the base before Wave 1; its `--case`s are enumerated in the EARS; treat it as a first-class spec'd artifact, not glue.
- **P2 — firebreak teardown residual on hard crash** (SIGKILL/OOM between activate and the `finally`) leaves a stale sentinel. Bounded + safe-closed: over-gates, never fails open; self-heals at the next `activate`. Made explicit (see §Firebreak Teardown), not claimed away.
- **Wall-clock/cost:** 3–4 sequential barriers + Opus tail = the most expensive run yet; reserved tail budget so harvest always completes. If appetite is limited, prefer path A (drop the 4 added types) over cutting the tail/harvest.

## Spec-Phase Resolutions (R1–R3 — closed 2026-07-21)

The shared-interface spec is now authored + convergence-ready:
`docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md` (all 6 mandatory sections,
Model Functions, Route Table, EARS, 10 Path-B `--case`s, planned manifest). The three open spec-phase
items from the last review are resolved:

- **R1 — Wave-0 overload → SPLIT into 5 single-owner agents.** The three overloaded concerns are now
  on distinct owners: (a) `smoke.py` + `<R>/pitfalls-baseline.txt` → **smoke-author**; (b) the
  `ext_ref` cross-resource uniqueness owner (`refs.py`) + the audit writer (`audit_models.py`) →
  **shared-services**; (c) app-factory / DB core / auth stay on scaffold / database / auth-core. So
  Wave 0 = {scaffold, database, auth-core, shared-services, smoke-author}. No agent carries smoke +
  ext_ref + baseline together. (This nudges the count up slightly — fine for Path B.)
- **R2 — smoke.py is AUTHORED + parse-checked in Wave 0 but EXECUTED post-assembly.** Wave-0 EARS
  gate is `python -m compileall swarmlimit` against the base — a PARSE check (covers `swarmlimit/smoke.py`
  since it is in-package; avoids the FC8/repo-Bash `python -c` prohibition). Its route/`--case` assertions and the manifest-equality check CANNOT pass until
  Wave 2 merges (routes exist), so they run at the **assembly C2 step**, not in Wave 0. Pinned in the
  spec's §Namespace note and the C2 EARS.
- **R3 — ownership: smoke-author owns ALL testing; Wave-3 integration layer is CUT.** `smoke.py`
  (smoke-author) solely owns the manifest-equality check, the 10 Path-B `--case` harness, the core
  cases (value/concurrency/rollback/IDOR/CSRF/SECRET_KEY), AND the cross-resource integration
  exercise (create_order + process_return span four resources inside the cases). There is **no
  separate Wave-3 integration agent** — it would double-own the cross-cluster test surface. The
  simplicity finding wins: one testing owner, no Wave-3. Waves are now 0→1(model)→2(routes)→tail.

**Honest projected count (spec §Projected Roster): ~19 build + ~3 tail ≈ 22 agents — BELOW 31.**
This is acceptable under this plan's own I1 rule (instrumentation-only, never pad). ⚠️ It does mean
Path B as-specified does NOT clear 31 at honest granularity; the Path-B-over-A case now rests on
**contradiction-type richness / harvest surface**, not count. If genuinely clearing 31 is wanted it
must be EARNED with additional *distinct* types (coupon/discount pricing, purchased-only reviews) at
launch — a deliberate decision, out of scope for convergence. Flagged for Alex.

## Feed-Forward
- **Hardest decision:** redefining "biggest" as highest-value limit-test — then, at the spec phase, accepting that the honest Path-B roster is ~22 agents (NOT >31) and **retiring the "clears 31" goal entirely** rather than padding to chase a symbolic record. Value = contradiction-type richness + harvest, per the first-party rule that count ≠ value.
- **Rejected alternatives:** Workflow engine (UNLAUNCHABLE); ~40 uncoupled CRUD agents (hollow); clone-FK resources / per-resource test clusters (padding the sizing).
- **Least confident:** two coupled uncertainties, both pre-spawn-checkable (which is why they're least-confident, not unmitigated). (1) Whether path-B's added contradiction types (state-machine, uniqueness, second transaction, soft-delete) converge to zero P0s pre-spawn — if not, fall back to path A (drop the 4 added types); a clean ~22 beats a contradictory bigger one. (2) Whether the now-substantial single-owner `smoke.py` (C2 manifest-equality + the C2 report + all ten Path-B `--case` proofs) is itself correct — a bug there makes C2 and every Path-B EARS unverifiable. Gate (1) via the convergence loop; gate (2) via import-check + case enumeration before Wave 1.

## Codex Handoff Prompt

```
Second-pass review of a DEEPENED plan for the biggest HIGH-VALUE unattended autopilot-swarm run (manual
/autopilot, NOT the Workflow engine — that's UNLAUNCHABLE): docs/plans/2026-07-21-feat-082-max-value-unattended-autopilot-limit-test-plan.md

Already revised against a 7-agent deepen. Ground truth: autopilot SKILL.md 5.5–18w, verify-self-audit 8
gates, lesson-studio + GigSheet solution docs. VALIDATE the fixes; hunt what remains. Focus:
1. Value-not-count: is V1 (verify-harvest: ≥5 traced, ≥2 net-new, evidence resolves to FAILURES rows,
   anti-circularity) genuinely non-gameable, or still theater? Is C2's "exercised" set capture real?
2. Sizing: is path B (new contradiction TYPES — state-machine, uniqueness, 2nd transaction, soft-delete) a
   genuine value increase over the honest ~25, or re-padding under a new name?
3. Decomposition: are the layered merge-barrier waves (model→routes→smoke) correct given worktrees root on
   origin/default? Is the push-to-origin-before-next-wave step (FC52) sufficient, or is there still a seam
   where wave N+1 can't see wave N?
4. Coupling: do the Wave-0-owned shared symbols (auth decorator, audit writer, transaction helper, PK
   contracts) actually prevent degradation to independent CRUD? Are the §5/§6 pins (3-class transaction,
   stock-guard SQL, FK on-delete per edge, 404-not-403) complete?
5. run_id-collision guard + firebreak teardown on every abort path — airtight?
6. EARS: every negative-path fixture executable? Is the atomicity smoke (inject-after-first-write) + the
   concurrency stock-race real?

Return P0/P1/P2. P0 = a way the run passes green while hollow, OR a bypassed mandatory gate, OR sizing that
pads the count.
```
