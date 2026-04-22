---
title: "Lead Scraper V2 Phase 2 Brainstorm"
date: 2026-04-21
project: lead-scraper
phase: brainstorm
feed_forward:
  risk: "Opener prompt rewrite may over-correct -- adding too many rules makes Haiku brittle. Test each change in isolation."
  verify_first: true
---

## Opener Benchmark Result: FAIL (2/5)

### Setup

5 synthetic leads with realistic hooks (tiers 1-3), generated via `_generate_opener()` calling Claude Haiku 4.5 with the current `_OPENER_SYSTEM_PROMPT`.

### Rubric (4 criteria, pass = 3+/4 per lead, overall pass = 4/5 leads)

| Criterion | Description |
|-----------|-------------|
| Sounds like Alex | Casual, personal, musician/consultant voice. Not corporate or templated. |
| Hook-specific | References the activity without echoing the hook's exact words/stats. |
| 1-2 sentences | Short. |
| Opens conversation | Invites a reply, not a dead-end compliment. |

### Scores

| Lead | Alex voice | Hook-specific | Length | Opens convo | Score | Pass? |
|------|-----------|---------------|--------|-------------|-------|-------|
| Sacha Boutros | Yes | Partial (parrots "bringing people together") | 1 sent | No | 2.5/4 | FAIL |
| John Beaudry | Yes | Yes (reframes philosophy) | 2 sent | Moderate | 3.5/4 | PASS |
| Madison Keith | Partial ("impressive" generic) | Yes but echoes stats | 1 sent | No | 2.5/4 | FAIL |
| Pat Cruz | Partial ("impressive" again) | Yes but echoes stats | 1 sent | No | 2.5/4 | FAIL |
| Daniela Torres | Yes | Yes (reframes theme) | 1 sent | Moderate | 3/4 | PASS |

### Failure Patterns

1. **Hook parroting**: Despite Rule 1 ("NEVER copy the hook text"), 3/5 openers echo stats or phrases from the hook (e.g., "doubling engagement", "30 muralists", "bringing people together through music"). The model rewrites the words but keeps the same information structure.

2. **"Impressive" repetition**: The word "impressive" appeared in 3/5 openers. This is the Haiku equivalent of "amazing" -- a filler word that signals "I don't know what to actually say about this."

3. **Dead-end compliments**: 4/5 openers are observations that don't invite a response. Nobody replies to "that was impressive" with anything more than "thanks." The few-shot examples in the prompt DO include conversation-opening elements ("The Dalida revival alone was worth showing up for" implies shared knowledge), but the model isn't generalizing this.

### Proposed Prompt Fixes (for Plan phase)

**Fix A: Add explicit banned words list**
Add to rules: `6. NEVER use: "impressive", "amazing", "incredible", "remarkable". Use specific observations instead.`

**Fix B: Add conversation-opening rule**
Add to rules: `7. End with something that implies shared context or curiosity, not a compliment. Good: "the Dalida revival alone was worth showing up for." Bad: "that was really well done."`

**Fix C: Add contrastive FAIL example**
From the gig-lead-responder solution doc on contrastive pairs: add a FAIL example that shows high-quality prose using the wrong pattern (a polished compliment that doesn't open conversation). The model needs to see WHAT NOT TO DO, not just what to do.

```
FAIL (polished but dead-end): Madison, Operation Max Wave was impressive — doubling engagement over four months takes real strategy.
PASS (opens conversation): Madison, the way Max Wave played the long game on socials reminded me of how album rollouts used to work. Four months is a real commitment.
```

**Fix D: Reduce stat echoing via negative example**
```
FAIL (stat echo): Pat, getting 30 muralists and 2,000 people to Barrio Logan is no small feat.
PASS (personal angle): Pat, the Barrio Logan Art Walk had a different energy this October. Walking through that many murals in one stretch changes how you see the neighborhood.
```

### P3 Triage (from Phase 1 Review)

Applying won't-fix criteria from gigprep P3 batch cleanup doc:

| P3 | Action | Rationale |
|----|--------|-----------|
| CSV formula injection on import | **FIX** | Real attack vector, sanitize_csv_cell already exists for export but import path is unprotected |
| CSRF on Flask delete endpoint | **FIX** | State-changing POST with no CSRF token. Flask-WTF or manual check. |
| Cache templates in generate loop | **DEFER** | <3 templates, fs reads are ~0.1ms. Premature optimization. |
| Extract _transition_status() helper | **WON'T FIX** | Only 3 callers (approve, skip, sent), each has distinct logic. Abstraction adds indirection for no dedup. |
| CSV field map redundant keys | **WON'T FIX** | Cosmetic, 2 consumers, no bug risk. |
| CSV phone column warning | **FIX** | Users expect phone import to work. Print a clear warning explaining phone comes from enrichment, not import. |
| .env parser quoted values | **DEFER** | Edge case (quoted values with spaces). No user has hit this. Fix when it's reported. |

### Phase 2 Scope Proposal

**Must-do (blocks production use):**
1. Opener prompt rewrite (benchmark fails)
2. CSV formula injection on import
3. CSRF on Flask delete endpoint

**Should-do (improves UX):**
4. CSV phone column warning on import
5. --limit calibration after first real campaign

**Defer to Phase 3:**
- Template caching
- .env parser quoted values

**Won't fix:**
- _transition_status() helper (YAGNI)
- CSV field map redundant keys (cosmetic)

### Open Questions for Plan Phase

1. Should the opener prompt fix be benchmarked incrementally (one fix at a time, re-run after each) or all-at-once? Incremental is slower but tells you which fix actually helped.
2. CSRF: Flask-WTF (full library) vs manual X-Requested-With header check? The gig-lead-responder used X-Requested-With. Flask-WTF is heavier but standard.
3. Is 4/5 the right pass threshold, or should we accept 3/5 for v2 and iterate?

## Feed-Forward

- **Hardest decision:** Whether to include the opener prompt fix in Phase 2 scope or treat it as a separate prompt-engineering spike. It's the highest-risk item (LLM behavior is non-deterministic) but also the one that blocks production use.
- **Rejected alternatives:** Skipping the benchmark and shipping the current prompt ("good enough"). The 2/5 score proves it's not good enough -- dead-end compliments defeat the purpose of personalized outreach.
- **Least confident:** Whether Fixes A-D will be sufficient or if the prompt needs a fundamentally different structure (e.g., chain-of-thought, separate "rewrite" step). The contrastive pair approach from gig-lead-responder is the best bet, but Haiku may need more examples than Opus.
