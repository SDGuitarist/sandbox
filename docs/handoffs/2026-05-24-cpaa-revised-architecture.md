# CPAA Revised Architecture -- Post-Codex Analysis

**Date:** 2026-05-24
**Phase:** Pre-Brainstorm Revision (addressing 3 P0s, 8 P1s, 1 Insight from Codex review)
**Prior doc:** `docs/handoffs/2026-05-23-cpaa-codex-pre-brainstorm.md`
**Codex review date:** 2026-05-24

## What Changed and Why

Codex identified a structural flaw: the original architecture treated AI as a live-event actuator with a thin human gateway. That's unsafe for food safety, financial operations, and any system where latency or hallucination has physical consequences.

**The revision:** CPAA is now a **deterministic control plane with AI as a bounded advisory layer**, not a general-purpose autonomous agent dispatching physical commands.

### 5 Revisions Applied (from Codex recommendation)

| # | Codex Directive | Status |
|---|----------------|--------|
| 1 | Add action-class safety model | Done -- see Action Classification Matrix below |
| 2 | Insert Phase 0: simulator/digital twin | Done -- see Revised Roadmap |
| 3 | Remove food safety and monetary actions from AI control path | Done -- both are Class D (never AI-controlled) |
| 4 | Replace mutable state dictionary with event log + derived state | Done -- see Layer 3 revision |
| 5 | Split into sandbox lab + production candidate tracks | Done -- see Two-Track Strategy |

---

## Action Classification Matrix (NEW -- addresses P0 #3)

Every action the system can take is classified before implementation, not at runtime. Agents cannot reclassify actions.

| Class | Description | AI Role | Approval | Examples |
|-------|-------------|---------|----------|----------|
| **A: Read-Only** | Observe and report | Full access | None | Query POS totals, read temperature, check bid status |
| **B: Reversible Low-Risk** | Bounded physical changes | Propose + execute within guardrails | Automated with bounds check | Adjust secondary lighting (10-80%), change digital signage, lower ambient audio by ≤5dB |
| **C: Human Approval Required** | Significant operational changes | Propose only, human executes | Push notification, operator must tap approve | Activate patio heaters, reroute staff, trigger AV promotional media, send donor outreach |
| **D: Never AI-Controlled** | Safety-critical, financial, legal | Summarize and escalate only | Human-only, no AI in control path | Food safety response, card charges, bid state changes, alcohol service decisions, guest data access |

**Rules:**
- Classification is defined at MCP tool registration, not at inference time.
- Class B tools have hardcoded bounds (min/max values, cooldown timers, single-writer locks).
- Class C actions queue into an approval inbox on the operator dashboard. No timeout-based auto-approval.
- Class D actions are not exposed as MCP tools at all. AI can read related telemetry (Class A) and surface alerts, but the action path is human-only.

---

## Revised 5-Layer Architecture

### Layer 1: Edge & Telemetry (The Senses) -- revised per P1 #4

Deterministic hardware layer. No AI lives here.

- **Culinary telemetry:** Calibrated temperature probes (not just load cells) at food stations with HACCP-style thresholds. Load cells for replenishment tracking. Connected to ESP32 microcontrollers.
- **Financial telemetry:** Read-only webhooks from POS (Square/Toast) and auction platform (Givebutter). No write-back capability at this layer.
- **Environmental telemetry:** Smart home APIs (Ecobee, Hue, Lutron) + local weather station.

**Edge reliability (new):**
- Local edge gateway (Raspberry Pi or mini-PC) acts as a buffer between sensors and the cloud. Sensors push to the gateway over local mesh (Zigbee/BLE), not venue WiFi.
- Offline buffering: gateway stores telemetry locally when upstream connectivity drops. Replays on reconnect.
- Heartbeat monitoring: each sensor sends a heartbeat every 30s. Missing heartbeats surface as "UNKNOWN" in the event state, never as "all clear."
- UPS/battery backup on the edge gateway and critical sensors.
- Stale-data detection: any telemetry older than its TTL (configurable per sensor type) is flagged as stale in the event log.

