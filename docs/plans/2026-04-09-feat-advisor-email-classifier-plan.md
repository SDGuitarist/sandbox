---
title: "feat: Advisor Strategy Email Classifier (Custom Tool Proxy)"
type: feat
status: active
date: 2026-04-09
origin: docs/brainstorms/2026-04-09-advisor-strategy-brainstorm.md
revision: "2026-04-09 — pivoted from advisor_20260301 (not live) to custom tool proxy"
feed_forward:
  risk: "Whether Haiku's self-assessment of 'I need help' is reliable enough for email classification with sophisticated spam"
  verify_first: true
---

# feat: Advisor Strategy Email Classifier

### Prior Phase Risk

> "Whether Haiku's self-assessment of 'I need help' is reliable enough for
> email classification. The benchmarks show it works for BrowseComp, but email
> classification with sophisticated spam is a different distribution. The
> sandbox experiment MUST measure escalation accuracy, not just classification
> accuracy."

This plan addresses the risk by making escalation measurement the primary
output of the experiment, not a secondary metric. The script logs every
classification with enough data to compute escalation accuracy, and the
test set includes deliberately ambiguous emails designed to trigger (or fail
to trigger) escalation.

## Overview

Build a standalone Python script (`email_classifier.py`) at the sandbox repo
root that classifies emails using the advisor pattern: Haiku as executor with
a custom `consult_advisor` tool that routes to Opus when Haiku decides it
needs help. This is a sandbox experiment to learn how executor-driven
self-escalation behaves before retrofitting the email triage agent (step 2)
and adopting as default (step 3).

**Why custom tool proxy instead of `advisor_20260301`:** The advisor tool
announced April 9, 2026 is not yet live in the Messages API (returns 400,
see `advisor_spike_response.json`). A custom tool preserves the core behavior
-- Haiku decides when to escalate, not us -- while giving better observability:
we see exactly what Haiku sends to the advisor and what Opus returns. When
`advisor_20260301` launches, migration is a one-line tool swap.

(see brainstorm: docs/brainstorms/2026-04-09-advisor-strategy-brainstorm.md)

## Problem Statement / Motivation

Alex's inbox is cluttered with sophisticated subscription emails that mimic
personal outreach. High-stakes leads (gig inquiries, business opportunities,
genuine networking) risk getting buried. Current Gmail filters (65 rules) can't
handle emails that use casual language and familiarity to bypass spam detection.

The advisor pattern is a cost-effective solution: Haiku handles obvious
classifications cheaply, Opus provides frontier reasoning only at decision
points. But we need to verify this works for email classification specifically,
not just BrowseComp benchmarks.

## Proposed Solution

A single Python script that classifies a built-in set of 20 labeled test
emails, logs structured JSON results, and prints a summary report with
escalation accuracy metrics.

**Gmail integration is out of scope for this plan.** It will be a separate
follow-up plan after the advisor pattern is validated on sample data. This
plan completes on sample mode alone.

### Phase 0: Verify custom tool proxy works

Before writing classification logic, confirm the multi-turn tool-use flow
works with Haiku as executor and Opus as advisor:

1. Send Haiku an ambiguous email with a `consult_advisor` custom tool available
2. Confirm Haiku calls the tool when uncertain (returns `stop_reason: "tool_use"`)
3. Send the tool input to Opus, get guidance back
4. Return Opus guidance as a tool result, confirm Haiku produces a final answer
5. Save the full multi-turn exchange as `advisor_spike_response.json`

**Stop conditions:**

1. **Haiku never calls the tool** even on deliberately ambiguous input after
   prompt tuning: The executor-driven escalation pattern doesn't work for this
   task. STOP and consider confidence-threshold routing instead.
2. **Multi-turn flow breaks**: Tool result not accepted, Haiku can't incorporate
   advisor guidance, or the conversation structure doesn't support the pattern.

