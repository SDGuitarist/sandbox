# Autopilot Brief — CPAA Shadow Lab Event-Replay Simulator (Advanced / 12-layer)
**2026-06-06 · autopilot-swarm (`swarm: true`) · 20–25 agents · Two-stage: attended plan/spec-convergence + human verify → unattended build (see Layer 12)**

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
1. **Dedup logic** — every event carries an `idempotency_key` that is GLOBALLY UNIQUE (UNIQUE constraint). Append via `INSERT OR IGNORE` (valid SQLite) inside `BEGIN IMMEDIATE`; FIRST WRITE WINS. A duplicate key is silently ignored (no error) and counted; the same key arriving with a DIFFERENT payload is also ignored and logged as an anomaly (never overwrites). Re-running a replay cannot create duplicates; concurrent appends are serialized by the immediate transaction.
2. **Determinism contract** — "same event sequence → identical projection," verified by hashing the canonically-serialized projection after a full replay; deterministic iff hashes match across two runs. Canonical serialization (spec MUST pin exactly): all projection tables included, rows ordered by primary key, JSON object keys sorted, floats and timestamps normalized to fixed precision/format. On mismatch, emit a field-level diff (spec defines the diff schema).
3. **Shadow isolation** — two separate SQLite files: `live.db` (source telemetry, treated as READ-ONLY) and `shadow.db` (all replay writes). The replay engine opens ONLY `shadow.db` for writing and never a writable `live.db` handle. The validator MAY open `live.db` READ-ONLY to assert it is unchanged. No row-level tagging. ("Live state unchanged" = `live.db` content hash identical pre- vs post-replay.)
4. **Ordering** — apply strictly by monotonic `event_id`, assigned at append/ingest time (so out-of-order batch arrival still yields canonical order). Logical timestamp is data, not apply-order; equal timestamps tie-break on `event_id`. Point-in-time replay query: `WHERE logical_ts <= :t ORDER BY event_id`.
5. **Payload semantics** — PATCH semantics (per-key change tracking); the projection upsert merges patch keys. Null rule: an explicit `null` in a payload CLEARS that key (sets it null); a key ABSENT from the payload is left unchanged. Unknown keys and per-event-type merge rules (incl. additive counters) are pinned in the spec's Coordinated Behaviors section.
**8. Tone:** Hyper-precise, literal, strictly typed, architecture-focused, rigorously documented.
**9. Avoid:** Do NOT touch the production DB (local SQLite only). Do NOT make undeclared external calls. Do NOT implement clock-speed/rewind time-travel beyond point-in-time read (deferred). Do NOT allow overlapping file ownership across the 6 clusters (overlap = gate fail).

## [Your Contract / The Delivery]
**10. Definition of Done:** The run succeeds only if BOTH of the following hold.

*(a) EARS acceptance — 100%:*
- A valid batch replayed twice produces identical projections.
- `get_projection_at_time(t)` applies ONLY events where `logical_ts` ≤ t.
- App start succeeds and every route returns its EXPECTED status per the spec's route smoke table (e.g. GET 200, redirects 302, POST/validation errors their declared 4xx) — 100% pass against that table.
- Duplicate idempotency keys are deduplicated per the pinned strategy.
- Events that arrive out of order in a batch are applied by monotonic `event_id` (canonical append order), not by batch/arrival order.
- Replay on shadow leaves live state completely unchanged.
- The tail-runner completes review + compound within its 30-minute timeout; on timeout it writes `CHECKPOINT.md` and the run is marked NEEDS-RESUME (never silently passed).

*(b) Mandatory tail artifacts — run FAILS if any is missing (operating contract):*
- `BUILD_TRACKING.md` with filled AGENT_STATUS, FAILURES, RUN_METRICS.
- Solution doc in `docs/solutions/` with YAML frontmatter.
- Learnings propagation via `/update-learnings-noninteractive` (produces the "Learnings Propagated" summary table; agent-pitfalls Update Log has today's entry).
- Updated `HANDOFF.md` (state, artifacts, next-session prompt; every DEFERRED item has a matching entry).
- Self-audit report at `docs/reports/<run-id>/self-audit.md` (final status, WARN disposition table with every WARN disposed, "What Was Missed", skeptical Q&A, promotion decisions, and a 6-dimension Run Quality Grade scored 1-5 with artifact-backed evidence).

Note: >~70% `context_proxy_chars` saturation before Step 17w is a recorded post-run architectural FINDING (logged in the telemetry log + self-audit). It is NOT a runtime action and NOT a build failure; it feeds a follow-up planning decision on whether to start the Orchestration Hardening plan.

**11. Format — produce:**
- Finalized **plan** file in `docs/plans/` starting with YAML frontmatter that includes `swarm: true` (required to trigger the swarm path) and the `feed_forward:` block.
- Finalized **spec** document resolving the 5 mandatory gaps + clearing all 6 swarm-gate surfaces, including a **route smoke table** (route, method, payload, expected status) and the canonical-serialization + PATCH merge rules.
- **Per-agent file-ownership matrix** (produced BEFORE Step 10w worker spawn): agent ID → exclusive files, declared owner for any shared file, and merge order. Overlap = ownership-gate fail.
- Working code repository.
- **Architectural telemetry log** at `docs/reports/<run-id>/context-telemetry.md`: one row per phase boundary (columns: phase/step boundary, `context_proxy_chars`, % of budget, timestamp), covering at minimum Steps 6, 9w.6, 10w, 11w–16w, 17w, 18w.
- `/workflows:review` output plus a Feed-Forward section whose "least confident" item names the inline-phase context risk.
- The mandatory tail artifacts from Layer 10(b).

**12. Process — execution model (human gate is PRE-LAUNCH, never runtime):**
This runs in TWO stages.
- **Stage 1 (attended, pre-launch):** humans + Claude + Codex run the plan / spec-convergence loop and the human structural-verification gate to produce a FROZEN, committed, verified spec. Convergence criterion: Codex clean AND human finds zero P0s. This stage MAY involve human questions and review.
- **Stage 2 (unattended):** the autopilot-swarm run is launched against that frozen spec; the build proceeds with NO human in the loop. NOTHING in Stage 2 waits on a human — every gate in Stage 2 is automated (spec-completeness + consistency checkers, ownership gate, contract check, smoke, tests, self-audit).

The 5 mandatory gaps are ALREADY frozen in "Pinned gap decisions" (Layer 7); Stage 1 must implement them verbatim and must NOT re-open or re-infer them — enforced through the 6 spec sections (Layer 7), not a separate gate. Stage 1 must also produce a complete Data Ownership table (one writer per table) covering: event log, shadow projection, validation results, replay metadata/checkpoints, and API/report tables (plus the READ-ONLY `live.db`). Do NOT defer gap-pinning or ownership assignment to Stage 2.

References (read in Stage 1 IF PRESENT; treat as NON-BLOCKING if absent — re-resolve, do not stall): event-sourced-audit-log, autopilot-swarm-orchestration, spec-completeness-checker-pre-swarm-gate, sandbox-autonomy-hardening, chain-reaction-inter-service-contracts — likely under `docs/solutions/` here or in a sibling `sandbox-autopilot-delegation/` checkout.
