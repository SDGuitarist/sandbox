---
title: "Scale-Validation Swarm Vehicle — Lesson-Studio Manager (≥20 agents)"
date: 2026-07-09
type: brainstorm
phase: brainstorm
status: proposed
decision: "GOAL chosen 2026-07-09 = validate the governance stack at scale (throwaway app; maximize coordination-seam surface). Vehicle = a disposable lesson-studio / music-school manager, Flask+SQLite+Jinja, ~22-26 agents, own top-level namespace dir. App usefulness is irrelevant; the deliverable is a legible at-scale exercise of G1 firebreak + FC58 path-pin + 080-W5 compounded-darkness gate + G3 chain + Step 1.52 telemetry. Next phase = Plan (6 contract sections + EARS, sized ≥20), then convergence hardening (Codex + human P0 pass) before launch."
traces_to:
  - docs/plans/2026-07-07-chore-validate-orchestrator-context-telemetry-at-scale-plan.md (the validation criteria this vehicle serves)
  - docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md (the G1/G3 stack being validated; Step 5 complete)
  - docs/solutions/2026-06-30-shelftrack-run-080-g1-g3-coexistence-revalidation.md (last coexistence run — only 4 agents)
  - docs/solutions/2026-06-08-film-production-pm-run-070-swarm-build.md (16-agent precedent, proven stack)
  - .claude/hooks/firebreak-classify.py (FC58 path-pin, commit fb20a11 — live-tested by this run)
  - tools/check_compounded_darkness.py (080-W5 gate, commit 5ae30c6 — live-tested by this run)
feed_forward:
  risk: "The app is throwaway but the VALIDATION is the deliverable. The real failure mode is a vehicle so SIMPLE that few genuine seams exist — the machinery is never stressed and a green run gives false confidence. Seam-density (not feature count) is the whole game."
  verify_first: true
---

# Scale-Validation Swarm Vehicle — Lesson-Studio Manager (≥20 agents)

## Origin (why we're here)

Steps 1–5 are complete. The governance stack — G1 firebreak, the FC58 carve-out plus
today's path-pin, today's 080-W5 compounded-darkness gate, the G3 self-audit/disconfirmer
chain, and the Step 1.52 context telemetry — has been built and hardened, but has **only
ever run on tiny builds** (079 = 3 agents, 080 = 4). The failure modes it exists to catch
(orchestrator context-death, coordination-seam bugs) appear only at scale. The
validate-at-scale plan (`docs/plans/2026-07-07-...`) explicitly designates *the next
≥20-agent swarm build* as the vehicle to prove it, with a pre-registered trigger: **a
missing telemetry boundary row at scale is an instrument failure, not a pass.**

Goal chosen 2026-07-09: **validate the stack** — a throwaway app, spec optimized to
maximize coordination-seam surface. This doc designs that vehicle.

## Design Goal — what "good" means for a validation vehicle

Not business value. The app is disposable. Success = the run exercises every
coordination-seam surface the machinery guards, at ≥20 agents, and every gate/telemetry
produces a **legible** signal — fires correctly OR stays correctly quiet; both are
validation data. The anti-goal: a vehicle so simple it never stresses the seams, so a
green run proves nothing.

## The Vehicle (proposed)

- **Domain:** lesson-studio / community music-school management. Throwaway. Chosen because
  (a) it decomposes into ~13 *interrelated* entities → ~22–26 agent clusters, and (b) it
  sits in Alex's PFE youth-music wheelhouse, so the **mandatory human P0 structural-verify
  pass** (the non-optional cross-section-contradiction catch) is fast — a domain he groks
  lowers the one cost only he can pay.
- **Stack:** Flask + SQLite + Jinja2 + Bootstrap — the proven swarm stack (film-PM run 070,
  ShelfTrack run 080). `agent-pitfalls.md` is calibrated to it, so build reliability is
  high and any failure we see is a real seam signal, not stack noise.
- **Namespace:** its own top-level dir (e.g. `studio/`) per FC59 — never the shared `app/`.

### Entity / agent decomposition (~22–26 agents)

~13 entity clusters (several split model-vs-routes/templates to push count) + cross-cutting
agents: scaffold-auth, schema/contract owner, RBAC/authorization-matrix owner, mock/seed,
nav/layout, dashboard-aggregator, smoke-test.

