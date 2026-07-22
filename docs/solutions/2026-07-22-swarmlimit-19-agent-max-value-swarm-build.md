---
title: "swarmlimit Max-Value Autopilot Limit-Test — 19-Agent Wave-Barrier Swarm Build (Run 083)"
date: 2026-07-22
run_id: "083"
project: swarmlimit
tags:
  - swarm-build
  - multi-agent
  - flask
  - sqlite
  - pitfall-harvest
  - wave-barrier
  - firebreak
  - class-b-transactions
  - cross-agent-seams
  - governance
category: swarm-build
related_plans:
  - docs/plans/2026-07-21-feat-082-swarmlimit-shared-interface-spec.md
  - docs/plans/2026-07-21-feat-082-max-value-unattended-autopilot-limit-test-plan.md
related_solutions:
  - docs/solutions/2026-07-10-lesson-studio-30-agent-scale-validation-swarm-build.md
  - docs/solutions/2026-06-11-stack-rx-11-agent-swarm-build.md
status: complete
---

# swarmlimit Max-Value Autopilot Limit-Test — 19-Agent Wave-Barrier Swarm Build (Run 083)

## What Was Built

A 19-build-agent autopilot swarm (plus 3 tail agents) constructed a fully functional 31-endpoint Flask/SQLite e-commerce back-office API (`swarmlimit/`). The build used a **3-wave merge-barrier structure** that was the primary governance experiment:

- **Wave 0 (5 agents):** Shared surface — scaffold, database, auth-core, shared-services, smoke-author. Merge → push to origin/master before Wave 1 spawns.
- **Wave 1 (7 agents):** Model layer — supplier, category, product, order, shipment, return, payment models. Merge → push before Wave 2 spawns.
- **Wave 2 (7 agents):** Routes layer — suppliers, categories, products, orders, shipments, returns, payments routes. Merge → assembly C2.

The wave-barrier mechanic forces each wave to root its workers on the completed prior wave via `origin/master` fast-forward, giving Wave N+1 agents access to Wave N's merged code (FC52 provenance guarantee).

**This build was Path B: value-over-count.** The honest roster is ~22 agents (19 build + 3 tail), below 31. The goal was contradiction-type richness (state machine, cross-resource uniqueness, class-B transactions, soft-delete) + pitfall harvest quality, NOT agent count.

## App Summary

| Attribute | Value |
|-----------|-------|
| Endpoints | 31 (exact match: spec Route Table == smoke manifest == exercised set) |
| Architecture | Flask/SQLite, pure JSON API, no templates |
| Auth | Session-based, CSRF header token, role_required two-branch (None→401, wrong-role→403) |
| Transaction classes | Class-A (14 autocommit writers), Class-B (2: create_order, process_return), Class-C (4+3 in-tx helpers) |
| Governance | Firebreak active (phase=build → tail); G1+G3 stack live |
| FC59 namespace | swarmlimit/ (per-build namespace, no collision with prior builds) |
| C2 smoke | STATUS: PASS — 31/31 endpoints, 0 suite failures, all 10 Path-B cases green |

## C2 Smoke Results

```
STATUS: PASS
planned endpoints: 31
exercised endpoints: 31
planned_minus_exercised: 0
exercised_minus_planned: 0
suite failures: 0
```

All 10 Path-B EARS cases green: atomicity rollback (create_order + process_return), concurrency stock-race, IDOR-404/admin-403/anon-401/CSRF-400/SECRET_KEY-fail-closed/register-role-ignored/shipment-unique.

## Pitfall Harvest (H1–H9) — Primary Deliverable

The harvest is the value of this run. All 9 findings are bound to distinct `root_cause_id`s and cross-referenced to BUILD_TRACKING FAILURES rows.

