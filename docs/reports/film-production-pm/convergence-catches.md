# Convergence Catches — Film Production PM (validation probe)

**Spec:** docs/plans/film-production-pm-plan.md (2010 lines, 16-agent swarm)
**Date:** 2026-06-08
**Purpose:** Per `docs/roadmap-to-fully-unattended.md` §6 — log every defect this attended convergence pass catches, classified by whether an automated gate would have caught it. Human-only catches are the blueprint for the next hardening gate (A1/A2/A4).

---

## Catch ledger

Severity: P0 = build-breaking / data corruption · P1 = functional defect · P2 = security/quality · L = low.
Gate column: **EXISTING** = a current gate (9w.6) should catch it → validates a shipped track. **HUMAN-ONLY** = no current gate catches it → derives a future gate.

| # | Sev | Finding | Sections in conflict | Gate | Derives |
|---|-----|---------|----------------------|------|---------|
| F-G1 | P1 | **Track B blind spot.** Export Names Table declares ZERO `orchestration entrypoint` rows, so the FC50 guard (Check 1b) returns **N/A and passes** — it never fires on the 6 call-sheet cross-boundary imports, which are the exact FC50 drift risk. The guard only checks *declared* entrypoint rows (documented blind spot in the checker). Gate is BLIND here, not catching. | Export Names Table vs spec-completeness-checker Check 1b | **HUMAN-ONLY (gate N/A)** | Spec-template fix: REQUIRE orchestration-entrypoint rows for known cross-boundary call surfaces, so the guard actually fires |
| F-H1 | **P0** | **FTS double-maintenance.** Schema declares BEFORE triggers on scenes/cast/crew/locations that maintain `search_index`, AND the wiring table has those same routes calling `index_entity`/`remove_entity` explicitly. Both fire → contentless FTS5 gets double-indexed (dup search rows; delete removes only one). | Database Schema (triggers) vs Cross-Boundary Wiring (route calls) vs Model Functions (index_entity) | **HUMAN-ONLY** | "single-writer responsibility" gate — flag when two subsystems both mutate one store |
| F-H2 | **P0** | **FTS trigger ownership impossibility.** Triggers are assigned to the *search agent* (schema comment) but `CREATE TRIGGER` must live in `schema.sql`, owned by the *database agent*. Search agent owns no file that can hold them → triggers never created or ownership-gate violation. | schema.sql comment vs File Assignment Boundaries (agent 14 vs 15) | **HUMAN-ONLY** | "artifact-location vs owner" cross-check gate |
| F-H3 | **P1** | **`VALID_TRANSITIONS` undefined.** Input Validation references `VALID_TRANSITIONS[current]` for both project phase and scene status, but the actual allowed-transition maps are specified nowhere. Two agents reference a shared-sounding constant that has no owner and no contents. Violates Plan Quality Gate ("figure it out while coding"). | Input Validation vs Model Functions vs (missing constants section) | **HUMAN-ONLY** | "referenced-constant-must-be-defined" gate |
| F-H4 | **P1** | **Money input unit contradiction.** Global "Money parsing pattern" reads `request.form['amount']` as float dollars × 100. Per-route Input Validation rows name the field `amount_cents` and say "amount int >= 0" (integer cents, no ×100). Template field name + route parse convention can disagree → KeyError or 100× money error. | Input Validation Prescriptions vs Money parsing pattern | **HUMAN-ONLY** | "value-unit consistency" check (field name ↔ parse convention) |
| F-H5 | **P1** | **Rejection-path inconsistency.** Sibling write fns carry rejection in the return (`create_schedule_entry → int\|None`, `allocate_budget → bool`), but `create_expense → int` (bare) signals overspend only via the `spent_cents <= allocated_cents` CHECK raising. Route needs a pre-check *and* a try/except backstop the spec never pins → TOCTOU overspend becomes a 500. | Model Functions vs Transaction Contracts vs Input Validation | **HUMAN-ONLY** | "rejection-path consistency across sibling writers" check |
| F-H6 | P2 | **dept_head ownership is prose, not code.** Crew + expenses "dept_head: own dept only" semantics are described in the Authorization Matrix but never pinned as exact ownership code (only a generic IDOR snippet exists). Brainstorm refinement #1 explicitly warned (VenueConnect: 5/8 P1s were IDOR). | Authorization Matrix vs Auth Decorators (`require_role` does NOT check ownership) | **HUMAN-ONLY** | "role+ownership routes need prescribed ownership code" gate (A4 extension) |
| F-L1 | L | `scene_elements` table has no model functions and no Export Table entry; scenes detail claims to show elements. Single-agent-internal (scenes owns table accessor + consumer) → low cross-boundary risk. | Schema vs Model Functions | HUMAN-ONLY | accessor-coverage lint (low priority) |
| F-L2 | L | `_strip_color` silently maps `DAWN`/`DUSK` day_night values to day colors (only DAY/NIGHT handled). | SortableJS contract vs Schema enum | HUMAN-ONLY | enum-exhaustiveness lint |
| F-L3 | L | `get_production_progress` return shape unpinned (no keys). Single-agent-internal (reports). | Model Functions vs Template Render Context | HUMAN-ONLY | return-shape coverage |
| F-L4 | L | Stale run number: Swarm Agent Assignment branches are `swarm-063-*`; runs have advanced to 069. Next run ≈ 070. | Swarm Agent Assignment | mechanical | n/a — fix at launch |
| F-L5 | L | `generate_call_sheet` doesn't prescribe how `call_sheet_cast.status` (W/SW/WF/SWF/H) is computed at generation; schema defaults to 'W'. | Model Functions vs Schema vs DOOD algorithm | HUMAN-ONLY | n/a — acceptable default, note only |

