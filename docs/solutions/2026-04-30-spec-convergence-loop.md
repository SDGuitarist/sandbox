---
title: "Spec Convergence Loop -- Multi-Tool Hardening Before Autopilot"
date: 2026-04-30
status: solved
category: automation
tags:
  - spec-hardening
  - convergence-loop
  - multi-tool
  - codex
  - notebooklm
  - autopilot
  - swarm
  - compound-engineering
modules:
  - docs/plans/2026-04-30-ethics-toolkit-platform-spec.md
  - docs/brainstorms/2026-04-30-ethics-toolkit-brainstorm.md
  - ethics-toolkit/
severity: N/A (process innovation, not a bug)
root_cause: "Prior autopilot specs were single-author single-tool documents. Cross-section contradictions survived because the same tool that wrote section A also wrote section B and couldn't see the conflict."
origin_plan: docs/plans/2026-04-30-ethics-toolkit-platform-spec.md
origin_brainstorm: docs/brainstorms/2026-04-30-ethics-toolkit-brainstorm.md
key_lesson: "Cycling a spec through 3+ tools with different perspectives (authoring, async review, research synthesis) until convergence, followed by a human structural verification pass, produces specs that survive 15-agent swarm execution with zero structural failures."
feed_forward_risk: "Whether this process scales to specs larger than 1000 lines or domains the human cannot personally verify"
feed_forward_resolution: "Validated at 1000+ lines, 15 agents, 4 phases, 116 files. The human verification pass caught 4 P0s that all three AI tools missed. The process works but the human pass is non-optional."
---

# Spec Convergence Loop -- Multi-Tool Hardening Before Autopilot

## Problem Statement

Prior autopilot specs were written in a single tool (Claude Code) with at most one Codex review pass. Cross-section contradictions survived into the swarm because:

1. The tool that authored section A also authored section B -- it couldn't see its own blind spots
2. A single review pass catches obvious gaps but misses contradictions that are internally consistent within each section but incompatible across sections
3. Research-backed data (rate tables, festival policies, union rules) was hand-transcribed without cross-referencing against source material

The result: swarm agents would encounter ambiguities and invent heuristics, producing code that compiled but didn't compose correctly at assembly.

## The Convergence Loop Process

### Tool Roles

| Tool | Role | What it catches |
|------|------|----------------|
| **Claude Code** | Author + implementer. Writes the spec, applies fixes, does structural editing. | Structural issues, missing sections, implementation feasibility |
| **Codex** | Async reviewer. Fresh context every time. Finds contradictions, scope concerns, missing edge cases. | Cross-section contradictions, unstated assumptions, scope creep, ambiguity |
| **NotebookLM** | Research synthesizer. Cross-references spec against source material (rate research docs, festival policies, union contracts, existing frameworks). | Data accuracy, missing source references, claims without evidence, research gaps |

### The Actual Sequence (Ethics Toolkit, Run 033)

```
1. Claude Code -- brainstorm (docs/brainstorms/)
2. Claude Code -- refine brainstorm
3. Codex -- review brainstorm, produce findings table
4. Claude Code -- implement Codex fixes, write spec
5. NotebookLM -- cross-reference spec against source material
6. Claude Code -- implement NotebookLM findings
7. Codex -- review spec
8. Claude Code -- implement fixes
9. Codex ↔ Claude Code -- loop until Codex returns clean
10. Human -- manual structural verification (found 4 P0s)
11. Claude Code -- apply P0/P1/P2 fixes (9 total)
12. Autopilot -- 15-agent swarm execution
```

### What Each Pass Caught

**Codex passes caught:**
- Scope concerns (recommended cutting from 5 tools -- rejected but forced explicit justification)
- Missing privacy section (added)
- Festival data strategy ambiguity (resolved: human-curated v1)
- Identity model conflict (resolved: Option A anonymous workshop)
- Email automation understated (resolved: v1 = 3 simple lifecycle emails only)
- Square subscription complexity (resolved: checkout links + manual activation)

