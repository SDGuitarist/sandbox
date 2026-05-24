---
title: "CPAA Shadow Lab — Cyber-Physical Ambiance Architecture"
date: 2026-05-24
status: complete
topic: cpaa-shadow-lab
phase: brainstorm
feed_forward:
  risk: "Event replay simulator may not surface the real hard problems (out-of-order events, stale-state ambiguity, operator cognitive load) until tested under realistic time pressure with failure injections"
  verify_first: true
---

# CPAA Shadow Lab — Brainstorm

## What We're Building

A **replay-only event simulator** (Phase 0 of the CPAA architecture) — a digital twin that replays a scripted 4-hour charity gala from synthetic telemetry data. No AI, no MCP servers, no hardware. Just an append-only event log, derived current state, and an operator dashboard with replay controls.

This is the foundation layer for the full Cyber-Physical Ambiance Architecture (CPAA), Pacific Flow Entertainment's intelligent event management system. Phase 0 proves the state model before any AI or physical actuation is added.

### Why Phase 0 First

Codex review identified that the biggest risk is not AI prompting or MCP syntax — it's distributed systems thinking: async events, stale state, replay, time synchronization, and failure recovery. Phase 0 isolates those lessons from AI and hardware complexity. If the state model is broken, adding AI on top makes it worse, not better.

### Success Criterion

You can replay the entire event, inspect any point in time, and explain why the current derived state is what it is from the event history alone.

## Architecture Decisions (from Codex Review + Brainstorm Dialogue)

### 1. Action Classification Matrix (A/B/C/D)

Every action the system can take is pre-classified at MCP tool registration time. Agents cannot reclassify actions at runtime.

| Class | Description | AI Role | Examples |
|-------|-------------|---------|----------|
| **A: Read-Only** | Observe and report | Full access | Query POS totals, read temperature, check bid status |
| **B: Reversible Low-Risk** | Bounded auto-actuation | Execute within guardrails | Decorative/accent lighting (10-80%), non-safety digital signage, ambiance presets |
| **C-auto** | Approved auto-execute | Propose, system executes after operator approval | AV cues, non-safety signage changes, pre-scripted lighting scenes |
| **C-manual** | Approved manual action | Propose, human performs action physically | Patio heaters, staff dispatch, anything requiring physical site verification |
| **D: Never AI** | Safety/financial/legal | Summarize and escalate only | Food safety response, card charges, bid state, alcohol service, guest PII access |

**Class B boundary (strict):**
- Allowed: decorative/accent lighting, non-safety digital signage, tightly scoped reversible ambiance presets.
- Excluded: egress lighting, safety lighting, emergency circuits, evacuation signage, compliance messaging, venue-wide audio, any fixture shared with emergency/manual override systems.
- Eligibility is decided **per device inventory**, not per category label.

**Class C split rule:**
- If the operator can fully understand device state from telemetry AND the action is reversible, bounded, and low-blast-radius → C-auto.
- If safe execution depends on local physical context the system cannot reliably observe → C-manual.

### 2. Donor Data Boundary

AI sees **anonymized segments only**, never direct identifiers.

**AI may see:** tier, prior-giving band, bid recency bucket, attendance zone, engagement score bucket.
**AI may NOT see:** name, phone, email, exact location, table assignment, CRM notes.

**Re-identification guard:** At small events (50-200 guests), segment combinations (zone + tier + recent bid) can uniquely identify a person. Segment outputs require minimum group sizes and careful field selection.

**Architecture rule:** "Who should we reach out to?" → segment-level answer from AI. "Which exact person?" → human-only or deterministic CRM workflow outside the model context.

### 3. Privacy Model

PII stays in the CRM (e.g., Givebutter). CPAA receives only anonymized segment outputs and aggregate financials.

**No PII enters:**
- Event log
- Agent prompts
- Edge gateway
- Operator timeline
- MCP tool payloads (except through tightly constrained segment-query interface)

**Cross-border consideration:** The Baja Bash is in Mexico. CRM stays in the US. CPAA queries segment-level data only. No direct identifiers cross the border.

### 4. Event State Model

**Append-only event log** with derived current state via projections. NOT a mutable JSON dictionary.

- Every telemetry reading, agent proposal, operator decision, and actuation command is an immutable event.
- Current state is computed from the log, never written directly.
- Benefits: full replay, causal auditability, no shared mutable state for agents to corrupt.
- Implementation: SQLite `events` table + view for current state (Phase 0). Postgres in production track.