These use standard API features (custom tools, multi-turn), so hard API errors
are unlikely. The risk is behavioral: Haiku might not call the tool.

## Technical Approach

### Architecture

```
email_classifier.py          # single file, repo root
├── EmailClassifierConfig    # frozen dataclass: models, max_uses, thresholds
├── classify_email()         # multi-turn: Haiku classifies, optionally calls advisor
├── call_advisor()           # routes tool input to Opus, returns guidance
├── load_sample_emails()     # returns list of test email dicts
├── log_result()             # appends JSON line to results file
└── print_summary()          # escalation rate, cost, accuracy stats
```

Single file at repo root, matching the standalone script convention from
`deep_researcher.py` and `content_pipeline.py`.

**Conventions reused from existing scripts:**
- Single-file structure at repo root (no subdirectory)
- `load_dotenv(Path(__file__).parent / ".env")` for API key loading
- `requests` library for HTTP calls (not the `anthropic` SDK)
- `BASE = "https://api.anthropic.com/v1"` constant + shared headers dict

**Conventions NOT reused (different API surface):**
- Existing scripts use the Managed Agents API (`/agents`, `/sessions`). This
  script uses the Messages API (`/messages`) with custom tool use -- different
  endpoint, different request/response shape, no polling loop.
- No agent ID caching to disk (no persistent agent to reuse)
- Multi-turn conversation (tool use requires follow-up messages)

### Config dataclass

```python
@dataclass(frozen=True)
class EmailClassifierConfig:
    executor_model: str = "claude-haiku-4-5-20251001"
    advisor_model: str = "claude-opus-4-6"
    max_uses: int = 5
    api_version: str = "2023-06-01"
```

(Pattern from research-agent: frozen dataclass prevents accidental mutation,
centralizes model strings. See brainstorm prior art section.)

### Custom tool definition

```python
ADVISOR_TOOL = {
    "name": "consult_advisor",
    "description": (
        "Consult a senior advisor for a second opinion on email "
        "classification. Use this when you are uncertain about whether "
        "an email is a genuine lead or sophisticated marketing/spam."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "email_summary": {
                "type": "string",
                "description": "Brief summary of the email and sender"
            },
            "preliminary_classification": {
                "type": "string",
                "description": "Your initial classification category"
            },
            "confidence": {
                "type": "number",
                "description": "Your confidence 0-1"
            },
            "uncertainty_reason": {
                "type": "string",
                "description": "What specifically makes you uncertain"
            },
        },
        "required": [
            "email_summary",
            "preliminary_classification",
            "confidence",
            "uncertainty_reason",
        ],
    },
}
```

### Multi-turn classification flow

Each email classification follows this flow:

```
1. Send email to Haiku with consult_advisor tool available
   → Haiku either:
     (a) Returns text with JSON classification (no escalation, 1 API call)
     (b) Calls consult_advisor tool (escalation, 3 API calls total)

2. If tool call:
   → Extract tool input (email_summary, preliminary_classification,
     confidence, uncertainty_reason — fully logged)
   → Send to Opus via call_advisor() with advisor system prompt
   → Opus returns guidance (classification recommendation + reasoning)

3. Return Opus guidance as tool_result to Haiku
   → Haiku incorporates advice and returns final JSON classification
```

**No escalation (1 call):**
```python
response = api("POST", "/messages", {
    "model": config.executor_model,
    "max_tokens": 1024,
    "tools": [ADVISOR_TOOL],
    "system": SYSTEM_PROMPT,
    "messages": [{"role": "user", "content": email_text}],
})
# response.stop_reason == "end_turn", content has JSON classification
```