**NotebookLM pass caught:**
- Rate data accuracy against source research doc
- Festival policy details against actual festival websites
- Framework references (Three Questions, 3 C's) against manifesto content
- Workshop interaction types against Alex's actual facilitation patterns

**Human structural verification caught (the 4 P0s no tool found):**
1. Disclosure checklist referenced fields (usageLevel, humanSupervisor, etc.) that didn't exist in DisclosureInput schema -- satisfaction logic would have required agents to invent heuristics from free text
2. Realtime idempotency said "server checks processed_events" for broadcast-first interactions that have no server step -- logical contradiction
3. probabilistic_payload was TEXT in SQL but JSONB in the TypeScript interface -- agents would choose different serialization
4. Fixtures were promised for all 5 tools but only provided for 2 -- agents would invent expected outputs

### Why the Human Pass Was Non-Optional

All three AI tools missed the P0s because each contradiction was **internally consistent within its own section**:

- The checklist items made sense as a checklist (Section 4, lines 258-265)
- The DisclosureInput schema made sense as an input schema (Section 4, lines 228-237)
- They just didn't match each other

This is the fundamental limitation of section-by-section review. AI tools read sequentially and evaluate coherence locally. A human reading the full spec can hold "the checklist says X" and "the schema defines Y" in working memory simultaneously and notice the mismatch.

## Results

| Metric | Previous Best (Run 022) | This Run (033) |
|--------|------------------------|----------------|
| Spec length | ~200 lines | 1000+ lines |
| Agents | 6 | 15 |
| Phases | 1 | 4 sequential with gates |
| Files produced | 13 | 116 |
| Post-assembly structural fixes | 1-2 | 0 |
| Ownership conflicts | 0 | 0 |
| Pre-launch spec fixes | 0 (no multi-tool process) | 9 (4 P0, 4 P1, 1 P2) |

The convergence loop caught 9 issues before the swarm launched. Zero of those issues would have been caught by the verification pipeline (contract checker, smoke test, test suite) because they are design-level contradictions, not mechanical errors.

## Key Insights

### 1. Each tool has a blind spot the others cover

Claude Code can't review its own output with fresh eyes. Codex can't do research synthesis against external docs. NotebookLM can't implement fixes. The convergence comes from cycling through all three.

### 2. The loop termination signal is "Codex returns clean"

You know the spec is ready when Codex (fresh context, adversarial reviewer) can't find new issues. But even then, the human pass is required for cross-section structural verification.

### 3. P0s are always cross-section contradictions

Every P0 found by the human was a mismatch between two sections that were each internally correct. This is the signature failure mode of single-tool spec writing.

### 4. The investment pays for itself in swarm execution

The convergence loop added ~2 hours to spec development. It saved the entire swarm from producing code with incompatible interfaces, which would have required manual debugging across 116 files. The ROI is asymmetric -- 2 hours of spec work vs. potentially days of post-assembly fixes.

### 5. This process is repeatable

The sequence (author → review → research → fix → review → fix → loop → human verify → execute) is not specific to this project. It applies to any spec that will be executed by autonomous agents.

## Prevention Strategies

### For all future autopilot specs:

1. **Minimum 2 Codex review rounds** before autopilot launch
2. **NotebookLM pass** whenever the spec references external data (rates, policies, research)
3. **Human structural verification checklist:**
   - For every schema: do all referenced fields exist?
   - For every checklist/logic block: do the field names match the input schema?
   - For every "see Section X" reference: does Section X actually say what's claimed?
   - For every fixture: does the expected output match the computation rules?
   - For every column type: does the SQL match the TypeScript?
4. **Convergence criterion:** Codex returns clean AND human finds zero P0s

### Process template:

```
/workflows:brainstorm → refine → Codex review → fixes →
NotebookLM research check → fixes →
Codex review → fixes → [loop until clean] →
Human structural verification → final fixes →
/autopilot
```

## Feed-Forward

- **Hardest decision:** Trusting the process and doing multiple rounds instead of launching autopilot after the first clean Codex review
- **Rejected alternatives:** Single-pass spec writing (the previous default), having Claude Code self-review (blind spot problem), having Codex write the spec (loses the author's domain knowledge and intent)
- **Least confident:** Whether this process scales beyond 1000-line specs. At some point, the human structural verification becomes infeasible because no one can hold 2000+ lines in working memory. The next experiment should test whether a dedicated "cross-section consistency checker" agent can substitute for or augment the human pass.