**Prior lesson applies:** Event-sourced audit log solution doc — synchronous projection upsert inside BEGIN IMMEDIATE is simpler and safer than async workers for SQLite. Cursor pagination with `id > cursor` avoids off-by-one traps.

### 5. Kill Switch Design

Both software and physical kill switches required before any Phase 3 actuation.

- **Software:** Single-tap dashboard button. Reverts all AI-actuated systems to safe defaults. Disables all Class B/C tools. Logged.
- **Physical:** Independent path on the edge gateway. Works when the UI, network, or AI layer is degraded. Does not depend on cloud connectivity.
- **Gate rule:** No Phase 3 actuation unless both kill paths exist and are tested.

### 6. Field-Test Gate (Phase 3 prerequisite)

Two-stage validation before any real-world actuation:

**Stage 1 — Lab gate:** Deterministic proof of mechanics.
- Real sensor → gateway → event log path works end to end
- Heartbeat loss surfaces as UNKNOWN, not stale "healthy"
- Network loss/reconnect tested, buffered events replay correctly
- Local safety alarms fire during upstream outage
- Both kill switches work
- Device cooldowns and single-writer locks behave correctly
- Timestamps stay coherent for event reconstruction

**Stage 2 — Rehearsal gate:** Field validation under real conditions.
- Low-stakes test event (small dinner, backyard setup — not the Baja Bash)
- Operators can understand alerts and intervene correctly
- Edge hardware survives real environmental conditions

**Phase 3 actuation unlocks only after both gates pass.**

### 7. Portability Strategy

Two-phase approach:
- **Phases 0-3:** Optimize for the Baja Bash. Baja-specific behavior is fine, but keep configuration data separate from control logic.
- **Phase 4+:** Generalize only what the first deployment proved is stable.

**Explicit seams from day one** (design awareness, not premature abstraction):
- Venue profile
- Device registry
- Zone definitions
- Action-class inventory
- Event config

In Phase 0, these seams may be as simple as a config dict or constants file — not a full configurable framework. The plan phase decides the right implementation weight.

### 8. Inference Cost Budget

**Under $50 per 4-hour event.** This is an architectural constraint, not just a budget line.

**Implications:**
- No continuous "every few seconds" agent polling
- Agents wake on threshold crossings, stale-data alerts, operator queries, or scheduled summary intervals
- Cheapest model that can do the job; reserve larger models for ambiguity or cross-domain synthesis
- Phase 1 measures actual usage against this pre-set target

### 9. Vendor Interaction

**Deferred to Phase 4+.** For the Baja Bash, the operator mediates all vendor communication manually.

Later, if the core proves stable: add domain-specific read-only vendor views (kitchen, bar, AV).

### 10. Build vs. Buy

| Component | Decision |
|-----------|----------|
| Smart device integration | Buy: Home Assistant or Node-RED |
| POS/auction feeds | Buy: vendor webhooks (Square, Givebutter) |
| Event state storage | Build simple: SQLite events table + views (Phase 0), Postgres later |
| MCP servers | Build custom, domain-specific (core IP) |
| Agent orchestration | Buy framework: LangGraph (single agent first) |
| Operator dashboard | Build: Flask + Jinja2 + Bootstrap (Phase 0), PWA later |
| Push notifications | Buy: Firebase Cloud Messaging or similar |
| Kafka / Kubernetes | Do not use. Overengineered for single-event scale |

### 11. Two-Track Strategy

| Track | Scope | Repo | Phases |
|-------|-------|------|--------|
| **cpaa-shadow-lab** | Synthetic telemetry, replay, advisory AI, learning | `~/Projects/sandbox/cpaa-shadow-lab/` | 0-2 |
| **cpaa-control-plane** | Real hardware, actuation, operator dashboard, production safety | `~/Projects/cpaa-control-plane/` (own repo) | 3-5 |

The sandbox track is a learning tool. The production track inherits lessons but starts clean with stricter review culture.

## Phase 0 MVP Scope (What We Actually Build Next)

### Components

1. **Synthetic telemetry generator** — scripted replay of one 3-4 hour gala with event types for:
   - Culinary telemetry (station weights, temperature readings)
   - Financial telemetry (POS transactions, auction bids)
   - Environmental telemetry (temperature, humidity, wind)
   - System events (heartbeats, alerts, operator notes)