**With escalation (3 calls):**
```python
# Call 1: Haiku decides to escalate
resp1 = api("POST", "/messages", {...})
# resp1.stop_reason == "tool_use"
# Extract tool_use block: tool_input has email_summary, confidence, etc.

# Call 2: Route to Opus
advisor_resp = api("POST", "/messages", {
    "model": config.advisor_model,
    "max_tokens": 512,
    "system": ADVISOR_SYSTEM_PROMPT,
    "messages": [{"role": "user", "content": format_advisor_query(tool_input)}],
})

# Call 3: Return guidance to Haiku
resp3 = api("POST", "/messages", {
    "model": config.executor_model,
    "max_tokens": 1024,
    "tools": [ADVISOR_TOOL],
    "system": SYSTEM_PROMPT,
    "messages": [
        {"role": "user", "content": email_text},
        {"role": "assistant", "content": resp1["content"]},
        {"role": "user", "content": [{"type": "tool_result", ...}]},
    ],
})
# resp3 has final JSON classification
```

### System prompt design

Two system prompts:

**Executor (Haiku) system prompt** must accomplish:

1. **Classification instruction**: Return JSON with `category`, `confidence`,
   `reasoning` fields
2. **Escalation instruction**: "Before classifying any email as low-priority,
   consider whether it could be a real lead. If there is ANY chance the email
   is from a real person seeking work, business, or connection, use the
   consult_advisor tool before making your final decision."

This is how we implement "mandatory escalation for high-stakes" -- Haiku
decides when to call the tool, not us
(see brainstorm: decision 3, implementation note).

**Advisor (Opus) system prompt**: "You are a senior email classification
advisor. A junior classifier is uncertain about an email. Review their
preliminary assessment and the email details. Return JSON with your
recommended `category`, `confidence`, and `reasoning`. Focus on whether this
could be a real lead that should not be missed."

**Full observability advantage:** Unlike the `advisor_20260301` tool (where the
executor curates context opaquely), the custom tool gives us complete
visibility into what Haiku sends to the advisor (the tool input fields) and
what Opus returns (the full advisor response). Both are logged.

### Classification taxonomy

Two tiers (see brainstorm: decision 4):

**High-stakes (must surface):**
- `gig_inquiry` -- music/sound work availability, rates, projects
- `business_opportunity` -- workshop bookings, consulting, partnerships
- `genuine_networking` -- industry contacts, collaborators, real people

**Low-priority (safe to defer):**
- `subscription` -- newsletters, digests
- `marketing` -- promotional emails
- `notification` -- GitHub, services, receipts
- `social_digest` -- social media notifications

### Email input fields

Each sample email provides: `sender` (name + address), `subject`, and `body`
(plaintext, max ~500 words). No attachment handling, no HTML parsing, no
thread context. This is the minimum viable input for classification. If the
experiment shows sender/subject alone are insufficient, that's a finding.

### Test email set (20 emails)

The test set must include deliberately ambiguous cases to stress-test
escalation:

| # | Category | Description | Ambiguity | `should_escalate` |
|---|----------|-------------|-----------|-------------------|
| 1-3 | `gig_inquiry` | Clear gig requests with rates/dates | Low | `false` |
| 4-5 | `business_opportunity` | Workshop/consulting inquiries | Low | `false` |
| 6-7 | `genuine_networking` | Industry contacts reaching out | Low | `false` |
| 8-10 | `subscription` | Obvious newsletters with unsubscribe | Low | `false` |
| 11-12 | `marketing` | Promotional blasts with offers | Low | `false` |
| 13-14 | `notification` | GitHub/service alerts | Low | `false` |
| 15-16 | **Ambiguous** | Marketing email using casual "Hey Alex" tone, mimicking personal outreach | High | `true` |
| 17-18 | **Ambiguous** | Newsletter from a real contact (genuine person, but subscription content) | High | `true` |
| 19 | **Ambiguous** | Cold outreach that could be spam OR a real gig lead | High | `true` |
| 20 | **Ambiguous** | Conference invite that could be marketing OR genuine networking | High | `true` |

Each test email has two ground truth labels:
- `ground_truth`: the correct classification category
- `should_escalate`: whether this email is ambiguous enough that Haiku should
  consult the advisor (`true` for emails 15-20, `false` for 1-14)