**Food safety path (deterministic, no AI -- addresses P0 #1):**
- Temperature probes have local threshold alarms on the ESP32 itself.
- If ceviche station exceeds safe temp, the ESP32 triggers a local buzzer/LED + pushes an alert directly to the operator's phone via a simple webhook. No AI in this path.
- AI can read temperature data (Class A) and include it in summaries, but it cannot suppress, delay, or override food safety alerts.
- Human response procedure (runbook) is printed and posted at each station.

### Layer 2: Deterministic Control Plane (NEW -- replaces "thin wrappers")

This layer is the policy enforcement engine, not a passthrough. Addresses P1 #5.

- **Domain-based MCP servers** (not monolithic):
  - `cpaa-telemetry-server` -- read-only access to all sensor data. Class A tools only.
  - `cpaa-atmosphere-server` -- write access to lighting, audio, signage. Class B tools with bounds checks.
  - `cpaa-operations-server` -- write access to heaters, staff dispatch. Class C tools (queues to approval inbox).
  - `cpaa-audit-server` -- append-only audit log access. No delete or update tools.
- **No financial or food-safety write tools exist.** Class D actions have no MCP tool surface.

**Every write tool enforces:**
- Strict JSON schema validation on inputs
- Bounds checks (e.g., lighting 10-80%, audio adjustment ≤5dB per call)
- Idempotency keys (prevents duplicate commands from retries)
- TTL/expiry (command expires if not executed within N seconds)
- Actor attribution (which agent, which reasoning trace)
- Reason string (human-readable justification, logged)
- Audit ID (links to the event log entry that triggered this action)
- Circuit breaker (if a device fails 3x in a row, the tool disables itself and alerts the operator)
- Cooldown timer (prevents rapid-fire toggling of the same device)
- Single-writer lock (only one agent can actuate a given device at a time)

### Layer 3: Event Log & Derived State (revised -- addresses P1 #11)

Replaces the mutable "Event State Dictionary" with an append-only event model.

- **Event log:** Append-only table. Every telemetry reading, every agent proposal, every human decision, every actuation command is an immutable event with a timestamp, source, and causal chain ID.
- **Derived current state:** A projection rebuilt from the event log. This is what agents read. It is never written to directly -- it is computed.
- **Benefits:** Full replay capability (debug any incident by replaying the log), causal auditability (trace any action back to the telemetry that triggered it), no shared mutable state for agents to corrupt.
- **Implementation:** Postgres `events` table + materialized view for current state. Not Kafka -- that's overengineered for this scale.

### Layer 4: Advisory AI Layer (revised -- addresses P0 #1, P0 #2)

The AI is an advisor, not a controller. It sees everything, proposes actions, and executes only within Class B bounds.

- **Routing Agent (Supervisor):** Watches the derived current state. Detects anomalies (temperature spike, bid stall, crowd shift). Routes to specialist agents.
- **Specialist Agents:**
  - *Atmosphere Agent:* Proposes and executes Class B actions (lighting, signage). Proposes Class C actions (heaters, AV) into the approval queue.
  - *Fundraising Agent:* Reads auction/POS data (Class A). Proposes donor outreach and AV cues (Class C). **Cannot touch bid state, charges, or financial records (Class D).**
  - *Summary Agent:* Generates natural-language event status reports for the operator dashboard. No actuation capability.
- **Conflict resolution (addresses P1 #6):** Agents do not negotiate. They propose actions into a deterministic priority queue:
  1. Safety (always wins)
  2. Legal/compliance
  3. Financial integrity
  4. Operations
  5. Ambiance optimization

  A single policy engine evaluates the queue. If two proposals conflict (e.g., audio up vs. audio down), the higher-priority domain wins. Ties escalate to the operator.

### Layer 5: Operator Interface & Governance (revised -- addresses P1 #9)

- **Operator dashboard (mobile-first):** Real-time event timeline built from the event log. Shows current state, pending approvals (Class C queue), active alerts, and AI recommendations.
- **Kill switch:** Physical button or single-tap dashboard action that immediately reverts all AI-actuated systems to safe defaults and disables all Class B/C tools. Does not require network connectivity to the AI layer.
- **RBAC:** Operator (full access), Staff Lead (view + limited approvals), Vendor (view own domain only), Observer (read-only timeline).
- **Incident runbooks:** Pre-written response procedures for: food safety alert, power failure, network loss, auction system crash, weather escalation. Posted physically and accessible in-app.
- **Guest privacy (addresses P1 #9):** CRM/donor data access requires explicit data handling policies. At a Baja event, cross-border data concerns apply. The brainstorm must define: what donor data is accessed, where it is stored, what consent is required, and whether any PII crosses the US-Mexico border.

---

## Revised Roadmap (addresses P1 #8, Insight #10)

### Phase 0: Digital Twin / Event Replay Lab (NEW)
**Goal:** Learn distributed systems thinking before touching hardware.
**Build:** A simulator that replays a past event from synthetic telemetry data. Append-only event log, derived state projections, simple dashboard showing the event timeline. No AI, no hardware, no vendor APIs.
**Teaches:** Async events, stale state, replay, time synchronization, state modeling under pressure.
**Stack:** Python + Postgres + simple web dashboard.
**Location:** Sandbox project (`cpaa-shadow-lab/`).

### Phase 1: Shadow Mode (revised)
**Goal:** Add advisory AI to the replay lab.
**Build:** Single LLM reads derived state from the simulator, generates natural-language recommendations ("I would suggest turning on heaters now because temp dropped 4F in 10 minutes"). No actuation. Displayed in the dashboard alongside the event timeline.
**Teaches:** Prompt engineering for real-time advisory, latency budgets, recommendation quality evaluation.
**Stack:** Phase 0 + Claude API / LangGraph single agent.
**Location:** Sandbox project.

### Phase 2: Read-Only MCP + Live Telemetry
**Goal:** Connect to real vendor APIs (read-only) and validate the telemetry pipeline.
**Build:** MCP telemetry server with read-only tools. Connect to Square sandbox API, Givebutter test account, simulated sensor feeds. AI can answer operator questions ("Which station is running low?").
**Teaches:** MCP server development, API integration, real-world data messiness.
**Stack:** Phase 1 + MCP servers + vendor sandbox credentials.
**Location:** Sandbox project (still safe -- read-only, sandbox APIs).

### Phase 3: Closed-Loop Actuation (Class B only)
**Goal:** First real-world actuation with strict guardrails.
**Build:** Atmosphere MCP server with Class B tools only (lighting, signage). Test at a low-stakes rehearsal event, not the Baja Bash.
**Teaches:** Bounds enforcement, circuit breakers, cooldowns, single-writer locks.
**Stack:** Phase 2 + atmosphere MCP server + physical test rig.
**Location:** Own repo (`cpaa-control-plane/`). Production-grade from here.

### Phase 4: Operator Dashboard + Class C Approval Flow
**Goal:** Human-in-the-loop for higher-risk actions.
**Build:** Mobile operator dashboard with approval inbox, kill switch, event timeline. Class C tools (heaters, staff dispatch, AV) queue for human approval.
**Teaches:** Mobile UX for high-pressure decision-making, approval workflow design.
**Stack:** Phase 3 + mobile dashboard (React Native or PWA).
**Location:** Own repo.

### Phase 5: Live Event Deployment
**Goal:** Run CPAA at the WILDCOAST Baja Bash.
**Preconditions:** Phases 0-4 complete. Simulation rig passes multi-crisis scenarios. Rehearsal event runs clean. Incident runbooks reviewed. Guest privacy policies defined. Operator trained.
**Location:** Own repo + physical deployment kit.

---

## Two-Track Strategy (addresses P1 #12)

| Track | Purpose | Repo | When |
|-------|---------|------|------|
| **cpaa-shadow-lab** | Phases 0-2. Synthetic telemetry, replay, advisory AI. Learning and prototyping. | `~/Projects/sandbox/cpaa-shadow-lab/` | Now |
| **cpaa-control-plane** | Phases 3-5. Real hardware, actuation, operator dashboard. Production safety culture. | `~/Projects/cpaa-control-plane/` (own repo) | After Phase 2 proves the model |

The sandbox track is disposable -- it's a learning tool. The production track inherits lessons but starts clean with stricter review, secrets management, deployment topology, and safety documentation.

---

## Build vs. Buy Guidance (addresses Insight #10)

| Component | Recommendation |
|-----------|---------------|
| Smart device integration | **Buy:** Home Assistant or Node-RED |
| POS/auction feeds | **Buy:** Vendor webhooks (Square, Givebutter) |
| Event state storage | **Build simple:** Postgres events table + materialized views |
| MCP servers | **Build:** Custom, domain-specific (this is the core IP) |
| Agent orchestration | **Buy framework:** LangGraph (start with single agent, add routing later) |
| Operator dashboard | **Build:** PWA or lightweight React app |
| Push notifications | **Buy:** Firebase Cloud Messaging or similar |
| Message queue | **Skip for now.** Direct function calls until scale demands it |
| Kafka / Kubernetes | **Do not use.** Overengineered for single-event scale |

---

## What's Still Unresolved (for the brainstorm to address)

### Codex Verification Carry-Forwards (2026-05-24, P1 priority)

8. **Class C semantics:** Choose one model -- system executes after human approval, OR human performs the action manually after seeing the recommendation. Matters especially for heaters and AV.
9. **Donor outreach reclassification:** Split into aggregate fundraising recommendation (Class A/C) vs. selecting/contacting a specific donor from CRM/PII (Class D or human-only). AI must not touch individual donor identity or location.
10. **Narrow Class B scope:** Explicitly exclude egress lighting, safety lighting, evacuation signage, compliance messaging, and venue-wide audio from Class B. Only decorative/secondary fixtures and non-safety signage qualify.
11. **Kill switch as Phase 3 prerequisite:** Minimal operator console, event timeline, and kill switch must exist before any real-world actuation -- cannot wait until Phase 4.
12. **Edge/gateway field-test gate:** Add an explicit milestone before or inside Phase 3: real sensor -> gateway -> event log, network loss/reconnect, stale heartbeat handling, local alarm behavior during upstream outage.
13. **Top carry-forward risk (Codex override):** The biggest remaining risk is NOT "does Phase 0 teach enough." It is the transition from simulated/replay to live edge hardware + stressed human operators. Phase 0 teaches event modeling but not RF instability, device drift, field calibration, operator overload, or rollback under live actuation. "Field integration before Baja" is the top risk.

### Original Unresolved Items

1. **Guest privacy model:** What donor data is accessed? Where is it stored? What consent is required? Cross-border (US-Mexico) data handling rules?
2. **Observability stack:** How does the operator know the system itself is healthy (not just the event)?
3. **Multi-event portability:** Is CPAA a one-off for the Baja Bash or a reusable platform? This shapes every architectural decision.
4. **Vendor coordination:** How do caterers, bartenders, and AV techs interact with the system? Do they get their own dashboard views?
5. **Cost model:** What's the inference cost budget per event? How does that constrain agent polling frequency and model choice?
6. **Device registry and calibration:** How are sensors registered, calibrated, and health-checked before an event? (Promote to Phase 3 gate)
7. **Time synchronization:** All event log entries need a common clock. How is this enforced across edge devices with spotty connectivity? (Promote to Phase 3 gate)

---

## Feed-Forward

- **Hardest decision:** Demoting AI from "autonomous controller" to "bounded advisor." The original vision was more exciting, but Codex correctly identified that excitement as a safety risk.
- **Rejected alternatives:** General-purpose AI actuation with a thin human gateway (original architecture). Rejected because it conflates ambiance optimization with safety-critical and financial operations.
- **Least confident (updated per Codex verification):** The transition from simulated/replay conditions to live edge hardware with stressed human operators. Phase 0 teaches event modeling but not RF instability, device drift, field calibration, operator overload, or rollback under live actuation. "Field integration before Baja" is the top risk.
