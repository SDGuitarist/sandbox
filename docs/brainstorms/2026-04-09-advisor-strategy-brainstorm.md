---
title: "Advisor Strategy — Applying Opus Advisor Pattern Across Projects"
date: 2026-04-09
status: brainstorm
tags: [advisor-strategy, cost-optimization, model-routing, api-pattern, email-classifier]
prior_art: research-agent/docs/solutions/architecture/tiered-model-routing-planning-vs-synthesis.md
---

# Advisor Strategy — Applying Opus Advisor Pattern Across Projects

## What We're Building

A three-step adoption of Anthropic's advisor strategy (`advisor_20260301` API
tool) across Alex's existing and planned projects:

1. **Sandbox experiment** — Standalone Python email classifier using Haiku +
   Opus advisor
2. **Retrofit one existing agent** — Convert the highest-cost managed agent to
   use the advisor pattern
3. **Adopt as default** — Use advisor pattern as standard architecture for new
   API-powered agents

The advisor pattern flips the typical orchestrator model: a smaller model
(Sonnet/Haiku) drives the task end-to-end and only escalates to Opus at hard
decision points. Opus never calls tools or produces output -- it returns
guidance, corrections, or stop signals.

## Why This Approach

### The real problem being solved

Alex's inbox is cluttered with sophisticated subscription emails that mimic
personal messages. High-stakes leads (gig inquiries, business opportunities,
genuine networking) risk getting buried. Email senders increasingly use casual
language and familiarity to bypass spam filters, making simple rule-based
classification unreliable.

### Why advisor pattern fits

- Most emails are obviously subscriptions or obviously leads -- Haiku handles
  these fast and cheap
- The hard cases (sophisticated marketing mimicking personal outreach) are
  exactly where Opus-level reasoning adds value
- Dual escalation: confidence threshold for routine categories + mandatory
  escalation for high-stakes categories
- Prior art in research-agent: tiered model routing already proved Haiku
  handles classification tasks without quality loss (14 queries validated,
  zero decision flips in A/B testing)

### Benchmark evidence

| Config | BrowseComp Score | Relative Cost |
|--------|-----------------|---------------|
| Haiku solo | 19.7% | Baseline |
| Haiku + Opus advisor | 41.2% | ~15% of Sonnet |
| Sonnet solo | ~58% | 100% |
| Sonnet + Opus advisor | ~60% | 88% of Sonnet solo |

## Key Decisions

### 1. Start with email classifier as sandbox experiment

**Decision:** Build a standalone Python script (no deployment, no UI) that
pulls emails via Gmail API, classifies with Haiku + Opus advisor, logs results.

**Why:** Fastest path to learning how escalation behaves in practice. Ties
directly into the AI Email Triage product idea and the existing 65-filter
email triage system. The throwaway code is the point -- we're testing the
pattern, not building the product.

### 2. Three-step adoption sequence (sandbox -> retrofit -> default)

**Decision:** Deliberate learning sequence rather than immediate adoption.

**Why:** Matches the sandbox app sequencing philosophy. Each step produces a
solution doc that compounds into the next. The sandbox experiment will reveal how often Haiku escalates
and whether `max_uses: 5` needs tuning.

### 3. Dual escalation strategy for email classification

**Decision:** Combine confidence-based and category-based escalation.

**Why:** Some decisions are always high-stakes (is this a real lead?) regardless
of Haiku's confidence. Others are genuinely ambiguous (sophisticated marketing).
Both triggers serve different failure modes.

**Implementation note:** With the advisor tool, the executor (Haiku) decides
when to escalate -- there's no programmatic override. "Mandatory escalation"
means strong prompt instructions telling Haiku to always consult the advisor
before classifying something as low-priority if it could be a lead. The sandbox
experiment should verify Haiku actually follows this instruction.

### 4. Classification taxonomy

**Decision:** Two tiers with specific categories:

**High-stakes (must surface, never miss):**
- Gig inquiries (music/sound work availability, rates, projects)
- Business opportunities (workshop bookings, consulting, partnerships)
- Genuine networking (industry contacts, collaborators, real people)

**Low-priority (de-prioritize safely):**
- Subscriptions and newsletters
- Marketing and promotional emails
- Automated notifications (GitHub, services, receipts)
- Social media digests

**Why:** Revenue and relationships live in the high-stakes tier. Everything
else is noise that can wait. The classifier's job is to separate these two
tiers, not to sub-sort within them.

## Prior Art

### Research Agent Tiered Model Routing (Cycle 21)

The research-agent already implements manual tiered routing:
- 7 planning call sites routed to Haiku (decompose, refine, coverage gaps, etc.)
- 8 synthesis call sites kept on Sonnet (quality-critical)
- Zero decision flips in A/B testing with 9 queries
- Saved ~4-7% cost and ~3-5s latency

The advisor strategy is the API-native evolution of this pattern. Instead of
manually splitting call sites, the executor model decides when to escalate.
This is simpler to implement but gives up fine-grained control over which
specific calls get the upgrade.

### Current Claude Code Subagent Model Assignments

Already doing binary tiering:
- Sonnet: session-kickoff, code-explainer, pre-commit-check, plan-quality-gate,
  cross-project-navigator, post-merge-verifier
- Haiku: voice-guardian, solution-doc-searcher, codex-handoff-writer,
  deferred-items-tracker

These can't use the advisor pattern today (Claude Code subagents don't support
API-level tool declarations), but the learning transfers to API-powered agents.

## Resolved Questions

1. **What's the right `max_uses` for the email classifier?**
   **Answer:** Start with 5 (balanced). Enough room for genuine escalation
   without running out. Adjust based on observed escalation rate in sandbox.

2. **Which managed agent to retrofit in step 2?**
   **Answer:** Email triage / accountability agent. Natural evolution from the
   sandbox email classifier -- the learning transfers directly.

3. **How to measure success?**
   **Answer:** Both cost and accuracy, with lead safety as the hard constraint.
   - **Hard constraint:** Zero missed leads. No real lead ever classified as
     noise. False positives (subscriptions flagged as leads) are acceptable.
   - **Optimization target:** Cost per email vs Sonnet/Opus baseline. Track
     escalation rate as the primary cost driver.
   - **Secondary metrics:** Escalation accuracy (did Opus actually change
     Haiku's answer?), latency per classification, comparison against current
     65-filter Gmail performance.

## Feed-Forward

- **Hardest decision:** Whether to build a deployed system (Edge Function) or
  a throwaway script. Chose throwaway because we're testing the pattern, not
  shipping a product. Risk: throwaway code might not surface production-like
  escalation behavior.
- **Rejected alternatives:** Extending the existing email triage system directly
  (too coupled), building a code review summarizer (less personal pain point,
  weaker motivation to iterate), Supabase Edge Function (premature deployment).
- **Least confident:** Whether Haiku's self-assessment of "I need help" is
  reliable enough for email classification. The benchmarks show it works for
  BrowseComp, but email classification with sophisticated spam is a different
  distribution. The sandbox experiment MUST measure escalation accuracy, not
  just classification accuracy.
