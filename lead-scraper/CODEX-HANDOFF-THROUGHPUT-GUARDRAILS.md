# CODEX HANDOFF: Throughput and Deadline Guardrails

## Purpose

This handoff exists to stop future agent sessions from optimizing for correctness while ignoring workshop-feasible throughput.

## Read First

Read `CLAUDE.md` before assisting with this repo.

## Business Constraint

- Workshop date: **May 30, 2026**
- Lost momentum has already cost over a week.
- The user is considering cancelling the workshop because lead generation and approval throughput have stalled.

This means throughput is not a nice-to-have. It is the primary operational constraint.

## What Agents Must Understand Before Helping

Before proposing fixes, workflows, or new tooling, explicitly reason about:

1. Deadline
2. Required lead / send volume
3. Current bottleneck
4. Manual review burden
5. Whether the proposed process can actually scale before the workshop

If those are not understood, the agent is not ready to help yet.

## Hard Rule

Any process that requires one-by-one review for a large percentage of leads is presumed **not feasible** unless the agent proves otherwise with throughput math.

## Failure Pattern To Avoid

The repo already suffered from this pattern:

- careful process
- low output
- high manual burden
- late realization that the system does not scale

Future agents must detect this early and escalate immediately instead of continuing down the same path.

## What Good Help Looks Like

- identify the main bottleneck fast
- do the math early
- reject dead-end workflows
- prefer batch-safe, deadline-feasible paths
- protect production data while increasing throughput