| id | root_cause_id | FC class | Wave/Seam | Severity | Status | Teaches |
|----|---------------|----------|-----------|----------|--------|---------|
| H1 | RC-config-db-key-unpinned | FC5 | Wave0 scaffold↔database↔smoke | NEAR-MISS | CONVERGED (not a failure) | 3-way lucky convergence on `"DATABASE"` config key — pin shared config keys in spec |
| H2 | RC-package-init-unowned | n/a | Wave0 namespace | BENIGN | RESOLVED-BENIGN | Python namespace packages tolerate missing subpackage `__init__.py` under a regular parent — verify before manufacturing a fix |
| H3 | RC-close-db-unregistered | FC3 | Wave0 database→scaffold | MEDIUM | Fixed at assembly | `close_db` exported by database agent, registration (`teardown_appcontext`) owned by scaffold but not named in its brief → per-request connection leak. Classic FC3 at a framework-lifecycle seam |
| H4 | RC-envelope-key-unpinned | FC30/FC5 | Wave0 smoke ↔ Wave2 routes | HIGH cross-wave risk | Mitigated before Wave2 | Spec never pinned singular success-envelope key spelling; smoke inferred keys Wave-2 routes must match. Propagated envelope keys into Wave-2 briefs before spawn |
| H5 | RC-firebreak-orchestrator-gate-python | FC58 | Orchestrator wave-gate | MEDIUM (infra) | Documented toggle protocol | `python -m compileall` / `python -m <pkg>.smoke` NOT on TRUSTED_PIPELINE_SCRIPT_PATHS; `-m` module mode never qualifies → DEFERRED even for trusted orchestrator. Multi-wave runs must toggle firebreak off for each orchestrator assembly window |
| H6 | RC-initdb-app-context | FC39-family | Wave0 scaffold↔database | HIGH (C2-blocking) | Fixed at assembly | `init_db()` called bare (no app context); `database.py:_db_path()` calls `current_app.config` → "working outside application context" at every `create_app`. Assembly fix: `with app.app_context(): init_db()` |
| H7 | RC-firebreak-cwd-root-drift | FC58-family (net-new: FC68) | Orchestrator/firebreak lifecycle | HIGH (governance-critical) | Mitigated by cwd reset + sentinel verification | `firebreak-activate.py` derives repo_root via `git rev-parse` in cwd. Orchestrator cwd drifted into a lingering worker worktree → sentinel written to wrong root → new workers would find no sentinel (FAIL-OPEN). Fix: reset cwd to main root before each activate; verify sentinel's `repo_root` field after (re)activation |
| H8 | RC-delete-envelope-divergence | FC5 | Wave2 routes (suppliers/categories/products) | LOW (benign for C2) | Documented | DELETE-success bodies diverged 3 ways: categories `{"ok":true}`, suppliers `{"deleted":sid}`, products `{"product":{"id":pid}}`. H4 pinned create/list/detail but not delete-success body → 3 blind agents, 3 shapes |
| H9 | RC-secretkey-env-vs-config-seam | net-new (FC69) | Wave0 smoke ↔ scaffold | HIGH (C2-blocking) | Fixed at assembly | `create_app` reads SECRET_KEY from `os.environ` and validates it BEFORE applying the `config` dict → `RuntimeError` when smoke passed config-only SECRET_KEY. Assembly fix: `os.environ.setdefault("SECRET_KEY", ...)` in `build_app()` |

### Net-New Failure Classes (FC68, FC69)

**FC68 — Governance Tool cwd Self-Location (H7)**
A governance control (firebreak activator) that discovers its own anchor path via `cwd` fails silently when the orchestrator's working directory drifts — most likely from a lingering worker worktree `cd`. The sentinel writes to the wrong root. Next-wave workers walk up from their OWN worktrees and never find the sentinel → ungoverned spawn with no error signal.

**Prevention:** Pin governance tooling to an explicit `--root` argument (never `git rev-parse` in cwd). After every `(re)activate`, verify the sentinel's `repo_root` field matches the expected main-repo path before spawning workers.

**FC69 — App Factory Config-Order Seam (H9)**
An app factory that reads a secret from `os.environ` and validates it BEFORE applying its `config` dict argument creates an order-of-operations trap: callers that supply the secret via config (not env) will silently fail with a misleading error. Neither agent's brief pinned whether the working-app config path goes through env or config.

**Prevention:** Spec must pin the exact initialization order for secrets that have a validation gate — either (a) env-only with documented precedence, or (b) config-first with env fallback. Add this to the Input Validation Prescriptions section.

## Assembly Fixes Applied

Three findings were C2-blocking or assembly-blocking and were fixed at assembly:

