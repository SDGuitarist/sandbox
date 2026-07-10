---
title: "Content-Graphic Template System"
date: 2026-07-09
status: complete
origin: "ideas.md (Workshop Story: 1 Ad → 288 Ads) + Metricool pipeline 'missing piece: graphic generation' — conversation 2026-07-09"
---

# Content-Graphic Template System — Brainstorm

## Problem

Posting across the two brands (Amplify AI, Alex Guillen Music) has mostly stopped because the per-post cost is too high for a solo operator. Today's workflow when a post does happen:

1. Come up with the content (manual thinking time)
2. Generate an image in an AI chat (usually ChatGPT) — a fresh prompt-and-iterate session every single time
3. Post/schedule manually

The image step has two hidden costs beyond time:
- **No batching:** each image is a one-off chat session; making 5 graphics costs 5x the effort of making 1.
- **No brand consistency:** every AI-generated image looks different. There is no recognizable visual identity across posts — the opposite of what a two-brand strategy needs.

The result isn't slow posting — it's *no* posting. The pipeline dies at production cost, not at ideas.

**Honest scope note:** a graphic template system removes step 2 only. Step 1 (coming up with content) is the copy side — that's `content_pipeline.py` / the mind-dump workflow's job. This brainstorm should not oversell itself as fixing the whole cadence problem; it fixes the marginal cost of the visual, and only pays off if the copy side flows too.

