---
title: Ethics Toolkit - AI Filmmaking Ethics Platform
date: 2026-04-30
status: brainstorm
deadline: 2026-05-30
build_method: autopilot
---

# Ethics Toolkit (Working Title)

Interactive web platform that gives filmmakers practical ethics tools for AI adoption. Used live at the May 30 workshop AND as a standalone take-home product. Full platform scope -- five integrated tools, dual-mode workshop UX, payments, email automation.

This is an autopilot stress test: full platform in 30 days via swarm build.

## The Problem

Filmmakers are adopting AI with no structured way to evaluate risk, document usage, disclose properly, or check festival compliance. The ethics conversation is loud but the practical tools don't exist. Actors have SAG-AFTRA. Writers and composers have protections that are uneven, fragmented, and less visible than performer protections. Alex's ethics frameworks (Three Questions, 3 C's, Risk Tiers, behind-the-camera protection gap) fill this gap -- but they're trapped in workshop handouts and a manifesto PDF.

This platform makes those frameworks interactive, persistent, and shareable.

**Important: This platform provides guidance, not legal advice.** All tools frame output as ethical frameworks and practical decision support, not legal counsel. Users needing legal review are directed to an entertainment attorney.

## What We're Building

Five integrated tools in one platform, powered by Alex's original ethics frameworks:

### Tool 1: AI Disclosure Generator
- Filmmaker inputs what AI was used for (writing, music, VFX, voice, storyboard, etc.)
- Outputs a properly worded disclosure statement ready for festival submissions
- **Deterministic:** structure, required fields, compliance checklist
- **Probabilistic (AI):** natural language wording tailored to their specific project

### Tool 2: Festival Policy Lookup
- Searchable database of festival AI policies (starting with 12+ already researched)
- "Does Sundance allow AI music?" "What does SXSW require for disclosure?"
- **100% deterministic** -- policies are facts, no AI needed
- Free and fully open (SEO magnet, top-of-funnel entry point)
- v1 data: human-curated policies with source URL, last-reviewed date, and confidence level. Existing scraper infrastructure (sandbox/venue-scraper) can be adapted for automated refresh post-launch.

### Tool 3: Project Risk Scanner
- Filmmaker inputs project details (roles, AI usage per department, content type)
- Returns a risk profile across legal, ethical, reputational, and union compliance dimensions
- Built on Risk Tiers framework + behind-the-camera protection gap
- **Deterministic:** scoring, risk tiers, role vulnerability mapping
- **Probabilistic (AI):** contextual recommendations based on project specifics
- Key upsell driver: "Your score is high -- want help fixing it?" leads to consulting

### Tool 4: AI Provenance Chain Builder
- Filmmaker logs what was human-made vs. AI-assisted vs. AI-generated across every department
- Creates an audit trail for distributors, festivals, or unions
- **100% deterministic** -- it's record-keeping, not analysis
- Ahead of regulation (C2PA is coming). First-mover advantage.

### Tool 5: Budget vs. Ethics Calculator
- Input: task being considered for AI (score, VFX, storyboarding) + user's actual budget
- Output: cost savings AND ethical tradeoffs -- role displacement, worker protections, fair compensation
- App provides industry reference rates for comparison (researched data in `docs/reports/031-film-crew-rates-ai-comparison.md`)
- **Deterministic:** rate ranges, cost comparisons, role displacement data
- **Probabilistic (AI):** nuanced ethical implications specific to their scenario

## Why These Five Together

- **AI only for probabilistic output.** Deterministic data (policies, scores, logs) uses rules and templates. AI only generates text where the output genuinely varies by context.
- **Five tools, one workflow.** They chain naturally: "What are the rules?" (Policy Lookup) -> "Am I at risk?" (Risk Scanner) -> "How do I disclose?" (Disclosure Generator) -> "Can I prove it?" (Provenance Chain) -> "Is this worth it?" (Budget Calculator)
- **Frameworks are the engine, not separate modules.** Three Questions, 3 C's, and consent spectrum are woven into the tools' reasoning -- not standalone educational pages.

## Workshop Identity Model

**Decision: Option A -- Anonymous workshop, optional email capture.**

- Workshop mode is fully anonymous. Attendees scan QR, join session, use tools. No login, no account, no friction.
- Results are ephemeral during the session. At the end (or anytime), a "Want to keep your results?" prompt offers email capture via magic link.
- Providing email creates an account, saves all session results, and starts the 14-day premium trial + post-workshop email sequence.
- Users who don't provide email lose results when the session ends. That's fine -- the workshop value was delivered live.
- This creates a natural conversion moment: "You just generated a risk score, a disclosure statement, and a provenance chain. Want to keep them?"

## Workshop UX (Dual-Mode)

The platform serves two modes. The self-serve version must stand alone. The facilitator layer adds on top.

### Self-Serve Mode (Default)
- User controls own pacing, sees only their data
- Progressive disclosure reveals complexity gradually
- Save/export results (requires account)
- Personalized results are the retention hook -- their risk score, their disclosure, their provenance chain

### Facilitator Mode (Workshop)
- A protected facilitator route that Alex controls from his laptop during workshops
- Projected view: large type, high contrast, step-by-step reveal, minimal chrome
- Attendees join on phones via QR code -- no download, no login, browser-based
- Single-action screens on mobile: one question, one tap, one result per screen
- Minimum 16pt body text on mobile, 44pt tap targets, primary actions in thumb zone

### Realtime Interactions (Minimal Build)

All realtime interactions use the same technical pattern: attendee sends a message to a Supabase Realtime channel, facilitator view subscribes and renders the aggregate. Different UI components, same plumbing.

**Five interaction types:**

1. **Polls** -- Alex asks a question ("Have you used AI in your last project?"), attendees tap an answer, live results appear on projected screen as a bar chart. Fast, one-tap. Good for transitions between sections and surfacing the room's ethical fault lines before diving into frameworks.

2. **Tool aggregation (Risk Scanner)** -- Everyone runs the Risk Scanner on their own project. Projected screen shows anonymized aggregate: "60% of this room has high risk in music. 40% have no disclosure plan." Individual results stay on phones. This is the strongest group moment -- turns a personal tool into a collective experience.

3. **Word cloud** -- Alex asks an open question ("What's your biggest concern about AI in your work?"). Attendees type one phrase. Words aggregate into a cloud on the projected screen, sized by frequency. Great for the OPEN phase -- lets Alex see what the room cares about and adjust his improvisation.

4. **Confidence slider (before/after)** -- Start of workshop: "How confident are you about where the ethical lines are?" Attendees slide 1-10. End of workshop: same question. Projected screen shows the shift. This is outcome proof -- screenshot it for marketing and case studies.

5. **Q&A queue** -- Attendees submit questions from phones. They appear on the facilitator view ranked by upvotes from other attendees. Alex picks from the top. No raised hands, no waiting. Quieter attendees participate equally.

**What we're NOT building for realtime:**
- Live leaderboards / gamification (wrong tone for ethics workshop)
- Free-text chat (too noisy, distracts from projected screen)
- Collaborative editing of any kind (complexity explosion)

### Workshop Technical Constraints
- Must degrade gracefully if venue WiFi fails. Cache festival data and rate data on device. Tools work individually even if realtime sync drops -- attendees just lose the projected aggregation.
- No app download. Browser-based only.
- QR code join. Project the code, attendees scan, they're in.
- Realtime sync for polls, tool aggregation, word cloud, confidence slider, and Q&A queue.

### Post-Workshop Retention
- End of workshop: "Want to keep your results? Enter your email." (conversion moment)
- 24-48 hours: personalized email with their specific results + deep link back
- 7 days: "Here's what others discovered" (anonymized aggregate)
- Day 10-12: premium expiry warning with specific usage data
- Day 14: graceful downgrade (UI-driven, no email)
- Day 21: win-back (discount or extension for engaged users)

### Privacy & Data
- Workshop inputs may include sensitive project details. All aggregated displays must be anonymized.
- Small rooms (< 10 attendees): minimum aggregate threshold before showing results on projected screen (e.g., "waiting for more responses" until 5+ submit)
- Consent copy at QR join: "Your individual answers are private. Only anonymized group results appear on screen."
- Stored data: results tied to email (if provided), anonymous session data deleted after 30 days.
- Users can delete their account and all associated data at any time.

## Monetization Model

**Model: Reverse Trial** -- users experience full value first, then downgrade to free tier.

### Free vs. Paid Boundary

| Tool | Free (habit-forming) | Paid (amplifier) |
|------|---------------------|-----------------|
| Festival Policy Lookup | Fully free (SEO magnet, top-of-funnel) | -- |
| Risk Scanner | Basic score (high/medium/low) | Detailed report + AI recommendations |
| Disclosure Generator | See template formats (show the value gap) | AI-customized wording for your project |
| Provenance Chain | 1 project, view only | Unlimited projects + PDF export |
| Budget Calculator | Cost comparison numbers | AI ethical analysis + displacement report |

**Principle:** Show what premium would fix (Grammarly model). Don't hide features -- let users see the value gap.

### Workshop Attendee Journey
1. Attends workshop ($175)
2. Scans QR code -> full premium access, anonymous, no login
3. End of workshop: "Want to keep your results?" -> email capture -> account created -> 14-day premium trial starts
4. Day 10-12: email with "here's what you used, here's what you'll lose"
5. Day 14: graceful downgrade to free tier (keep all data, lose premium outputs)
6. Day 21: win-back for engaged users

### Non-Attendee Journey
1. Finds app via search, content, referral (Festival Lookup is the SEO entry point)
2. Freemium: all tools available at basic level
3. Achievement-based upgrade prompts (after first success, not on a timer)
4. Subscription for unlimited premium access

### Anti-Patterns to Avoid
- Don't gate core functionality (kills the "aha moment")
- Don't hide premium features entirely (users can't evaluate what they can't see)
- Don't use time-based popups ("upgrade now!")
- Don't interrupt mid-task

## LLM Usage

Deterministic/probabilistic hybrid. AI only where output genuinely varies by context.

| Tool | AI needed for | Estimated cost/call |
|------|--------------|-------------------|
| Disclosure Generator | Natural language wording | Low (simple generation) |
| Risk Scanner | Contextual recommendations | Medium (analysis) |
| Budget Calculator | Ethical implications | Medium (analysis) |
| Festival Policy Lookup | None | $0 |
| Provenance Chain | None | $0 |

At subscription pricing, margin should be healthy even with heavy usage. Exact model routing (Haiku vs Sonnet) is a plan-phase decision.

## Rate Data

Industry rate research complete. Covers 8 AI-vulnerable roles with full tier breakdowns (student/indie/professional/studio), union minimums, and per-unit pricing. Reference: `docs/reports/031-film-crew-rates-ai-comparison.md`

Summary for $500K indie feature: $62,000-$171,000 combined for composer, VFX, storyboard, screenwriter, voice actor, editor, sound design, and colorist.

## IP Assets Powering This Platform

- **Three Questions Decision Framework** -- "Does it honor my creative intent? Can I stand behind every element? Would I put my name on it?"
- **The 3 C's** -- Consent, Compensation, Credit
- **Risk Tiers** -- Legal, ethical, reputational, union compliance dimensions
- **Behind-the-camera protection gap** -- Actors have SAG-AFTRA. Writers, composers, crew have protections that are uneven, fragmented, and less visible.
- **11-page manifesto** with 40+ primary source documents (union contracts, case law, festival policies)
- **Industry rate research** -- 8 roles, 4 budget tiers, union minimums

## Existing Infrastructure to Reuse

- **Scraper patterns:** `sandbox/venue-scraper/` has crawler/scraper infrastructure. Adapt for festival policy auto-refresh post-launch.
- **Producer Brief patterns:** Next.js + Vercel + Anthropic API + Zod validation + MockLLMProvider. Solution docs at `docs/solutions/2026-04-26-producer-brief-mvp-patterns.md`.
- **Sandbox solution docs:** Full library of patterns from previous builds (routing, CRUD, auth, API, testing).

## Decisions for Plan Phase

These topics were explored during brainstorm but should be formally evaluated and locked during the plan:

1. **Stack selection** -- Next.js + Vercel is the leading candidate (existing patterns from Producer Brief). Evaluate against alternatives.
2. **Auth provider** -- Supabase Auth is the leading candidate. Magic link for post-workshop account creation. Evaluate complexity.
3. **Real-time sync architecture** -- Supabase Realtime (WebSockets) is the leading candidate. Five interaction types all use the same channel/subscribe pattern. Evaluate message limits and disconnect behavior.
4. **Payment processor** -- Square is the leading candidate (consistency with workshop payments). Evaluate Stripe as alternative. Note: Square subscriptions require customer/subscription objects, plan variations, webhooks, and subscription status handling.
5. **Email service** -- Resend is the leading candidate (simple API, generous free tier). v1 sends simple opt-in lifecycle emails only, not behavior-triggered automation. Evaluate webhook/dedup needs.
6. **Subscription price point** -- $15/mo is the working number. Validate against indie filmmaker buying behavior (project-based vs monthly). Consider alternatives: per-project export, annual tier, workshop-included access.
7. **Trial length** -- 14 days based on Gartner/Recurly research (71% better conversion than 30-day). Confirm this applies to this audience.
8. **LLM model routing** -- Haiku for simple generation, Sonnet for complex analysis. Validate cost model with real prompts.
9. **Offline capability** -- Cache festival data and rate data on device. Tools degrade to "results will sync when connected." Define which flows work fully offline.
10. **App name** -- TBD (working title: "Ethics Toolkit"). Alex deciding separately.
11. **Autopilot phasing** -- Phased swarms with integration gates after each phase. Do not launch all agents over the whole platform at once. Define phase boundaries and shared interface specs.

## Open Questions

1. **App name** -- TBD
2. **Autopilot agent count** -- How many swarm agents for a platform this size? Previous max was 6. This may need more.
3. **Testing strategy** -- Unit tests per tool? Integration tests for the workflow chain? Workshop simulation tests with 30 concurrent users?
4. **Minimum aggregate threshold** -- How many attendees must respond before showing aggregated results on projected screen? (Prevents de-anonymization in small rooms.)

## Codex Review Integration (April 30)

Codex reviewed this brainstorm and flagged P0-P2 issues. Resolutions:

| Codex Finding | Resolution |
|--------------|-----------|
| P0: May 30 scope too broad | Rejected. Full scope. Autopilot has shipped platforms in under a week. |
| P0: Realtime sync unproven | Accepted partially. Building minimal realtime (5 interaction types, same plumbing). Manual fallback slides ready as backup. Rehearsal with simulated users before May 30. |
| P0: Festival auto-scraping | Resolved. v1 is human-curated with source URL + last-reviewed date + confidence level. Existing scraper infra adapts post-launch. |
| P0: No-login conflicts with saved results | Resolved. Option A identity model: anonymous workshop mode, email capture at end for persistence. |
| P1: Phased swarms | Accepted. Plan phase defines phase boundaries and integration gates. |
| P1: Five tools not equal for v1 | Rejected. All five ship. They chain as one workflow. |
| P1: Market claims too broad | Accepted. Softened language: "uneven, fragmented, less visible" not "almost nothing." Added "guidance, not legal advice" disclaimer. |
| P1: $15/mo may not fit | Deferred to plan phase. Will validate alternatives (per-project, annual, workshop-included). |
| P1: Square subscriptions complex | Noted. Plan phase evaluates Square vs Stripe based on actual subscription requirements. |
| P1: Email automation understated | Accepted. v1 sends simple opt-in lifecycle emails only. No behavior-triggered automation. |
| P2: Privacy/retention missing | Resolved. Added Privacy & Data section with anonymization thresholds, consent copy, retention policy, and deletion rights. |
| P2: Offline undefined | Resolved. Cache festival and rate data on device. Tools degrade gracefully. Full offline spec deferred to plan. |
| P2: Some plan decisions are brainstorm decisions | Resolved above. Identity model, festival data strategy, realtime scope, and market framing locked in brainstorm. Stack/auth/payments/email remain plan decisions. |

## Feed-Forward
- **Hardest decision:** Keeping full scope against Codex's recommendation to cut. The bet is that autopilot swarm can handle platform-level builds, not just CRUD apps. If this works, it validates the build method for all future products. If it fails, May 30 workshop still works with manual fallback for realtime and individual tool use on phones.
- **Rejected alternatives:** Building tools as separate apps (fragments the experience and loses the workflow chain), pure rules with no AI (disclosure and risk outputs would feel generic and impersonal), required auth for all features (kills adoption and workshop participation), 30-day trial (research shows no conversion benefit over 14 days), native app (download friction kills workshop participation), reduced scope for May 30 (limits the autopilot stress test and fragments the product story).
- **Least confident:** Autopilot swarm at platform complexity. Previous builds were single-purpose apps (CRUD, API, dashboard). This has cross-cutting concerns: auth/entitlement, realtime sync, LLM integration, payment webhooks, email lifecycle, and five tools with different deterministic/probabilistic patterns. Phased swarms with integration gates mitigate this, but it's still unproven territory. If swarm agents produce mechanical code that misses product judgment or UX coherence, manual passes will be needed between phases.