---

## Scoreboard (for roadmap §6 exit test)

- **Total catches:** 11 (2 P0, 3 P1, 1 P2, 5 L)
- **EXISTING-gate catches (validate shipped tracks):** 1 (F-G1 → Track B / FC50)
- **HUMAN-ONLY catches (derive new gates):** 9
- **Both P0s are HUMAN-ONLY and both are in the FTS subsystem** — textbook "internally-consistent sections, cross-incompatible" pattern. This is precisely the class your CLAUDE.md says human verification is non-optional for.

## New failure classes proposed (→ agent-pitfalls.md after the run)

- **FC52 — single-writer responsibility:** No data store may be mutated by two independent subsystems (e.g., DB trigger + explicit model call). Spec must name exactly one writer per store. (from F-H1)
- **FC53 — artifact-location vs owner:** Every artifact a section says an agent "creates" must live in a file that agent owns. (from F-H2)
- **FC54 — referenced-constant-defined:** Any `CONSTANT[...]` referenced in Input Validation must be defined, owned, and have its contents specified. (from F-H3)
- **FC55 — value-unit consistency:** A form field's name and its parse convention must agree on units (dollars vs cents). (from F-H4)

These four are candidates to become deterministic pre-swarm gates (the A1 cross-section gate generalizes F-H1/F-H2/F-H3).

---

## Disposition (to be filled as spec is fixed)

| # | Status | Resolution |
|---|--------|------------|
| F-G1 | **FIXED** | Added `Full Signature` column + an "Orchestration Entrypoints" row-group (10 rows: 6 call-sheet imports, 3 decorators, get_db) typed `orchestration entrypoint` with signatures. Track B's Check 1b now FIRES (not N/A) and should PASS. |
| F-H1 | **FIXED** | Single-writer chosen: dropped FTS triggers, kept explicit `index_entity`/`remove_entity` (must be called in same txn as source write). Schema comment + neg-constraint #13 updated. |
| F-H2 | **FIXED** | Resolved by F-H1 — no triggers, so no schema.sql/search-agent ownership conflict. |
| F-H3 | **FIXED** | Added "Transition Maps" section defining VALID_PHASE_TRANSITIONS (project_models, projects agent) + VALID_SCENE_TRANSITIONS (scene_models, scenes agent), both single-agent-internal. |
| F-H4 | **FIXED** | Standardized: forms submit DOLLARS (fields without `_cents`), routes parse to integer cents, models store `*_cents`. Money pattern generalized + convention stated. |
| F-H5 | **FIXED** | `create_expense -> int \| None`; overspend re-checked inside lock returns None (not CHECK-raise); route flashes remaining. Transaction Contracts row updated. |
| F-H6 | **FIXED (Codex round)** | Added "Department-Head Ownership Enforcement" section with exact per-route code for all 7 crew/expense routes; strengthened get_crew_member contract (now returns project_id+department_id) and added get_expense(); wired get_departments into expenses routes. |