| Entity cluster | Seams it creates |
|---|---|
| users / roles / auth (scaffold) | foundational; every ownership check depends on it |
| students | consumed by enrollments, schedule, attendance, invoices, practice-logs |
| instructors | consumed by courses, schedule; role-scoped visibility |
| courses / programs | FK → instructors; consumed by enrollments |
| enrollments | FK → students + courses (2-way seam) + transaction |
| schedule / lessons | FK → instructor + student + room + time (**4-way seam**) |
| rooms / facilities | consumed by schedule |
| instrument inventory | checkout → student (transaction, state machine) |
| attendance | FK → schedule + student |
| invoices / payments | FK → student, multi-table write (transaction contract) |
| practice logs | student-owned (ownership auth, self-service) |
| announcements | role-based visibility (coordinated behavior) |
| dashboard / reports | aggregates across many models (orchestration entrypoints) |

### Seam-density map — why it maxes the 6 mandatory contract sections

| Mandatory spec section | What this domain forces |
|---|---|
| Cross-Boundary Wiring | enrollments/schedule/attendance/invoices each carry multiple FKs → dense producer→consumer table |
| Authorization Matrix | role+ownership everywhere (students see only *their* logs/invoices; instructors *their* students; admin all) |
| Transaction Contracts | invoice + instrument-checkout + enrollment = multi-table writes |
| Coordinated Behaviors | nav, flash, blueprint registration across ~13 clusters |
| Export Names / Orchestration entrypoints | dashboard aggregates = route→many-model calls crossing agent boundaries |
| Input Validation | every POST/PUT/DELETE across ~13 clusters |

## What It Validates (the real deliverable)

- **FC58 path-pin (today) + 080-W5 compounded-darkness gate (today)** — first live exercise
  at scale. Tight loop: built two gates today, next run stress-tests them.
- **G1 firebreak** on a real ≥20-agent swarm (previously only 3–4).
- **G3 self-audit / disconfirmer chain** at scale.
- **Step 1.52 context telemetry** at scale — the explicit open residual.
- **Fresh pitfalls harvest** at a scale not seen since run 050 (31 agents).

## Success Criteria (tie to the validate-at-scale plan)

- `context-telemetry.md` has a complete boundary row at every Step 1.52 checkpoint. A
  **missing** row = instrument FAILURE trigger (harden the instrument), NEVER a pass.
- Firebreak: all pinned pipeline scripts (incl. today's `check_compounded_darkness.py`) run
  clean under the active tail firebreak; RED actions blocked; the built-in probe
  self-validates.
- Compounded-darkness gate emits a legible STATUS (OK, or COMPOUNDED_DARKNESS disposed by
  the self-audit).
- ≥20 agents actually spawned; ownership gates pass; 0 structural failures (or every
  failure traced to its agent and folded into `agent-pitfalls.md`).
- Honest status discipline: a "clean" run is read skeptically; PIPELINE_PASS vs
  PIPELINE_PASS_WITH_DEFERRED_RISK adjudicated by the self-audit, not asserted.

## Key Decisions

1. **Throwaway domain in Alex's wheelhouse** — eases the human P0 pass.
2. **~22–26 agents** — past the ≥20 residual threshold, near the 070 precedent (16) so
   build reliability holds, below the 050 record (31) to avoid gratuitous token burn.
3. **Proven Flask stack** — isolate the seam signal from stack noise.
4. **Own namespace dir (FC59)** — no ghost-file collision with prior builds.

## Open Questions (for the Plan phase)

- Exact agent count + cluster boundaries (the plan's file assignments set it).
- Which entities split into 2 agents (model vs routes/templates) to reach ~24.
- Seed/mock data volume sufficient for a *meaningful* smoke test (so the dynamic surface
  is genuinely LIT, not trivially green).
- Deliberately include the 4-way `schedule` FK seam as a guaranteed hard-contract exercise?
- Auth scope: session-based (proven); how wide is the role+ownership matrix?

## Feed-Forward

- **Hardest decision:** sizing for seam-density vs token cost. Too small → false-green;
  too big → token burn *and* higher context-death risk. Chose ~22–26 as the sweet spot:
  past the ≥20 residual threshold, near the reliable 070 precedent, below the 050 record.
- **Rejected alternatives:** (a) a real useful app — Alex chose throwaway; (b) a ~10–15
  shakedown — won't hit the scale-only residuals the plan targets; (c) maxing to 31+ —
  token burn for marginal validation gain; (d) an unfamiliar domain — raises the human P0
  cost with no benefit for a disposable app.
- **Least confident:** whether ~22–26 agents actually *reproduces* orchestrator pre-tail
  saturation. The June-5 delegation architecture (run 069 survived 24 agents) may simply
  hold — in which case the telemetry stays green and we've validated **resilience**, not
  stressed the **death path**. That is still a real result, but we must report it honestly:
  a green run confirms the happy path, it does not prove the failure path was exercised.