### Escalation accuracy metrics

Using the `should_escalate` labels, compute a confusion matrix:

| | Actually escalated | Did not escalate |
|---|---|---|
| **Should escalate** | True Positive (TP) | False Negative (FN) -- missed escalation |
| **Should not escalate** | False Positive (FP) -- unnecessary escalation | True Negative (TN) |

From this, derive:
- **Escalation recall** = TP / (TP + FN) -- "of emails that needed escalation,
  how many did Haiku actually escalate?" Sandbox target: >= 0.83 (miss at most
  1 of 6). This is a safety-oriented heuristic, not a statistically rigorous
  threshold -- with only 6 `should_escalate` emails, one missed escalation
  swings recall from 1.0 to 0.83. The target means "if Haiku misses 2+ of 6,
  the prompt instructions need rework before proceeding to step 2."
- **Escalation precision** = TP / (TP + FP) -- "of emails Haiku escalated, how
  many actually needed it?" Sandbox target: >= 0.50. Lower precision is
  acceptable since false positives cost money, not missed leads. On a 20-email
  set this is directional only -- meaningful precision measurement requires
  the step 2 retrofit with real email volume.
- **Unnecessary escalation rate** = FP / total -- cost overhead from Haiku
  being too cautious. Track it, but don't gate on it at this sample size.

### Structured logging

Each classification logged as one JSON line to `email_classifier_results.jsonl`:

```json
{
  "email_id": "sample_15",
  "sender": "alex@marketingco.com",
  "subject": "Hey Alex, quick question",
  "ground_truth": "marketing",
  "should_escalate": true,
  "haiku_preliminary": "genuine_networking",
  "haiku_confidence": 0.6,
  "haiku_uncertainty_reason": "Sender uses casual tone but could be marketing",
  "escalated": true,
  "advisor_recommendation": "marketing",
  "advisor_reasoning": "Sender domain is marketingco.com, casual tone is a common outreach pattern",
  "advisor_changed_answer": true,
  "final_decision": "marketing",
  "executor_input_tokens": 245,
  "executor_output_tokens": 89,
  "advisor_input_tokens": 312,
  "advisor_output_tokens": 45,
  "total_cost_usd": 0.0003,
  "latency_ms": 1240,
  "api_calls": 3,
  "timestamp": "2026-04-09T15:30:00Z"
}
```

**All fields are fully observable.** The custom tool proxy eliminates the
provisional field problem from the original plan:
- `escalated`: deterministic -- `true` if Haiku returned `stop_reason: "tool_use"`
- `haiku_preliminary` + `haiku_uncertainty_reason`: extracted from tool input
- `advisor_recommendation` + `advisor_reasoning`: extracted from Opus response
- `advisor_changed_answer`: computed by comparing `haiku_preliminary` != `final_decision`
- Token counts: from separate `usage` blocks on each API call
- `api_calls`: 1 (no escalation) or 3 (escalation)

### Summary report

Printed after all classifications:

```
=== Email Classifier Results ===
Total emails: 20
Correct classifications: 18/20 (90%)

Lead safety (HARD CONSTRAINT):
  High-stakes emails: 7
  Correctly identified: 9/9 (100%) ✓ PASS

Escalation accuracy (sandbox targets, n=6 ambiguous):
  Should have escalated: 6
  Actually escalated: 5  (TP=5, FN=1)
  Unnecessary escalations: 1  (FP=1)
  Escalation recall: 0.83 (5/6) -- target >= 0.83
  Escalation precision: 0.83 (5/6) -- target >= 0.50
  Advisor changed answer: 3/5 escalations

Cost:
  Total API calls: 30  (20 initial + 10 advisor round-trips)
  Total: $0.0045
  Per email: $0.000225
  Advisor overhead: $0.0012 (27% of total)
  Haiku-only baseline: $0.0033
```

### Out of scope: Gmail integration

