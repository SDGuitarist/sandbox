# Autopilot Brief — CPAA Shadow Lab Event-Replay Simulator (Advanced / 12-layer)
**2026-06-06 · autopilot-swarm (`swarm: true`) · 20–25 agents · Canonical brief for Codex review → plan phase**

## [Your Reality / The Fuel]
**1. Role:** Act as the Lead Agentic Swarm Orchestrator and Senior Systems Architect.
**2. Background:** We are executing Run 068+ of our autopilot architecture, building a CPAA Shadow Lab Event-Replay Simulator. The previous run proved 3-stage context-death delegation at 12 agents with 0 conflicts.
**3. Client Context:** The meta-goal is to validate the autopilot architecture itself, not just the application. CPAA is the workload used to find the inline-phase ceiling. The open architectural question: does this architecture survive 20–25 agents when deepening (Step 6) and worker spawn (Steps 7w–10.5w) stay inline in the orchestrator?

## [Your Assignment / The Destination]
**4. Task:** Execute this brief (canonical path: `docs/briefs/2026-06-06-cpaa-event-replay-simulator-brief.md`) to build an append-only event log with deterministic state reconstruction, point-in-time replay, and a determinism-validation harness. Orchestrate a 20–25 agent swarm across 6 distinct clusters (Core infra, Event parser, Replay engine, Validator, API/reporting, Tests/infra).
**5. Goal:** Build the simulator running against synthetic CPAA telemetry (never touching live state), while meticulously instrumenting the architecture to track context saturation limits.
**6. Audience:** Output is for the Lead Platform Architect to evaluate whether the orchestration survives. If >~70% `context_proxy_chars` saturation is observed before Step 17w, that is a post-run finding that would justify starting the separate Orchestration Hardening plan (not a runtime action).

## [Your Voice / The Guardrails]
**7. Core Differentiators:** Strictly enforce the following across all sub-agents. Do NOT infer architectural decisions — they must be explicitly pinned.
<implementation_rules>
- **Gaps to pin (frozen in the spec BEFORE launch — see Layer 12):** (1) dedup logic under concurrent replay (key + concurrency/transaction behavior), (2) determinism contract definition, (3) shadow isolation method, (4) ordering rules including tie-breaks, (5) payload semantics (patch vs snapshot).
- **Mandatory swarm gate (Step 9w.6) validates EXACTLY these 6 spec sections** (per CLAUDE.md); the gate FAILs if any is missing/incomplete: (1) Export Names, (2) Cross-Boundary Wiring, (3) Input Validation — rules + error responses for every write route AND every typed URL/path param (e.g., replay-time inputs), (4) Coordinated Behaviors, (5) Transaction Contracts (commits / no-commit / BEGIN IMMEDIATE) — Data Ownership (one writer per table) is recorded here, (6) Authorization Matrix. The 5 gaps are NOT a separate gate: each is resolved inside these sections (dedup → Input Validation + Transaction Contracts; determinism / ordering / payload → Coordinated Behaviors; shadow isolation → Authorization Matrix + Transaction Contracts).
- **Data Ownership:** strictly one declared writer per table (full table is a required spec deliverable — see Layer 12).
- **Telemetry:** track `context_proxy_chars` at every phase boundary.
</implementation_rules>

