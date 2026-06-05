# Codex Pre-Brainstorm Analysis: Cyber-Physical Ambiance Architecture (CPAA)

**Date:** 2026-05-23
**Phase:** Pre-Brainstorm (architecture analysis before formal brainstorm)
**Repo:** ~/Projects/sandbox
**Reviewer:** Codex

## What I Need From You

Analyze this architecture concept for feasibility, gaps, and risk before I run a formal brainstorm session. This is NOT a typical CRUD app -- it's a cyber-physical system that bridges AI agents with real-world hardware at live events. I need you to stress-test the thinking, not rubber-stamp it.

## The Vision

**Pacific Flow Entertainment** wants to build a **Cyber-Physical Ambiance Architecture (CPAA)** -- an intelligent central nervous system for high-stakes live events (charity galas, experiential activations). The system monitors real-time event telemetry (food stations, fundraising, environment) and dispatches AI agents to optimize the experience autonomously, with human-in-the-loop governance for high-risk actions.

**Target event:** WILDCOAST Baja Bash -- a charity gala at a private oceanfront residence in Baja California.

## Proposed 4-Layer Architecture

### Layer 1: Edge & Telemetry (The Senses)
Deterministic hardware layer. No AI lives here.
- **Culinary telemetry:** Load cells (weight sensors) under serving stations (e.g., ceviche ice beds), connected to Raspberry Pi / ESP32 microcontrollers. Push payloads to a central webhook when weight drops below a threshold.
- **Financial telemetry:** Webhooks from POS system (Square/Toast) and silent auction platform (Givebutter). Real-time JSON payloads of purchases and bids.
- **Environmental telemetry:** Smart home APIs (Ecobee, Hue, Lutron) + local micro-weather API. Real-time temperature, wind, humidity.

### Layer 2: Model Context Protocol (The Translator)
MCP servers as secure middleware between AI and physical systems.
- Thin wrappers around physical APIs with restricted tool surfaces: `get_current_bids()`, `trigger_patio_heaters()`, `dispatch_expeditor(location)`.
- Validates all incoming requests. Rejects out-of-bounds commands (e.g., heater set to 150F) before the physical API sees them.
- No raw database access for the AI -- ever.

### Layer 3: Orchestration & Cognitive Engine (The Brain)
Multi-agent system built on LangGraph or CrewAI Flows.
- **Event State Dictionary:** Continuously updating JSON object -- current temp, current revenue, active bottlenecks.
- **Routing Agent (Supervisor):** Fast, low-latency model. Watches telemetry, detects anomalies, wakes specialist agents.
- **Specialist Agents:**
  - *Atmosphere Agent:* Handles environmental responses (heaters, lighting, audio levels).
  - *Fundraising Agent:* Monitors auction stalls, queries CRM for donor locations, triggers AV system for targeted media.
  - (Future: Culinary Agent, Logistics Agent, Guest Experience Agent)

### Layer 4: Governance & CI/CD (The Guardrails)
- **Objective Functions:** Hardcoded constraints in system prompts (max decibels, max authorized spend per action).
- **Simulation Rig:** Fires synthetic multi-crisis scenarios (power failure + auction crash + rain) to validate agent conflict resolution.
- **Human Gateway:** Mobile dashboard for event director. 90% autonomous, high-risk actions halt for push notification approval.

## Phased Implementation Roadmap

1. **Phase 1 -- Shadow Mode:** Build telemetry + dashboard. Single LLM passively reads data and *suggests* optimizations via text. No actuation.
2. **Phase 2 -- Read-Only MCP:** MCP servers in read-only mode. Agents can pull POS/auction data to answer natural-language questions ("Which station is backing up?").
3. **Phase 3 -- Closed-Loop Actuation:** Write-access to low-risk systems only (digital signage, secondary lighting).
4. **Phase 4 -- Full Autonomy:** Financial and logistics actuation, bound by simulation-validated guardrails.

## Review Questions

1. **Layer 1 feasibility:** The plan assumes ESP32/RPi load cells pushing webhooks over venue WiFi at a remote Baja residence. Is this realistic? What about network reliability, power, latency? What happens when the edge hardware loses connectivity mid-event?

2. **MCP layer design:** The MCP servers are described as "thin wrappers." In practice, what does the tool surface actually look like? How many MCP servers -- one per hardware domain, or one monolithic server? What's the right granularity?

3. **Multi-agent coordination risk:** A supervisor routing to specialist agents is a well-known pattern, but at a live event, what happens when two agents conflict? (Atmosphere Agent wants to turn down outdoor audio because of noise complaints; Fundraising Agent wants to turn it UP to energize bidding.) How should conflicts be resolved -- priority hierarchy, event director escalation, or something else?

4. **Latency budget:** A LangGraph pipeline with supervisor + specialist routing could take 5-15 seconds per cycle. For atmosphere adjustments, that's fine. For food safety (ceviche temp), it's potentially dangerous. Does the architecture need a "fast path" of deterministic rules that bypass the AI entirely?

5. **Phase 1 scope:** If I were to build Phase 1 as a sandbox project right now, what's the minimum viable version? Can I simulate the telemetry layer with synthetic data (fake POS webhooks, simulated weight sensors) and still get a meaningful prototype?

6. **What's missing entirely?** Are there layers, components, or failure modes that this architecture doesn't address? (e.g., audit logging, data retention, guest privacy, vendor coordination, multi-event portability)

7. **Build vs. buy:** For each layer, where should I build custom and where should I use existing platforms? (e.g., should the Event State Dictionary be a custom JSON object or a proper event streaming platform like Redis Streams / Kafka?)

8. **Is this a sandbox project or does it need its own repo?** Given the scope (hardware integration, MCP servers, multi-agent orchestration, mobile dashboard), does this belong in ~/Projects/sandbox or should it be a standalone project from day one?

## Context for Your Analysis

- I am a beginner developer learning through compound engineering (brainstorm -> plan -> build -> review -> compound loops).
- My prior builds are Flask + SQLite + Jinja2 CRUD apps with Bootstrap, deployed via autopilot swarms of 15-25 agents. This project is a significant leap in complexity.
- I have deep domain expertise in live event production but am early in my systems engineering journey.
- The sandbox repo has 50+ brainstorm docs and a mature compound engineering pipeline, but nothing approaching IoT or cyber-physical systems.

## What to Return

A numbered list of findings, each tagged:
- **P0** -- Architecture is fundamentally flawed or dangerous in this area
- **P1** -- Missing component or unresolved risk that must be addressed in the brainstorm
- **P2** -- Design improvement or consideration for later phases
- **Insight** -- Non-obvious observation that could reshape the approach

Be direct. "This is ambitious" is not a finding. "The MCP layer needs a circuit breaker pattern because [specific failure mode]" is a finding.