## Context
<!-- What exists today? What constraints do we have? What do we know? -->
- Current image tool: ChatGPT image generation, ad hoc, per-post
- Copy generation exists in code: `content_pipeline.py` (sandbox) — structured per-platform output (## Instagram Post / ## LinkedIn Post / ## Facebook Post)
- Scheduling target: Metricool API (Advanced 15 plan includes API) — see ideas.md "Metricool API Automation"
- Prior lessons loaded (2026-07-09 compound-start): Phase 0 fixture spike before automation loop; pure renderTemplate(data) separate from Metricool I/O; versioned template (TEMPLATE_VERSION) against slot drift; single staging file to prevent multi-file state drift
- **`content_pipeline.py` status: DORMANT.** It has not been producing copy Alex actually publishes. A graphic template built in isolation plugs into nothing.
- **Goal (from Alex, 2026-07-09):** 3 posts/week, purpose = stay visible. Modest volume — ~12 posts/month. This justifies a simple build, not a production system.
- Solo operator, shrinking bandwidth (RA) — upkeep cost matters more than capability. Anything requiring per-post fiddling recreates the original problem.

## Options

### Option A: Thin end-to-end slice, one brand (reframed scope)
Revive the whole chain as one minimal weekly loop for ONE brand (Amplify first): mind-dump or topic list → `content_pipeline.py` generates the week's 3 posts → one HTML/CSS template + Playwright renders a graphic per post (start with a single 1:1 format) → Metricool API schedules copy+graphic. One weekly ~30-min review session, batch of 3.
- **Pros:** attacks the actual problem (no posting) not a sub-problem; every component gets exercised immediately; the template has a live consumer from day one; matches the 3x/week goal exactly; weekly batching fits solo bandwidth
- **Cons:** wider scope than a template alone — three integration points (pipeline, render, Metricool) each with unknowns; Metricool API contract unverified (prior-lesson risk class: API assumptions); more to debug when something breaks

### Option B: Graphic template system only (original scope)
Build the HTML/CSS + JSON + Playwright renderer as a standalone tool. Copy stays manual (or ChatGPT), posting stays manual; the template just replaces the ChatGPT image session.
- **Pros:** small, one-session build; zero external API risk; template quality gets full attention; useful even if pipeline stays dormant
- **Cons:** removes only 1 of 3 friction points — posting likely stays near zero, tool likely goes dormant next to the pipeline; builds inventory instead of outcome (violates the 30-day outcome test)

### Option C: No-code path — locked brand look inside existing tools
No build. Create a reusable brand style: either Canva Bulk Create (CSV → template → batch export) or a pinned ChatGPT/Gemini prompt + reference image that reproduces a consistent card look. Keep posting manual.
- **Pros:** zero code, starts today, tests whether consistent visuals even matter before investing; Canva bulk-create is genuinely close to the template concept
- **Cons:** doesn't integrate with content_pipeline.py or Metricool (manual glue forever); Canva template ownership lives in a subscription, not the repo; per-post manual steps remain, so the cadence problem persists; AI-image consistency via prompt is unreliable in practice

## Tradeoffs
- **Outcome vs. build size.** A is the only option that can produce the actual outcome (3 posts/week live) — but it's ~3x the scope of B. B and C are smaller but optimize a step of a pipeline that isn't flowing.
- **Upkeep vs. capability.** For a solo operator with shrinking bandwidth, the deciding metric is *minutes of human time per published post*, not feature count. A minimizes it (batch review only); B and C keep manual glue in the loop.
- **Risk concentration.** A's risk is integration (esp. unverified Metricool API contract). Mitigation from prior lessons: Phase 0 spike each integration point with fixtures before wiring the loop.
- **What matters most:** posts actually going out within 30 days. Brand-visual polish is secondary to cadence.

## Decision

**Option A — thin end-to-end slice, aggressively narrowed** (decided by Alex, 2026-07-09):

- ONE brand: Amplify AI (it's the one selling something)
- ONE format: 1:1 square (works on all three platforms)
- ONE template, versioned (`TEMPLATE_VERSION = 'v1'`)
- Weekly loop: topic input → `content_pipeline.py` writes 3 posts → template renders 3 graphics → Metricool schedules → Alex reviews the batch once (~30 min/week)
- **Phase 0 spikes before any loop-building** (per prior lessons): (1) push one image + caption through the Metricool media-upload + schedule endpoints and see it land; (2) render 3 real posts through the template as fixtures and verify 1080×1080 output
- **Graceful degradation:** if the Metricool spike fails, the system still generates the weekly batch and Alex schedules manually in Metricool's UI (~5 min/week) — still a win
- Expansion (music brand, 4:5/16:9 formats, thumbnail template) only after 4 consecutive weeks of 3-posts/week cadence

Why A: the goal is an outcome (3 posts/week visible), not a capability. B's template gets built anyway as a component of A; A is B plus the plumbing that makes B matter. B and C both leave manual glue in the loop, which is the exact failure mode that made the pipeline dormant.

## Open Questions

- **Metricool media upload contract:** does `PUT /v2/media/s3/upload-transactions` + `POST /v2/scheduler/posts` work as documented on the Advanced 15 plan with our token? Never exercised. → Phase 0 spike #1
- **Why is `content_pipeline.py` dormant?** Output quality, missing topic feed, or just friction? Needs a look before assuming it's usable as-is. Does its output need a voice-guardian pass before scheduling?
- **Topic input source:** manual weekly list vs. mind-dump file (ideas.md "Mind-Dump Workflow"). Start manual; automate only if the manual step becomes the bottleneck.
- **Playwright render fidelity:** fonts, emoji, text overflow at 1080×1080. → Phase 0 spike #2
- **Do templated graphics actually lift engagement vs. text-only?** Unknown. First 2 weeks of live posts are the cheap test — don't over-invest in template polish before that reads out.
- **Human-in-the-loop gate:** review-before-schedule vs. schedule-with-cancel-window. Start with review-before-schedule (outward-facing content, voice risk).

## Feed-Forward
- **Hardest decision:** template-only (original idea) vs. end-to-end slice. Chose end-to-end because the copy pipeline is dormant — a component built in isolation would go dormant beside it. The goal is posts going out, not tooling existing.
- **Rejected alternatives:** Option B (template only — polishes one gear of a stopped machine; fails the 30-day outcome test); Option C (Canva Bulk Create / locked ChatGPT brand prompt — zero code but manual glue persists, template ownership lives in a subscription, AI-prompt visual consistency unreliable).
- **Least confident:** (1) the Metricool API media-upload contract — completely unexercised, and the whole "scheduled automatically" promise rests on it; (2) whether templated graphics improve engagement over text-only posts at all. Both are cheap to test before building: spike #1 answers the first, the first two live weeks answer the second.