## Codex review round (2026-06-08)

Fresh-context Codex review returned 4 pre-launch + 1 cleanup finding — all cross-section, all consistent with the convergence pass. Applied directly:

1. **Call-sheet cast status** (P1, cross-section: schema enum vs acceptance text vs unspecified algorithm) — Option A: call sheets list only working cast; dropped `H` from `call_sheet_cast` enum (DOOD-only); added prescribed `generate_call_sheet` algorithm (Start/Work/Finish over the member's scheduled dates); fixed EARS text.
2. **F-H6 ownership** (P2→resolved) — exact code, see disposition above.
3. **FC50 producer-side alignment** (P1) — the 4 shared model signatures were `-> list` while the Orchestration Entrypoints table said `-> list[dict]`; aligned to `-> list[dict]` with matching key lists. *(Note: this is a same-contract-two-places drift the 9w.5 consistency gate might catch by type, but not the key-list mismatch — another gate-blind cross-section catch.)*
4. **Stale `(via triggers)`** (cleanup) — Data Ownership expenses row now says spent_cents updates via model functions.
5. **Stale `VALID_TRANSITIONS[current]`** (cleanup) — replaced with concrete `VALID_PHASE_TRANSITIONS[current_phase]` / `VALID_SCENE_TRANSITIONS[current_status]`.

All verified absent via grep.

## Human structural-verification gate (2026-06-08) — PASSED

Four parallel angle-sliced verification agents read the spec fresh from disk: (A) data-contract chain, (B) signature/orchestration, (C) auth/route/validation + ownership, (D) enum/algorithm/seed. **Result: ZERO P0s** → convergence criterion met (Codex clean AND human finds zero P0s). 2 P1 + 4 P2 surfaced; all P1s and the load-bearing P2s fixed (none reopen architecture):

| ID | Sev | Finding | Fix |
|----|-----|---------|-----|
| GATE-1 | P1 | Decorator stacking order never pinned — wrong order ⇒ `require_role` reads unset `g.member` ⇒ 500 on every protected route | Added MANDATORY canonical stacking example + rule to Auth Decorators |
| GATE-2 | P1 | Call-sheet re-generation hits UNIQUE(project_id, shoot_date) ⇒ unhandled 500 on 2nd Generate | `generate_call_sheet` now idempotent inside the lock (returns existing id); Input Validation row updated |
| GATE-3 | P2 | `created_by` not pinned in expense-create snippet (load-bearing for delete-ownership) | Pinned `created_by=g.user['id']` |
| GATE-4 | P2 | Unguarded `int(request.form['department_id'])` ⇒ 500 on bad input (3 sites) | Guarded the expense snippet + added parse-safety rule covering crew snippets |
| GATE-5 | P2 | `get_departments` def `-> list` vs authoritative `-> list[dict]` | Aligned to `-> list[dict]` |
| GATE-6 | P2 | GET routes with `<int:>` absent from Input Validation (Agent C: "checker may flag") | **NON-ISSUE (evidence):** RestaurantOps (29-agent, passed) has 22 such GET routes, lists 0 in Input Validation; GigSheet same. Checker does not enforce in practice. Logged as a watch-item for the 9w.6 run, not a blocker. |
| GATE-7 | P2 | `crew_call_time` NOT NULL gap | Benign (column has DEFAULT, is nullable). No action. |

**Gate verdict: PASS.** Zero P0s; all runtime-500 risks (the 2 P1s) eliminated; spec ready for launch (run 070) on `feat/film-production-pm`, pending only the operator's go.
| F-L4 | **FIXED** | Branch names swarm-063-* → swarm-070-* (next run). |
| F-L1,L2,L3,L5 | OPEN (accepted) | Single-agent-internal or acceptable defaults; noted for Codex round, not blocking. |