Gmail mode (`--gmail` flag) is a **separate follow-up plan** after this
experiment validates the advisor pattern on sample data. It is explicitly
non-blocking for this cycle. See brainstorm for Gmail integration notes
and gig-lead-responder learnings that will apply when that plan is written.

## System-Wide Impact

Minimal -- this is a standalone script with no dependencies from other apps.

- **No interaction with existing sandbox apps** -- separate entry point
- **Shared `.env` file** -- adds no new keys (uses existing `ANTHROPIC_API_KEY`)
- **New test file** -- `tests/test_email_classifier.py`

## Acceptance Criteria

### Phase 0 (verify custom tool proxy) — PASSED
- [x] Haiku calls `consult_advisor` tool on an ambiguous email
- [x] Full multi-turn flow works (Haiku → tool call → Opus → tool result → Haiku final answer)
- [x] Tool input fields (email_summary, preliminary_classification, confidence, uncertainty_reason) are populated meaningfully by Haiku
- [x] Multi-turn exchange saved to `advisor_spike_response.json`
- [x] No prompt tuning needed — Haiku called tool on first attempt

### Phase 1 (sample mode classifier)
- [ ] `email_classifier.py` exists at repo root
- [ ] `python3 email_classifier.py` classifies 20 sample emails and prints summary
- [ ] Structured JSON results written to `email_classifier_results.jsonl`
- [ ] Each sample email has `ground_truth` and `should_escalate` labels
- [ ] Summary report shows: classification accuracy, escalation confusion matrix (TP/FP/FN/TN), escalation recall/precision, lead safety, cost breakdown
- [ ] Zero missed leads in test set (all high-stakes emails correctly identified)
- [ ] Config uses frozen dataclass (model strings, max_uses centralized)
- [ ] `tests/test_email_classifier.py` covers: config creation, sample email loading, result logging, summary calculation

## Success Metrics

(see brainstorm: resolved question 3)

### Hard constraint (must pass)

- **Lead safety:** 0 missed leads. Every high-stakes email (gig inquiry,
  business opportunity, networking) correctly identified. On a 20-email set,
  this means 9/9. One miss = experiment fails and prompt needs rework.

### Primary metrics (what we're here to learn)

- **Escalation recall:** Sandbox target >= 0.83. Of the 6 ambiguous emails
  labeled `should_escalate: true`, Haiku escalates at least 5. This is a
  safety-oriented heuristic gate -- with only 6 ambiguous emails, it means
  "if Haiku misses 2+, the prompt needs rework." Not a statistical threshold.
- **Escalation precision:** Sandbox target >= 0.50. At least half of Haiku's
  escalations were on emails that actually needed it. Directional on a
  20-email set -- meaningful precision requires step 2 volume.
- **Advisor value:** At least 1 case where the advisor changed Haiku's
  classification on an ambiguous email. If Opus never changes the answer,
  the advisor adds cost without value.

### Secondary metrics (informational, no pass/fail at this sample size)

- **Cost per email:** Track and report. Cost patterns become meaningful at
  scale (step 2 retrofit), not on 20 emails.
- **Escalation rate:** Total escalations / total emails. Informational for
  tuning `max_uses` and prompt instructions.
- **Latency:** Track per-classification. No threshold on sandbox.

## Dependencies & Risks

**Dependencies:**
- `ANTHROPIC_API_KEY` in `.env` (already exists)
- `requests` and `python-dotenv` packages (already used by other scripts)

**Risks:**