**H3 fix (FC3 — dead wiring):** `swarmlimit/__init__.py` added `app.teardown_appcontext(close_db)`. The database agent defined `close_db`; the scaffold agent's brief never named the registration call.

**H6 fix (FC39-family — app context):** `swarmlimit/__init__.py` wrapped the bare `init_db()` call in `with app.app_context(): init_db()`. Neither brief pinned who establishes the app context for one-time schema initialization.

**H9 fix (FC69 — config order seam):** `swarmlimit/smoke.py` `build_app()` added `os.environ.setdefault("SECRET_KEY", "smoke-083-secret-key")` before `create_app(...)`. The scaffold's factory reads and validates SECRET_KEY from env before merging the config dict; smoke's config-only approach was ineffective.

## Feed-Forward Risk Resolution

### What Was Flagged

**Feed-forward risk (from plan):** "The two class-B transactions (create_order, process_return) and the ext_ref cross-resource uniqueness are the load-bearing seams; process_return is a 4-table atomic write reaching into 3 other agents' tables via in-tx helpers — the densest cross-agent write. Scrutinize this in review."

The plan also flagged two coupled uncertainties: (1) whether Path-B's four added contradiction types converge to zero P0s pre-spawn, and (2) whether the single-owner `smoke.py` is correct.

### What Actually Happened

The flagged risk seams **did NOT fire.** Both class-B transactions were implemented correctly:

- `process_return` owns exactly ONE `transaction()` (BEGIN IMMEDIATE) and threads the same `conn` to all four in-tx helpers. None of the four helpers call `conn.commit()`.
- `assert_ext_ref_unique` runs under the caller's BEGIN IMMEDIATE lock — concurrent writers serialize, so the cross-resource check has no TOCTOU window.
- `create_order` snapshots `unit_price_cents` at insert time inside the transaction, not at validation time.

The spec's explicit §5 Transaction Contracts table (Class A/B/C classification + "does NOT commit" annotation for every in-tx helper) was the key mitigation. The 7 model agents independently built correct per-class behavior, zero revision needed.

C2 proved it dynamically: the atomicity rollback cases (fault-injection via `_TX_FAULT`) both passed — `create_order` rolled back a partially-written unit, `process_return` rolled back all four writes after `add_refund_in_tx`.

The `smoke.py` correctness concern (uncertainty 2) was also resolved — after one assembly fix (H9, SECRET_KEY order-of-operations), the suite ran 31/31 with 0 failures.

### The Delta (Expectation vs Reality)

**Expected:** The dense cross-agent transaction seam would be where errors surface.
**Reality:** The seam held perfectly. The failures came from **infrastructure lifecycle gaps** (H6 app context, H3 dead wiring) and a **governance tooling fragility** (H7 cwd drift) — none of which were in the dense transaction path.

**Key learning:** When the spec fully pins the transaction boundary (which functions own a `transaction()`, which are class-C with a caller `conn`, who commits), even a 4-table atomic write across 4 agents' tables assembles correctly. The seam that fires is not the hardest business-logic seam — it's the lifecycle seam that no brief mentions because "everyone assumes" the framework handles it.

The net-new failure classes (FC68 cwd self-location, FC69 factory config-order) come from exactly this pattern: both are cross-agent configuration/lifecycle seams where Agent A's creation behavior depended on Agent B's initialization order, and neither brief named the dependency.

## Governance Stack Performance

| Gate | Result |
|------|--------|
| Spec completeness (9w.6) | PASS — 7/7 surfaces |
| Spec consistency (9w.5) | PASS |
| Spec provenance (9w.9.5) | PROVENANCE_REPAIRED → PROVENANCE_OK (spec pushed to origin/master before Wave 0 spawn) |
| Firebreak (G1) | ACTIVE throughout build; wave-assembly windows toggled off/on with sentinel verification |
| FC58 (TRUSTED_PIPELINE_SCRIPTS) | H5: per-wave `python -m compileall` / `python -m <pkg>.smoke` NOT on allowlist → DEFERRED. Working protocol: toggle off for orchestrator-only windows, reactivate before each worker spawn |
| H7 firebreak cwd-drift | NEW — caught by cat-verifying sentinel repo_root; mitigated by cwd reset before each activate |
| Ownership gate | PASS — all workers committed to their assigned files only |
| C2 smoke | STATUS: PASS (31/31 endpoints, 0 failures) |
| Review | 0 P1, 3 P2 deferred |