2. **Append-only event log** — SQLite `events` table. Each event: timestamp, source, type, payload, causal chain ID (links related events, e.g., a threshold breach and the alert it triggered — schema defined in plan phase).

3. **Derived current state** — SQLite view that projects current state from the event log.

4. **Flask operator dashboard** with:
   - Event timeline (scrollable, filterable)
   - Current derived state panel (station status, environment, financials)
   - Alert/status indicators
   - Replay controls: play, pause, speed up (2x/5x/10x), jump to timestamp

5. **Failure injections** built into the synthetic replay:
   - Dropped heartbeat (sensor goes silent)
   - Delayed event arrival (out-of-order timestamps)
   - Network outage window (gap in events, then buffered replay)
   - Temperature threshold breach (food safety alert)
   - Auction stall period (no bids for N minutes)

### What Phase 0 Does NOT Include
- No AI / LLM calls
- No MCP servers
- No real hardware or vendor APIs
- No actuation of any kind
- No multi-agent orchestration
- No authentication / RBAC (single-user prototype)

### Stack
- Python + Flask + Jinja2 + Bootstrap
- SQLite (WAL mode, single-writer)
- No external dependencies beyond standard Flask ecosystem

## Key Decisions Summary

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | AI is advisory, not autonomous controller | Codex P0: safety-critical and financial paths cannot tolerate AI latency or hallucination |
| 2 | Action classification at tool registration, not runtime | Prevents classification drift; structurally enforced, not behavioral |
| 3 | Class C splits into C-auto and C-manual | Physical-context-dependent actions need human hands, not just human approval |
| 4 | Anonymized segments, never PII in prompts | Cross-border privacy + re-identification risk at small events |
| 5 | Append-only event log, not mutable state dict | Replay, auditability, no shared mutable state corruption |
| 6 | Phase 0 is replay-only, no AI | Isolates state-model lessons from AI/MCP complexity |
| 7 | $50/event inference budget | Forces event-driven wake-ups over continuous polling |
| 8 | Dual kill switch (software + physical) before actuation | Software depends on layers most likely degraded during failure |
| 9 | Lab gate + rehearsal gate before Phase 3 | Checklist proves mechanics; rehearsal proves field conditions |
| 10 | Two-track: sandbox lab + production repo | Different safety cultures for learning vs. live deployment |

## Resolved Questions

1. **Class C execution model** → Split into C-auto (digital, reversible, observable) and C-manual (physical, context-dependent). Per-tool decision.
2. **Donor outreach classification** → AI sees anonymized segments only. Individual donor selection is human-only or deterministic CRM workflow.
3. **Class B exclusions** → Egress, safety, emergency, compliance, and venue-wide audio all excluded. Per-device-inventory eligibility.
4. **Kill switch type** → Both software and physical, both required before Phase 3.
5. **Field-test gate** → Lab validation first, then low-stakes rehearsal event. Both must pass.
6. **Portability** → Baja-specific through Phase 3, with explicit seams. Generalize in Phase 4+.
7. **Vendor access** → Deferred to Phase 4+. Operator-mediated for Baja.
8. **Cost budget** → Under $50/event. Architectural constraint, not just budget.
9. **Privacy model** → PII in CRM only, walled off. Re-identification guard via minimum group sizes.
10. **Phase 0 MVP** → Replay-only simulator. No AI, no MCP, no hardware.

## Open Questions

None — all carry-forwards resolved. Remaining unknowns (observability stack details, time sync implementation, device registry schema, secrets management) are implementation concerns for the plan phase, not brainstorm-level decisions.

## Feed-Forward

- **Hardest decision:** Demoting AI from autonomous controller to bounded advisor. The original vision was more exciting, but three Codex P0s proved that excitement was a safety risk. The revised architecture is less dramatic but actually deployable.
- **Rejected alternatives:** (1) General-purpose AI actuation with thin human gateway — conflates ambiance with safety/financial. (2) Full CRM read access for fundraising agent — collapses the Class D privacy boundary. (3) Software-only kill switch — depends on the layers most likely degraded during failure.
- **Least confident:** Whether the replay simulator will surface the real hard problems (out-of-order events, stale-state ambiguity, operator cognitive load under time pressure) well enough to prepare for live edge hardware. The jump from simulated replay to real sensors with stressed operators is still the biggest risk. Codex flagged "field integration before Baja" as the top carry-forward risk — the lab + rehearsal gate is the mitigation, but it's unproven.