**Pinned gap decisions (FROZEN 2026-06-06 by human — authoritative; the spec must implement these verbatim):**
1. **Dedup logic** — every event carries an `idempotency_key` with a UNIQUE constraint; append via `INSERT … ON CONFLICT IGNORE` inside `BEGIN IMMEDIATE`. Re-running a replay cannot create duplicates; concurrent appends are serialized by the immediate transaction.
2. **Determinism contract** — "same event sequence → identical projection," verified by hashing the canonically-serialized projection after a full replay; deterministic iff hashes match across two runs. On mismatch, emit a field-level diff for diagnostics.
3. **Shadow isolation** — replay writes to a SEPARATE SQLite file (`shadow.db`), never the live DB; the replay engine never opens a live-DB handle. (No row-level tagging.)
4. **Ordering** — apply strictly by monotonic `event_id` (append order). Logical timestamp is data, not apply-order; equal timestamps tie-break on `event_id`.
5. **Payload semantics** — PATCH semantics (per-key change tracking); the projection upsert merges patch keys.
**8. Tone:** Hyper-precise, literal, strictly typed, architecture-focused, rigorously documented.
**9. Avoid:** Do NOT touch the production DB (local SQLite only). Do NOT make undeclared external calls. Do NOT implement clock-speed/rewind time-travel beyond point-in-time read (deferred). Do NOT allow overlapping file ownership across the 6 clusters (overlap = gate fail).

## [Your Contract / The Delivery]
**10. Definition of Done:** The run succeeds only if BOTH of the following hold.

*(a) EARS acceptance — 100%:*
- A valid batch replayed twice produces identical projections.
- `get_projection_at_time(t)` applies ONLY events where ts ≤ t.
- App start returns 200 on all routes (100% smoke pass).
- Duplicate idempotency keys are deduplicated per the pinned strategy.
- Events that arrive out of order in a batch are applied by monotonic `event_id` (canonical append order), not by batch/arrival order.
- Replay on shadow leaves live state completely unchanged.
- The tail-runner finishes review and compound within the timeout.

*(b) Mandatory tail artifacts — run FAILS if any is missing (operating contract):*
- `BUILD_TRACKING.md` with filled AGENT_STATUS, FAILURES, RUN_METRICS.
- Solution doc in `docs/solutions/` with YAML frontmatter.
- Learnings propagation via `/update-learnings-noninteractive` (produces the "Learnings Propagated" summary table; agent-pitfalls Update Log has today's entry).
- Updated `HANDOFF.md` (state, artifacts, next-session prompt; every DEFERRED item has a matching entry).
- Self-audit report at `docs/reports/<run-id>/self-audit.md` (final status, WARN disposition table with every WARN disposed, "What Was Missed", skeptical Q&A, promotion decisions, and a 6-dimension Run Quality Grade scored 1-5 with artifact-backed evidence).

Note: >~70% `context_proxy_chars` saturation before Step 17w is a recorded post-run architectural FINDING (logged in the telemetry log + self-audit). It is NOT a runtime action and NOT a build failure; it feeds a follow-up planning decision on whether to start the Orchestration Hardening plan.

**11. Format — produce:**
- Finalized spec document resolving the 5 mandatory gaps + clearing all 6 swarm-gate surfaces.
- Swarm execution plan detailing disjoint file ownership across the 20–25 agents.
- Working code repository.
- Architectural telemetry log of `context_proxy_chars` at each phase boundary.
- The mandatory tail artifacts from Layer 10(b).

**12. Process (human gate is PRE-LAUNCH, not runtime):**
This is an UNATTENDED autopilot-swarm run — there is no human to answer questions mid-run. Therefore the 5 mandatory gaps are ALREADY frozen by the human in "Pinned gap decisions" (Layer 7); the plan / spec-convergence phase must implement them verbatim and must NOT re-open or re-infer them. They are enforced through the 6 spec sections (Layer 7), not a separate gate, and the human structural-verification step confirms each is carried into the spec before launch. The plan must also produce a complete Data Ownership table (one writer per table) covering: event log, shadow projection, live projection (read-only during replay), validation results, replay metadata/checkpoints, and API/report tables. Do NOT defer gap-pinning or ownership assignment to runtime. Before planning, re-resolve and verify references (paths may live in `sandbox-autopilot-delegation/docs/solutions/`): event-sourced-audit-log, autopilot-swarm-orchestration, spec-completeness-checker-pre-swarm-gate, sandbox-autonomy-hardening, chain-reaction-inter-service-contracts.