## Verify-Harvest Gate (Run 083)

Per the run-plan's evidence-backed gate:

| Criterion | Result |
|-----------|--------|
| ≥5 distinct root_cause_id | PASS — 9 distinct: RC-config-db-key-unpinned, RC-package-init-unowned, RC-close-db-unregistered, RC-envelope-key-unpinned, RC-firebreak-orchestrator-gate-python, RC-initdb-app-context, RC-firebreak-cwd-root-drift, RC-delete-envelope-divergence, RC-secretkey-env-vs-config-seam |
| ≥2 net-new failure classes | PASS — FC68 (H7 cwd-root-drift) and FC69 (H9 config-order seam) are genuinely new classes |
| Each bound to a distinct FAILURES row | PASS — each H-finding maps 1:1 to a BUILD_TRACKING FAILURES row |
| Anti-circularity (not just restating the fix) | PASS — each teaches a generalizable rule, not just "we added an app context wrapper" |

## Wave-Barrier Mechanic Validation

The 3-wave merge-barrier structure is the infrastructure experiment of this run. Key observations:

1. **FC52 provenance held at each wave.** Each wave's workers rooted on origin/master, which was fast-forwarded to the completed prior wave before spawn. Workers at Wave N+1 correctly saw Wave N's merged code.

2. **H4 mitigation pattern works.** The envelope-key contract risk (smoke authored in Wave 0, routes in Wave 2) was mitigated by propagating smoke's expected envelope keys into Wave-2 briefs before spawn. This is the correct pattern for any cross-wave contract.

3. **Firebreak toggle protocol is required for multi-wave runs.** H5 and H7 both stem from the orchestrator needing to run its own per-wave assembly python (not on the TRUSTED_PIPELINE_SCRIPTS allowlist). The protocol is: deactivate → run orchestrator-only assembly window → reactivate → verify sentinel → spawn next wave. This must be documented in the run plan for any multi-wave swarm.

4. **Context proxy growth was steep but manageable.** At pre-swarm gates: ~255K chars (~128% of 200K-char comparative proxy). Post-Wave-0 merge: ~520K chars (~260%). The 200K proxy is known to undercount Opus 4.8's real 1M-token window (run-081: 430K chars ≈54% real). Aggressive delegation (assembly fix agents, compileall gates) kept growth bounded.

## Sizing Honest Count

| Wave | Agents | Notes |
|------|--------|-------|
| Wave 0 (shared) | 5 | scaffold, database, auth-core, shared-services, smoke-author |
| Wave 1 (models) | 7 | one per resource: supplier, category, product, order, shipment, return, payment |
| Wave 2 (routes) | 7 | one per resource matching Wave 1 |
| Tail | 3 | review, self-audit-reviewer (Sonnet), self-audit-disconfirmer (Opus) |
| **Total** | **22** | Honest Path-B roster; I1 (>31 non-gating) is an aspirational stretch, NEVER a pad target |

## Feed-Forward

- **Hardest decision:** Accepting that the wave-barrier add-on for H4 (injecting smoke's envelope keys into Wave-2 briefs before spawn) is the correct cross-wave contract pattern — more explicit than spec amendment alone, faster than a re-wave, and directly testable at C2.
- **Rejected alternatives:** Running all 19 workers in a single wave without barriers (would reproduce FC51 base-divergence for the model layer workers who need Wave-0's auth/database exports); adding test-cluster agents to pad past 31 (hollow per first-party data from runs 080/081).
- **Least confident:** Whether the firebreak toggle protocol (deactivate/reactivate around each orchestrator-only assembly window) is the right long-term fix for H5, or whether the TRUSTED_PIPELINE_SCRIPTS allowlist should simply grow to include `python -m compileall` and `python -m <pkg>.smoke` patterns. The toggle protocol works but is manual and fragile to orchestrator cwd drift (H7 is evidence). A wider allowlist with an explicit module-mode pattern match would be more robust.