| Risk | Impact | Mitigation |
|------|--------|------------|
| Haiku never calls `consult_advisor` tool | Cannot test escalation at all | Phase 0 spike detects this. Tune system prompt to strongly encourage tool use on ambiguous cases. If prompt tuning fails after 2-3 attempts, STOP and fall back to confidence-threshold routing |
| Haiku calls tool on every email | No cost savings, defeats the pattern | Tune system prompt to be more specific about what warrants escalation. Track escalation rate per run |
| Haiku doesn't escalate on ambiguous emails | Escalation recall < 0.83, experiment inconclusive | Strong prompt instructions + 6 deliberately ambiguous test emails + `should_escalate` labels to measure precisely |
| Multi-turn latency too high | Escalated emails take 3x longer | Acceptable for sandbox. Track latency per email. Latency is a secondary metric |
| API error (429/500/timeout) mid-batch | Results for already-processed emails lost | Write each result to JSONL immediately after classification (append mode). Wrap each email's API call in try/except, log errors as `{"error": "..."}` lines, continue to next email |
| Haiku returns malformed JSON | Classification fails silently | Parse response JSON in try/except, log raw response on parse failure, continue to next email |
| Opus advisor disagrees but Haiku ignores advice | Advisor value metric meaningless | After tool result, Haiku must respond -- its final answer is what we log. If it ignores Opus consistently, that's a finding about the tool-use pattern |

## Quality Gate Answers

1. **What exactly is changing?** Adding `email_classifier.py` at repo root,
   `advisor_spike_response.json` (Phase 0 output),
   `tests/test_email_classifier.py` in tests dir, results file at
   `email_classifier_results.jsonl`.

2. **What must not change?** Existing sandbox apps, `.env` structure, other
   scripts (`deep_researcher.py`, `content_pipeline.py`), test patterns.

3. **How will we know it worked?** Phase 0: Haiku calls the `consult_advisor`
   tool on an ambiguous email, full multi-turn completes. Phase 1: summary
   report shows zero missed leads (9/9 high-stakes), escalation recall meets
   sandbox target >= 0.83 (heuristic gate), and at least one case where the
   advisor changed Haiku's classification.

4. **Most likely way this plan is wrong?** Haiku might not reliably call the
   `consult_advisor` tool when it should -- LLMs can be inconsistent about
   tool use. Phase 0 tests this with prompt tuning. If Haiku can't be
   prompted to escalate on ambiguous cases, the custom tool approach fails
   and we need confidence-threshold routing (programmer-driven, not
   executor-driven).

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-04-09-advisor-strategy-brainstorm.md](docs/brainstorms/2026-04-09-advisor-strategy-brainstorm.md)
  Key decisions carried forward: throwaway script approach, dual escalation
  strategy, two-tier classification taxonomy, max_uses 5, lead safety as
  hard constraint.

### Internal References

- Tiered model routing: `research-agent/docs/solutions/architecture/tiered-model-routing-planning-vs-synthesis.md`
- Existing API scripts: `deep_researcher.py`, `content_pipeline.py`
- Frozen dataclass pattern: `research-agent/docs/solutions/architecture/model-string-unification.md`

### External References

- Anthropic advisor strategy blog post (April 9, 2026)
- Advisor tool API: `advisor_20260301` -- not live as of 2026-04-09, see
  `advisor_spike_response.json` for spike results
- Messages API tool use documentation (custom tools, multi-turn)

## Feed-Forward

- **Hardest decision:** Pivoting from `advisor_20260301` (not live) to custom
  tool proxy. The key insight: a custom tool where Haiku decides when to call
  it is executor-driven self-escalation -- the same behavior as the advisor
  tool, just with us handling the routing. This is different from confidence-
  threshold routing where we decide when to escalate (programmer-driven).
- **Rejected alternatives:** Waiting for `advisor_20260301` to go live
  (unknown timeline), confidence-threshold routing (tests different behavior,
  kept as fallback if Haiku won't call the tool), extended thinking budgets
  (doesn't test multi-model routing), giving up on the experiment entirely.
- **Least confident:** Whether Haiku will reliably call the `consult_advisor`
  tool when it should. LLMs can be inconsistent about tool use, especially
  when the task (email classification) doesn't obviously require a tool. The
  system prompt needs to make the tool feel natural and necessary for
  ambiguous cases. Phase 0 tests this directly.
