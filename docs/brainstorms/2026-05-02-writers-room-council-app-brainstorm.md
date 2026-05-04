# Writers Room Council App — Brainstorm

**Date:** 2026-05-02
**Author:** Alex Guillen, with Claude
**Status:** Complete — ready for plan
**Deadline:** May 30, 2026 (Amplify workshop, San Diego)

---

## What We're Building

A full-featured creative writing tool that operationalizes the Writers Room Council framework (v1.4) as a web app. Four modes, one shared identity system, shipping as beta at the May 30 Amplify workshop.

**Core positioning:** "Help you edit like you, and get better every time."

The app never writes a word. It interrogates, flags, and learns. The user's voice gets sharper, not replaced.

### The Four Modes

| Mode | Function | Architecture Type |
|------|----------|------------------|
| **Seed Council** | 5-beat interrogative sequence for writers with ideas but no draft. Excavates what the writer actually wants to write. | Conversational orchestration of existing v1.4 framework |
| **Standard Council** | 5-voice adversarial developmental feedback on drafted scripts. Produces Greenlight/Rewrite/Pass verdict. | Conversational orchestration of existing v1.4 framework |
| **Returning Writer Protocol** | Iteration evaluation across drafts. Reads previous central question and verdict before evaluating revision. | Conversational orchestration of existing v1.4 framework |
| **Editor** | 15-principle editorial analysis with inline annotations, accept/reject decisions, Crystal Principle filter, and signature learning that compounds over time. | Novel architecture: persistence layer, decision trail, signature compounding |

### The Developmental Arc

Seed (excavate idea) -> Draft (write the scene) -> Standard Council (develop) -> Revision -> Returning Writer Protocol (iterate) -> Editor (polish editorial judgment)

Users can enter at any mode that makes sense for where they are. Phase 0 always runs first regardless of entry point (it's intake, not a mode). "Enter at any point" means which mode you start with (Seed if you have an idea, Standard Council if you have a draft, Editor if you have a polished piece), not whether you skip intake. The app guides progression from the chosen entry point forward.

---

## Why This Approach

### The Problem
The WRC framework exists as a Claude Projects setup (~4,000-word system prompt). Workshop attendees get a handout that describes the framework but can't rebuild it. The IP is protected, but the user gets nothing they can use after the workshop. The app IS the IP protection layer: users get the outcome, framework instructions stay behind the interaction.

### The Solution
A web app where the framework's architectural constraints are enforced by the UX itself. App-controlled sequence with conversational input within each step. The user speaks freely; the app ensures the framework's rules hold (Phase 0 before anything, voices in order, no skipping beats, Crystal Principle filter on Editor suggestions).

### Why Not Simpler
- A chat interface would require enforcement logic bolted on top. The framework's sequence IS the product. A guided flow makes the structure a feature, not friction.
- A wireframe or demo would protect IP but give attendees nothing to use. Full app = full value = beta cohort acquisition.
- Separate tools per mode would lose the compounding story. One app, shared fingerprint, shared project state.

---

## Key Decisions

### 1. UX Paradigm: Hybrid (App-controlled sequence, conversational input)
**What it means:** The app controls beat progression, voice order, and phase gates. The user controls what they say within each step (free-text conversational input, no dropdowns or forms). The Council voices respond to what the writer actually said, calibrated to their specific seed/draft.

**Why:** The framework's sequence is architecturally fixed. Phase 0 before script, voices in order, no skipping. A chat interface would require building enforcement logic on top. A guided flow makes enforcement invisible. For the May 30 demo, guided flow also keeps the demo on the arc that produces the compounding moment.

### 2. Authentication: Magic link email via Supabase Auth
**What it means:** User enters email, gets a login link, no password. Beta cohort whitelisted. Post-beta, new signups hit paywall or waitlist.

**Why:** Lowest friction for workshop attendees (filmmakers and writers, not developers). No OAuth complexity. Supabase Auth handles it natively.

### 3. LLM Backend: Opus 4.6 for all modes
**What it means:** Every voice, every beat, every Editor suggestion runs on Claude Opus 4.6. No model tiering.

**Why:** The Contrarian's verb catch, the Champion's improvised questions, and the Editor's Crystal Principle filtering require Opus-level judgment. The verb catch that made the workshop volunteer gasp requires reasoning depth that Sonnet might miss. Cost is ~$0.50-1.00 per full council session, acceptable for a beta cohort of 5-15 users.

### 4. Editor UI: Inline annotations
**What it means:** Suggestions appear as highlighted marks in the document itself. User clicks a highlight to see the principle invoked, the flag, and the question. Accept/reject happens right there in the writing.

**Why:** The thesis is felt when the suggestion appears IN the writing, not in a list beside it. A side panel turns the Editor into a grammar checker. The doctor sentence scenario only lands emotionally if the flag appears in the sentence. Inline also makes the Crystal Principle filter visible in the right way: structural catches appear, voice formalizations don't, and the user feels the product's logic without being told.

### 5. Document Input: Paste text, editable on accept
**What it means:** User pastes their draft into a text area. App renders it with inline annotation capability. On accept: annotation clears, cursor lands in the flagged text, user rewrites in place. On reject: annotation clears, decision logged. If user accepts but doesn't change text, logged as accepted-no-edit (real signal, not enforced friction). Export final text when done.

**Why:** No file format headaches. Works for any source (Google Docs, Word, Scrivener, plain text). Editable-on-accept means the accept action hands the pen back to the user immediately. The rewrite rep is the muscle that produces compounding.

### 6. Phase 0 Fingerprint: Layered (user + project), serving both Council and Editor

Phase 0 is a single intake that calibrates both the Council (creative judgment) and the Editor (editorial judgment). It has three layers, each serving a different purpose.

**Layer 1: User-level fingerprint (runs once at account creation)**

Captures who the writer IS, independent of any project. Feeds both Council and Editor.

*Council-calibration fields:*
1. *"What kind of writing do you do most?"* (genre/form, maps to Council's genre calibration)
2. *"What's a theme or subject you keep returning to?"* (thematic obsessions, calibrates Champion's "what's worth protecting")
3. *"When your writing doesn't work, what's usually the problem? Structure? Characters? Endings?"* (structural instincts + failure patterns, calibrates which voices push hardest)
4. *"Describe your voice in a sentence. How would a reader who knows your work describe your tone?"* (voice/tone self-report, calibrates all five voices to not impose a foreign register)

*Editor-calibration fields:*
5. *"What's your worst writing habit, the one you catch yourself doing and cut in revision?"* (editorial failure pattern, primes signature before session one)
6. *"What register are you working in, and who's the reader you're writing toward?"* (Crystal filter calibration, Principle 9 baseline)

*Shared inputs (used by both):*
7. A writing sample (500-1000w): *"Share something you wrote that sounds like you."* (voice texture for both Council calibration and Editor principle-matching)
8. A before/after passage: *"Paste a passage you've edited before. Show the before and the after."* (editorial signature baseline from real edit delta, REQUIRED input. The delta tells the Editor what the writer already values; it tells the Council what the writer's self-editing instincts are.)

**Layer 2: Project-level calibration (runs per project, lightweight)**

Captures what the writer is WORKING ON right now. Short form, three questions:
1. What are you working on? (brief description)
2. What's this piece trying to do? (intent, calibrates Audience Proxy and Editor's function-determines-form principle)
3. What are you protecting in this piece? (voice/argument priority, calibrates Champion and Crystal filter)

**Layer 3: Seed Council micro-interview (runs within Seed Council only)**

NOT part of Phase 0. This is the coaxing prompt + three micro-interview questions that happen AFTER Phase 0, WITHIN a Seed Council session. It captures the seed itself and makes it specific enough for the council to push against. The micro-interview does not repeat Phase 0 questions. It asks about the specific image/moment/idea the writer is bringing to this session.

**How Phase 0, micro-interview, and project calibration differ:**
- Phase 0 (Layer 1) = who you are as a writer (persistent, runs once)
- Project calibration (Layer 2) = what you're working on (per-project, runs once per project)
- Micro-interview (Layer 3) = what you're bringing to THIS session (per-session, Seed Council only)

**Scoring Floor behavior:** If the writing sample and before/after passage together lack enough texture for the Council voices to generate genuine questions (they can only tell, not ask), the app flags this: *"Your intake doesn't give the council enough to work with. Add more detail to your writing sample or before/after passage."* The Scoring Floor prevents the Council from running in a degraded mode where voices declare instead of interrogate. The Editor can still run with a weaker baseline (it has the 15 principles as structure), but the signature dashboard flags that the baseline is weaker.

**Constraint:** The before/after passage is required. If a user skips it, the Editor runs on the writing sample alone with a weaker-baseline flag. The Council can still run but the Scoring Floor check is more likely to trigger.

### 7. Project Model: Project-based containers with full session state

**What it means:** Each writing project is a container holding the complete developmental arc. The data model must support the RWP (which reads prior state), the verdict handoff (which guides the next step), and the Editor (which compounds across passes).

**Project record fields:**
- Project metadata (title, created_at, genre, user_id)
- Project-level Phase 0 calibration (intent, what you're protecting)
- Current handoff state: what the app should prompt the user to do next (e.g., "submit revised draft", "run Editor pass"). Set by the verdict handoff logic.

**Per-session records (one per Council or Editor pass):**

*Seed Council sessions:*
- Full session transcript (all beats, all writer responses, stored as structured data, not a text blob)
- Named intent (what the writer named as worth protecting at Beat 2/5)
- Contrarian's unanswerable question (the deliverable)
- Closing handoff text delivered

*Standard Council sessions:*
- Draft version ID (links to the pasted text that was evaluated)
- Full session transcript (all 5 voices + writer responses)
- Verdict: Greenlight, Rewrite, or Pass
- Pass subtype (if Pass): premise_broken or reckoning_insufficient. Not formalized as separate verdicts in v1.4, but the app should store which meaning applies so the handoff text and suggestions differ.
- Verdict explanation (the council's reasoning)
- Central question (the load-bearing question the council surfaced)
- Revision map (structural guidance for what to address in revision)

*Returning Writer Protocol sessions:*
- Previous session reference (which council session this revision responds to)
- Previous central question (read from prior session, not re-derived)
- Draft version ID (the revised draft)
- Full session transcript
- New verdict + explanation + central question (the cycle continues)

*Editor sessions:*
- Draft version ID (the text that was analyzed)
- All suggestions generated (structural + voice, including suppressed)
- Per-suggestion: principle invoked, flag text, question, Crystal filter classification, user decision (accept/reject/accept-no-edit), timestamp
- Suppression count (voice formalizations filtered)
- Signature snapshot at session end (principle weights after this session's decisions)

**Why this matters:** The RWP needs the previous central question, verdict, and revision map as first-class data. The Editor needs decision history across sessions for signature learning. The handoff state drives the contextual next-step UX. If any of these live only in conversation history or are derived at read-time, the modes can't interoperate reliably.

### 8. Signature Dashboard: Dedicated view
**What it means:** A "My Signature" page showing which principles the user accepts most, which they reject, decision trail history, Crystal Principle suppression count, and compounding indicators.

**Design constraint:** Must be readable after TWO sessions, not just twenty. If it only becomes meaningful with a lot of data, it fails at the workshop demo. "3 decisions logged, tell-after-show flagged twice, both accepted" is honest and specific from session one.

**Empty state:** Before any Editor pass, the dashboard shows the user's Phase 0 data back to them: their stated worst habit, their register, and a collapsed preview of their before/after edit. Below: "0 documents edited, 0 decisions logged. Run your first Editor pass to start building your editorial signature." The dashboard pulls live from stored fingerprint fields (not hardcoded). If the user updates Phase 0, the echo updates. The product is already about them before a single session runs.

### 9. Tech Stack: Next.js 15 + Supabase + Anthropic SDK + Vercel
**What it means:** Same proven stack as the ethics-toolkit autopilot build. Next.js 15 App Router, Supabase (Auth + Postgres), Anthropic SDK (Opus 4.6), Vercel deploy, Tailwind CSS.

**Why:** Proven in autopilot pipeline. Supabase handles magic link auth, persistence (decision trail, signature, fingerprint, project state), and scales to post-beta without migration. Vercel AI SDK for streaming LLM responses.

### 10. Demo Flow: Seed Council live + Editor pre-loaded
**What it means:** May 30 demo runs live Seed Council with a workshop volunteer (proven to wow the room), then switches to Editor showing Alex's own pre-loaded writing with real inline annotations, accept/reject, and genuine compounding data from prior sessions.

**Why:** Two distinct wow moments. Seed Council live = the interrogation that made the Apr 25 room gasp (85% confidence, proven 3x). Editor pre-loaded = controlled demo of the thesis (90% confidence, Alex's own data). Combined: 15-20 min, one live energy moment + one proof-of-thesis moment.

### 11. Build Approach: Editor-first, 4 sequential phases with gates
**What it means:** Phase 1 (foundation) -> Phase 2 (Editor) -> Phase 3 (Council modes) -> Phase 4 (polish). Each phase has automated gates. Autopilot progresses through all four phases within one engineering loop.

**Why:** Editor is the novel architecture (persistence, signature learning, Crystal Principle filter). If it works, the rest is mechanical wrapping of an existing framework. If it doesn't, the hardest problem is in your hands by day ~10, not day 24. Sequential phases with gates match the proven autopilot pattern (Run 033: 4 phases, 15 agents, 116 files, 0 structural failures post-convergence).

### 12. Single Genre Profile at Launch: Essay/Long-form Editing
**What it means:** The Editor ships with one genre profile. Email/business communication is not a shipped feature despite a Core Voice document existing for it.

**Why:** The thesis is long-form judgment-presence. Workshop audience is creative writers. Multi-profile UX adds switching complexity that doesn't earn its keep at demo. One tightly-calibrated profile is a stronger product story than two loose ones.

### 13. Beta Cohort, Not Free Trial
**What it means:** Workshop attendees become beta testers with 14-day free access. Paid tier launches post-beta. Beta framing = early collaborators who provide refinement data.

**Why:** Sets correct expectations. Avoids transactional free-trial dynamics. Beta testers are partners, not customers yet.

### 14. Verdict Handoff: Contextual next step
**What it means:** Each Standard Council verdict triggers a specific next-step flow:
- **Greenlight:** "Your draft has foundation." Displays central question and revision map. Prompts: [Run Editor pass] or [Start new project].
- **Rewrite:** "The council identified a central question." Displays central question and revision map. Prompts: [Submit revised draft] (triggers Returning Writer Protocol).
- **Pass:** "The council found a foundational issue." Displays explanation. Prompts: [Return to Seed Council] or [Start new project].

**Why:** A verdict without a next step is a dead end. The developmental arc only works if the app guides the writer from Council to the next session. Rewrite verdict is also the RWP activation point: it populates the "previous central question" field the RWP reads. Without contextual handoff, that field never gets written and the RWP can't run.

### 15. Session Navigation: Read-only scroll back
**What it means:** Full session history is visible above the current step. User can scroll up to re-read any prior beat, voice output, or their own responses. Cannot edit prior responses or re-run beats. Forward-only for progression, full transcript for reference.

**Why:** The Contrarian's question in Beat 4 lands differently when you can re-read what the Champion defended in Beat 2. Denying scroll-back is friction with no payoff. Re-do capability (Option 3) would let writers optimize their answers instead of giving honest ones, undermining the interrogation. The session transcript is also the deliverable: writers reference it when starting their next draft, and the RWP reads it when evaluating revisions.

**Constraint:** Writer's own responses must be logged as part of the session record, not just the council's output. The RWP reads the full conversation, not half of it.

---

## The 15 Editorial Principles (Editor Mode)

**These are seed principles for beta, not universal voice law.** The 15 principles were extracted from Alex's essay editing sessions (9 sessions, one writer, one genre). They are the starting calibration set for the Essay/Long-form genre profile. They are NOT assumed to be universal rules for all writers.

**How personalization works:** Every writer starts with the same 15 seed principles. Their accept/reject decisions personalize the set over time:
- Principles accepted at high frequency get reinforced (flagged earlier, with higher confidence).
- Principles rejected at high frequency get demoted (flagged only at high confidence, or suppressed).
- Emergent principles (patterns the user creates through their own consistent decisions that weren't in the seed set) get surfaced for naming once the pattern is statistically clear.

**How Alex-specific voice rules avoid overriding another writer's voice:** Principles 7 (no em-dashes) and 8 (banned vocabulary) are the most Alex-specific. They reflect Alex's codified voice rules from his own writing and Spiral testing. For beta, ALL users start with these as seed rules. This is acceptable because: (a) em-dashes are a documented AI tell regardless of writer, (b) Tier 1 banned vocabulary ("delve", "tapestry", etc.) is generic AI slop no writer should produce, and (c) the accept/reject mechanism means a writer who WANTS em-dashes can reject those flags repeatedly and the Editor will learn to stop surfacing them. The signature adapts. The seed calibration is a starting point, not a permanent constraint. Post-beta, genre profiles can ship with different seed sets.

Grouped into three categories:

**Argument & Information Architecture:** (1) Don't stack statistics, (2) Mechanism leads, studies illustrate, (3) Compress via hinge, (4) Concessions advance argument, (5) Headers name what you show, not what you counter, (6) Trust the reader, (12) Fold minor citations into parentheticals, (14) Function determines form.

**Voice & Register:** (7) No em-dashes (hard rule, auto-flag), (8) Five-tier banned vocabulary (see Tier coverage note below), (9) Peer-to-peer register.

**P8 Tier coverage for beta:** Tiers 1, 2, and 5 have complete word lists (sourced from Core Voice document at `amplify-workshop/marketing/context/voice/core-voice.md`). Tiers 3 (performative directness) and 4 (therapist mode) have category names and a few examples each but are short lists (Tier 3: 5 phrases, Tier 4: 3 phrases). This is adequate for beta launch because: (a) Tiers 3-4 are the least common patterns in essay writing, (b) the existing examples cover the most egregious cases, and (c) the accept/reject mechanism means users who encounter uncaught Tier 3-4 patterns can reject the non-flagging implicitly through their editing behavior. Post-beta, expand Tiers 3-4 from user decision-trail data. Do not claim "complete five-tier coverage" in marketing or demo. Accurate claim: "Catches AI vocabulary patterns across five tiers, with Tiers 1, 2, and 5 fully covered."

**Editorial Discipline:** (10) Crystal Principle (meta-rule: accept structural catches, reject voice formalizations), (11) Don't tell after showing, (13) Cut paragraphs that read like due diligence, (15) If narrating what you demonstrated, delete the narration.

**The Crystal Principle (10) is the meta-filter.** Before surfacing any suggestion, the Editor evaluates: structural catch or voice formalization? Structural catches surface immediately. Voice formalizations are suppressed by default but logged to a separate table (suppression count shown on signature dashboard). User can toggle "register-leveling" mode to see voice-formalizing suggestions.

**Principles 7-8 bypass the Crystal filter. Principle 9 does not.** P7 (em-dashes) and P8 (banned vocabulary) are deterministic pre-LLM grep flags, always surfaced, zero tokens. P9 (register drift) is a CONTEXTUAL check that requires LLM judgment to compare the draft's register against the user's Phase 0 register baseline. It cannot operate as a deterministic pre-LLM pass. P9 goes through the LLM judgment pass alongside Principles 1-6 and 10-15, but is classified as voice_protection (not voice_formalization), so it surfaces by default rather than being suppressed by the Crystal filter. The distinction: P7-P8 bypass the filter entirely (pre-LLM). P9 goes through the filter but is classified favorably (LLM tags it as voice_protection, not voice_formalization).

**Crystal filter is generate-then-filter, not prompt-to-suppress.** The LLM generates ALL suggestions (structural + voice). Each is tagged by the LLM as structural_catch or voice_formalization. The classification step is probabilistic (it is an LLM judgment call, not a deterministic rule). The enforcement step AFTER classification is deterministic code: suppress anything tagged voice_formalization from display, log it to the suppressed table. This two-step design means: (a) the filter's behavior is auditable (every suppressed suggestion is stored with its classification), (b) misclassifications can be detected by reviewing suppressed suggestions, and (c) classification accuracy can be tested against golden examples. The spec should include 10-15 classification test cases (known structural catches and known voice formalizations) to validate the LLM's tagging accuracy before launch.

Full operational definitions with before/after examples are in `~/Downloads/ai-human-editor-build-brief-v0.2.md`.

---

## Prompt-Porting Validation (WRC v1.4 -> API)

The WRC v1.4 framework was designed for Claude Projects (persistent system prompt, conversation memory across turns). Porting it to per-call API interactions is a quality risk. The system prompt stays behind the interaction (IP protection), but each API call must reconstruct enough context for the voice to perform at Claude Projects quality.

**What must be validated before the Council modes ship:**

1. **Golden transcripts.** Record 3-5 sessions in Claude Projects using the v1.4 system prompt. These are the quality baseline. The API implementation must produce output of comparable depth, specificity, and character consistency. If the Contrarian's verb catch doesn't land via API, the port has failed.

2. **Prompt templates per voice/beat.** Each voice (Champion, Story Architect, Character Interrogator, Audience Proxy, Contrarian) needs a prompt template that includes: the voice's persona and mandate, the framework's rules (never rewrite, identification not declaration), the user's Phase 0 fingerprint, the project calibration, and the session transcript so far. The template is not the full 4,000-word system prompt for every call. It is the relevant subset for this voice at this point in the sequence.

3. **Structured outputs.** Each API response should return structured data (not just prose) so the app can: extract the central question, store the verdict, identify the Contrarian's key question, tag suggestions with principles. Define the output schema per voice/beat. Use Claude's structured output capabilities.

4. **Context assembly pattern.** Define how the app constructs each API call: system prompt (voice template + framework rules) + user messages (Phase 0 data + project calibration + session transcript so far + current user input). The context window budget per call should be estimated. A full Standard Council session with 5 voices and user responses accumulates significant context by Voice 5.

5. **Prompt caching.** The voice templates and framework rules are static per session. Use Anthropic's prompt caching to avoid re-processing the system prompt on every call. This reduces latency and cost for the multi-turn Council sessions.

6. **Regression fixtures.** For each voice, define 2-3 input/output pairs from the golden transcripts that serve as regression tests. If a prompt template change causes the Contrarian to miss a verb catch it previously caught, the fixture fails. Include in the spec's verification pipeline.

**When this runs:** Phase 3 (Council modes). The golden transcripts should be recorded manually in Claude Projects BEFORE the autopilot build begins. They are an input to the spec, not a build artifact.

---

## Architectural Constraints (Non-Negotiable)

These are inherited from the Writers Room Council's core rule and carry into the full app:

1. **Never rewrites.** The app never produces replacement prose. What it CAN do: flag a passage, name the principle violated, ask a diagnostic question ("Which data point is stronger?"), and describe the structural move available ("These two paragraphs make the same argument from different angles. There's a hinge sentence that does the work of both."). What it CANNOT do: generate the rewritten sentence, offer a "suggested revision," produce alternative wording, or show a "before/after" with AI-written "after" text. The user's voice does the rewriting. The boundary is: the app can name the problem and describe the shape of the fix, but never write the fix.
2. **Every accept/reject is a logged decision.** The decision trail is the proof of judgment-presence. No silent applications. No bulk accept-all without per-decision logging.
3. **Per-user persistence across sessions.** Without this, the Editor is a stylist. The compounding loop is the entire product.
4. **Operates primarily on argument and structure, not prose voice.** Voice belongs to the user. Argument architecture is what the app sharpens. Principles 7-9 (em-dashes, banned vocabulary, register) are the exceptions: they operate on voice/register but serve the same goal of protecting the user's authentic voice from AI drift.
5. **App controls sequence, user controls voice.** Framework constraints (Phase 0 first, voices in order, beats in sequence) are enforced by the UX. The user speaks freely within each step.
6. **Phase 0 fingerprint shared between Council and Editor.** Same input, different application. Council calibrates creative judgment; Editor compounds editorial judgment.
7. **"Characters not scripts" framing.** The five voices are persistent characters with consistent personalities, not pre-written question scripts. The system prompt defines the personas; the personas improvise the dialogue live, calibrated to each seed/draft. This framing must be reflected in the UI (voice labels, character consistency across sessions) and in the prompt templates (persona definitions, not question lists).
8. **Closing Handoff is non-negotiable.** Every Seed Council session must deliver a closing handoff that situates the writer in the developmental cycle. If Beat 5 is skipped due to time, the handoff attaches to Beat 4 instead. The writer always leaves knowing there are further stages. The app enforces this: session cannot end without the handoff being displayed.
9. **Two forms of council-grade unanswerability.** The Contrarian's final question succeeds in one of two forms: (a) a question that can only be answered by going to the page (requires writing to resolve), or (b) a question that can only be answered by saying aloud something the writer has been carrying without naming (requires honest articulation). Both are valid. The prompt templates must instruct the Contrarian to aim for one of these two forms, not a generic "hard question."
10. **Crystal filter has three classification tiers, not two.** LLM-generated suggestions are tagged as: structural_catch (surfaces), voice_formalization (suppressed), or voice_protection (surfaces). P9 register drift is voice_protection. This prevents P9 from being accidentally suppressed by the Crystal filter while maintaining the two-category UX presentation (structural catches + voice protection both surface; voice formalizations are suppressed).

---

## Autopilot Build Requirements (From Run 033 + Solution Docs)

These are mandatory spec patterns learned from 13 prior autopilot builds (especially Run 033: 15 agents, 116 files, 12 P0s at integration seams). Every pattern below prevents a specific failure mode that occurred in production swarm builds.

### Export Names Table (Prevents P0-1 from Run 033)
Run 033's #1 failure: 13 files broke because agents agreed on interfaces but not exact export names (`createClient` vs. `createBrowserClient`). The spec MUST include an exact export names table:

```
| File | Export | Consumers | Usage |
|------|--------|-----------|-------|
| lib/supabase/client.ts | createBrowserClient | all client components | const supabase = createBrowserClient() |
| lib/supabase/server.ts | createServerClient | all API routes, middleware | const supabase = createServerClient(cookies()) |
```

Every exported function, every consumer, exact names. Not "exports a client function" but "exports `createBrowserClient`."

### Cross-Boundary Wiring Section (Prevents P0-6, P0-7, P0-8 from Run 033)
Run 033 had three dead-wiring P0s: Service Worker never registered, email scheduling never called, rate limiting never wired. Functions existed but no code imported them. The spec MUST include:

```
| Function | Created By | Called By | Import Path | When In Flow |
|----------|-----------|-----------|-------------|--------------|
| computeSignature() | editor agent | signature-dashboard agent | lib/editor/signature.ts | After accept/reject logged |
| runSeedCouncil() | council agent | project-flow agent | lib/council/seed.ts | When user starts Seed mode |
```

Every function that crosses an agent ownership boundary must have explicit wiring instructions.

### Data Ownership Table (Prevents cross-module write conflicts)
Every database table must have exactly one writing module. From the inter-service contracts solution doc:

```
| Table | Writer | Reader(s) |
|-------|--------|-----------|
| decisions | editor module only | signature module, dashboard |
| sessions | council module only | RWP module, project view |
| fingerprints | phase0 module only | council, editor |
```

### Atomic Operations Prescriptions (Prevents P0-2, P0-4 from Run 033)
Run 033 had non-transactional session claiming and non-atomic upvote increments. Any multi-row operation in the WRC app gets a prescribed Supabase RPC function:

- Session claiming (updating project + session records atomically)
- Signature recomputation after accept/reject (updating decision + signature tables)
- Any operation that reads-then-writes to the same row under potential concurrency

### Schema Pre-Gate (Phase 2.0 pattern from Run 033)
Before any Editor or Council agents start building, a pre-gate agent must validate:
- All Zod schemas for LLM structured outputs (suggestion schema, verdict schema, beat response schema)
- Fixture tests pass against those schemas
- All TypeScript types match the Supabase database schema

This prevents downstream agents from building on incompatible type definitions. Run 033 proved this pattern eliminates 90%+ of type mismatch bugs.

**Important limitation:** The Schema Pre-Gate validates the SHAPE of LLM outputs (Zod compliance), not the QUALITY of LLM judgment. The Crystal filter's classification accuracy (is this really a structural_catch or a voice_formalization?) cannot be tested by Zod. Classification quality requires separate golden-example tests: 10-15 known suggestions with expected classifications, run against the actual prompt template + LLM. These classification tests belong in Phase 2's gate alongside the Zod pre-gate, not as a substitute for it.

### Mock Mode From Day 1 (Prevents API key dependency)
The app must work without an Anthropic API key in development:
- Every LLM call has a mock fallback that returns valid structured data
- Mock responses match the exact schema the real API would return
- One mock system, not per-phase mocks (Run 033 had two divergent mock systems, P0-12)

This lets all agents build and test without API keys, and provides a fallback if the API is down during the demo.

### Structured Outputs for All LLM Calls
Every API call to Claude must return structured data (not just prose), so the app can:
- Extract the central question from a Standard Council session
- Store the verdict as a typed field
- Identify the Contrarian's key question
- Tag Editor suggestions with principle IDs and Crystal filter classification
- Parse beat responses for display in the guided flow

Define Zod output schemas per voice/beat/mode in the Schema Pre-Gate.

### Timeouts and Abort Signals (Prevents P0-5 from Run 033)
Every Anthropic API call must include an AbortController with a 15-second timeout. On timeout, fall back to mock response and surface an error indicator in the UI. Vercel function timeout is 60 seconds; an unhandled API stall blocks the user for the full duration.

### "DO NOT" Scope Boundaries
The spec must explicitly list what is NOT built. From the brainstorm's deferred items plus autopilot best practices:
- DO NOT build multi-genre profile management
- DO NOT build email/business communication profile
- DO NOT build subscription/payment mechanics (beta is free)
- DO NOT build mobile-specific layouts (responsive is sufficient)
- DO NOT build collaborative/multi-user features
- DO NOT build voice generation or rewriting features
- DO NOT build full Square/Stripe webhooks
- DO NOT build the Apprenticeship Simulator integration

### Spec Format (Follow Ethics Toolkit Pattern)
The plan/spec must follow the proven 13-section format from the ethics toolkit spec:
1. Global Constraints & Guardrails
2. Identity & Auth Architecture
3. Authoritative Database Schema (SQL + RLS)
4. Core Workflow Contracts (per mode, with Zod schemas + fixtures)
5. Realtime/Streaming Contracts (if applicable)
6. Locked Decisions (table format)
7. External Integration Contracts (Anthropic API)
8. Prompt Templates & Context Assembly
9. Rate Limiting
10. Autopilot Phasing Strategy (with gates)
11. Swarm Execution Guardrails (file ownership, bash rules)
12. Environment Variables (with fallback mode)
13. Items Deferred to Post-Launch

Plus the Swarm Agent Assignment section with file ownership matrix.

### Spec Convergence Loop (Before Autopilot Launch)
The spec must go through the proven convergence process:
1. Claude Code authors spec
2. Codex reviews (catches cross-section contradictions)
3. Claude Code implements fixes
4. Codex reviews again (minimum 2 rounds)
5. Human structural verification (P0s are always cross-section contradictions AI tools miss)
6. Convergence criterion: Codex clean AND human finds zero P0s
7. Then autopilot launches

### Verification Pipeline (Post-Assembly)
After each phase's swarm merge, run the full pipeline:
1. **Ownership gate** - `git diff --name-only` against assignment
2. **Spec contract check** - grep for exact export names, validate schemas
3. **Cross-boundary wiring check** (NEW, from Run 033 lessons) - grep for all exported functions, verify each has at least one consumer
4. **Smoke test** - start app, hit every route, verify status codes
5. **Test suite** - run all tests
6. **Assembly-fix** - 1 retry per failure type, then escalate

---

## Build Phases (Autopilot Spec Structure)

### Phase 1: Foundation (Days 1-3)
- Auth (Supabase magic link)
- Database schema (users, projects, fingerprints, sessions, decisions)
- Phase 0 fingerprint interview (user-level + project-level)
- Project model with first-class verdict/central-question fields
- App shell with mode selector dashboard

**Gate:** User can sign up via magic link, complete Phase 0 interview, create a project.

### Phase 2: Editor (Days 4-12)
- 15 principles loaded as operational definitions
- Crystal Principle filter (evaluate each suggestion: structural catch vs. voice formalization)
- Paste text input -> document rendering
- Inline annotation system (highlights with popover: principle, flag, question)
- Accept/reject UI with decision logging
- Decision trail storage (principle invoked, suggestion, decision, section, timestamp, genre tag)
- Signature learning (weighted profile of principle invocations and decision patterns)
- Signature dashboard (readable from session one)

**Gate:** Paste a document, receive inline annotations filtered through Crystal Principle, accept/reject suggestions, see signature dashboard with logged decisions.

### Phase 3: Council Modes (Days 13-22)
- Seed Council Mode (coaxing prompt, micro-interview, 5-beat interrogative sequence)
- Standard Council (5 voices in order: Champion, Story Architect, Character Interrogator, Audience Proxy, Contrarian; verdict system with contextual handoff)
- Returning Writer Protocol (reads previous central question, verdict, and revision map from project record; evaluates revision)
- All modes use guided flow (app advances beats/voices, user responds conversationally)
- Streaming LLM responses for all voice outputs (architectural requirement, not polish. The "characters not scripts" framing requires voices that feel alive)
- Prompt templates per voice/beat constructed from v1.4 framework rules + user fingerprint + session context
- Session results stored on project record as structured data (not conversation blobs)
- Prompt-porting quality validation: run golden transcript comparisons against API output. Contrarian verb catch must land. Champion must identify, not declare.

**Gate:** Run each mode end-to-end. Seed produces named intent + unanswerable question. Standard produces verdict with central question, revision map, and contextual handoff. RWP reads previous verdict and evaluates new draft. Golden transcript regression fixtures pass (verb catch lands, identification not declaration holds). Scoring Floor activates correctly when intake is too weak.

### Phase 4: Polish + Demo Prep (Days 23-28)
- Signature dashboard polish (compounding indicators, Crystal filter suppression count)
- Alex's own data pre-loaded (essay editing sessions for demo)
- Demo flow rehearsal path (Seed Council live + Editor pre-loaded)
- Edge cases and error handling
- UX polish (loading states, transitions)
- **May 25 readiness gate** (5 days before workshop, not May 20. May 20 was from the marketing execution plan which assumed a shorter build. With 4 phases and prompt-porting validation, May 25 is the realistic gate. If not ready by May 25, switch marketing to "early-access invite" language per the execution plan's fallback.)

**Gate:** Full app functional. Alex's demo data loaded. All four modes operational. Signature dashboard readable with real data. Demo rehearsal completed at least once end-to-end.

---

## Source Artifacts

| Artifact | Location |
|----------|----------|
| Editor strategic handoff | `~/Downloads/ai-human-editor-claude-code-handoff.md` |
| Editor build brief v0.2 (15 principles) | `~/Downloads/ai-human-editor-build-brief-v0.2.md` |
| WRC v1.4 framework handoff | `amplify-workshop/workshops/2026-04-25-amplify/writers-room-council-handoff.md` |
| WRC live validation solution doc | `amplify-workshop/playbook/docs/solutions/2026-04-25-writers-room-council-live-validation.md` |
| Core Voice document (all 5 tiers) | `amplify-workshop/marketing/context/voice/core-voice.md` |
| Vitaly IP decision | `amplify-workshop/strategy/meetings/2026-04-26-vitaly-ip-decision.md` |
| May 30 execution plan | `amplify-workshop/marketing/docs/plans/2026-05-01-feat-may30-workshop-30-day-execution-plan.md` |
| Genre expansion handoff (parked) | `~/Downloads/HANDOFF__WRC_Genre_Expansion__Speeches_Presentations.md` |
| Ethics toolkit spec (autopilot precedent) | `sandbox/docs/plans/2026-04-30-ethics-toolkit-platform-spec.md` |
| Spec convergence loop | `sandbox/docs/solutions/2026-04-30-spec-convergence-loop.md` |
| Autopilot swarm orchestration | `sandbox/docs/solutions/2026-04-09-autopilot-swarm-orchestration.md` |

---

## Open Questions

*None remaining. All resolved during review refinement.*

---

## Resolved Questions

1. **UX paradigm?** Hybrid: app-controlled sequence, conversational input within steps.
2. **Auth model?** Magic link email via Supabase Auth. Beta cohort whitelisted.
3. **LLM backend?** Opus 4.6 for all modes. No tiering.
4. **Editor UI?** Inline annotations in the document. Not a side panel, not sequential.
5. **Document input?** Paste text. No file upload, no rich text editor.
6. **Phase 0 scope?** Layered: user-level fingerprint + project-level calibration.
7. **RWP connection?** Project-based containers. Verdict and central question as first-class fields.
8. **Signature visibility?** Dedicated "My Signature" view. Must be readable from session one.
9. **Tech stack?** Next.js 15 + Supabase + Anthropic SDK + Vercel + Tailwind.
10. **Demo flow?** Seed Council live with volunteer + Editor on pre-loaded Alex essay.
11. **Build approach?** Editor-first, 4 sequential phases with gates, all within one autopilot loop.
12. **Genre profile?** Single: Essay/Long-form Editing. No email/business profile at launch.
13. **Access model?** Beta cohort (14-day free), not free trial. Paid tier post-beta.
14. **What does "accept" do?** Logged + editable in place. Accept clears the annotation, cursor lands in the flagged text, user rewrites themselves. Decision logged as accepted. If user accepts but doesn't change text, logged as accepted-no-edit (honest signal, not enforced friction). Reject clears annotation, decision logged.
15. **Principles 7-9 and Crystal filter?** P7 (em-dashes) and P8 (banned vocab) bypass the Crystal filter entirely as deterministic pre-LLM grep flags. P9 (register drift) goes through the LLM judgment pass (it requires contextual comparison, not grep) but is classified as voice_protection, so it surfaces by default. Three-tier system: P7-P8 = pre-LLM bypass, P9 = LLM-classified but surfaces, P1-6/10-15 = LLM-classified with Crystal filter applied.
16. **Phase 0 interview questions?** Three-layer design. Layer 1 (user-level, runs once): 4 Council-calibration questions (genre, thematic obsessions, structural failure patterns, voice self-report) + 2 Editor-calibration questions (worst habit, register/reader) + writing sample + before/after passage (required). Layer 2 (project-level, per project): what you're working on, intent, what you're protecting. Layer 3 (Seed micro-interview, per Seed session): coaxing prompt + seed-specific questions. Scoring Floor triggers if intake lacks enough texture for voices to generate genuine questions.
17. **Crystal filter implementation?** Generate then filter. LLM generates ALL suggestions (structural + voice). LLM tags each as structural_catch or voice_formalization (probabilistic classification). Code enforcement after classification is deterministic: suppress voice_formalization from UI, log to separate table. Suppression count displayed on signature dashboard. Classification accuracy validated against 10-15 test cases before launch.
18. **Signature dashboard empty state?** Phase 0 echo + prompt. Dashboard shows user's stated worst habit, register, and before/after edit preview (pulled live from stored fingerprint fields). Below: "0 documents edited, 0 decisions logged. Run your first Editor pass to start building your editorial signature." Not empty, not a feature tour. The product is already about them.
19. **Verdict handoff?** Contextual next step. Greenlight -> Editor pass. Rewrite -> submit revised draft (triggers RWP). Pass -> return to Seed Council or new project. Verdict also writes central question to project record (required for RWP).
20. **Session navigation?** Read-only scroll back. Full transcript visible (council output + writer responses). No re-do, no editing prior responses. Forward-only progression. Session transcript is the deliverable and the RWP's input.

### Deferred to Plan (Implementation Details)
- **Accepted-no-edit trigger timing:** When exactly does the system log an accept without text change? (On navigate away, on next annotation click, on document close.) Implementation detail.
- **"Section" field definition in decision trail:** What constitutes a section in plain pasted text? (Paragraph, character offset range, heading detection.) Data model detail.
- **Mid-session error UX:** What happens if an Anthropic API call fails or times out mid-Council session (e.g., between Voice 3 and Voice 4)? Options: retry with backoff, show error and let user retry the current step, fall back to mock response. The session transcript up to the failure point must be preserved.
- **Concurrent session handling:** What happens if a user has the app open in two tabs? The decision trail, session transcript, and signature could be corrupted by concurrent writes. Options: optimistic locking with draft_version_id, last-write-wins, or block concurrent sessions.
- **Schema fallback on malformed LLM output:** If the LLM returns JSON that doesn't match the Zod schema (e.g., missing classification tag on a suggestion), the app must fail gracefully. Options: return the suggestion without classification (surface it with an "unclassified" tag), retry the call, or suppress it. Define per-mode behavior.
- **Serverless timeout strategy:** Vercel function timeouts (10-60s depending on tier) may be exceeded by sequential multi-voice Council calls. The streaming approach (Vercel AI SDK) keeps the connection alive during a single call, but the app needs to handle the gap between calls (user reading + typing). Each voice is a separate API call, not one long-running function. Confirm this architecture handles timeout constraints.
- **Prompt caching TTL management:** Anthropic prompt caching has ~5-minute TTL. If a user takes longer than 5 minutes between beats (reading, thinking, writing), the cache drops and full context is rebilled. Acceptable for beta (small cohort, cost is manageable), but note for cost optimization post-beta.

---

## Feed-Forward

- **Hardest decision:** Opus for all modes vs. tiered models. Chose Opus everywhere because the Contrarian's verb catch and the Editor's Crystal Principle filtering are the product's signature moments, and model quality at those moments is what separates this from "just chatting with Claude." Cost is manageable for a beta cohort.
- **Rejected alternatives:** Chat-based interaction (would require enforcement logic on top of framework constraints), side-panel Editor (turns it into a grammar checker), auto-detect for RWP (guess with failure modes you don't want to debug before May 30), parallel build tracks (integration seams are where swarm builds fail, proven in Run 033), prompt-to-suppress for Crystal filter (unreliable, non-auditable, wrong place to trust the model).
- **Least confident:** Two risks tied for top concern. (1) Whether the inline annotation system with editable-on-accept can be built with sufficient quality in the autopilot timeframe. This is a rich interactive UI component (highlights, popovers, accept clears annotation and enables in-place editing, text export) that needs to feel satisfying, not just functional. If this underperforms, the Editor's thesis doesn't land. (2) Whether the prompt-porting from Claude Projects to API calls preserves the Contrarian's verb catch quality. Run 033 proved that integration seams are where swarm builds fail. The WRC app has an additional integration seam that Run 033 didn't: the seam between a designed framework (v1.4 system prompt) and per-call API reconstruction of that framework. Both risks should be verified first in their respective phases.
- **Key architectural split discovered in review:** The Editor has two processing passes. (1) Pre-LLM deterministic pass: grep for em-dashes, match against banned vocabulary lists. Always surfaced, bypasses Crystal filter, costs zero tokens. (2) LLM judgment pass: generates all suggestions (structural + voice), each tagged (probabilistic classification), Crystal filter code suppresses voice formalizations from display but logs them. This split is clean and should be spec'd explicitly.
- **Prompt-porting risk added post-Codex review:** The v1.4 system prompt was designed for Claude Projects. API porting requires golden transcripts, prompt templates, structured outputs, context assembly patterns, and regression fixtures. Golden transcripts must be recorded BEFORE the autopilot build begins.

---

## Review Fixes Applied (Post-Codex)

**Date:** 2026-05-02 (same-day revision after external Codex review)

### What Changed

| # | Issue | Severity | Fix Applied |
|---|-------|----------|-------------|
| 1 | Phase 0 only served the Editor, not the Council | P0 | Redesigned as 3-layer system: 4 Council-calibration fields + 2 Editor-calibration fields + shared inputs at user level. Defined how Phase 0, Seed micro-interview, and project calibration differ. Added Scoring Floor behavior. |
| 2 | Project data model too thin (verdict + central question only) | P0 | Expanded to full session records: Seed outputs (named intent, unanswerable question), Standard Council (verdict, Pass subtype, explanation, central question, revision map, draft version ID), RWP (previous session reference, new verdict), Editor (all suggestions including suppressed, per-suggestion decisions, signature snapshot). Added handoff state field. |
| 3 | 15 principles presented as universal voice law | P1 | Clarified as seed principles for beta. Added personalization mechanism (accept/reject adapts weights, emergent principles surface). Explained how Alex-specific rules (P7, P8) avoid overriding other writers' voices via the accept/reject adaptation loop. |
| 4 | No validation plan for WRC v1.4 -> API prompt porting | P0 | Added full Prompt-Porting Validation section: golden transcripts, prompt templates, structured outputs, context assembly, prompt caching, regression fixtures. Golden transcripts must be recorded before autopilot build. |
| 5 | "Never rewrites" boundary was vague | P1 | Defined allowed suggestions (flag, name principle, ask question, describe structural move shape) vs. forbidden (replacement prose, suggested revisions, AI-written "after" text). |
| 6 | Crystal filter language claimed deterministic classification | P1 | Corrected: classification is probabilistic (LLM judgment). Enforcement after classification is deterministic (code). Added requirement for 10-15 classification test cases. |
| 7 | P8 claimed five-tier coverage but Tiers 3-4 are short lists | P1 | Documented actual coverage. Tiers 1, 2, 5 complete. Tiers 3-4 have category names + few examples. Adequate for beta. Do not claim "complete coverage" in marketing. |
| 8 | May 20 readiness gate unrealistic; Phase 3 lacked quality validation | P1 | Moved readiness gate to May 25. Extended Phase 3 to days 13-22 to include prompt-porting validation and golden transcript regression. Added Scoring Floor gate check. Phase 4 compressed to days 23-28 (demo prep focus). |

### Risks Remaining Before Planning

1. **Golden transcripts don't exist yet.** They must be recorded manually in Claude Projects before the autopilot build begins. This is a pre-build dependency, not a build artifact. If Alex hasn't run 3-5 sessions in Claude Projects by the time planning starts, this becomes a blocker.

2. **Phase 0 is now 8 inputs.** That's a lot of onboarding friction for a workshop attendee. The plan phase should consider whether some fields can be optional or progressive (filled in across first 2-3 sessions rather than all at once).

3. **Phase 3 scope grew.** Adding prompt-porting validation, golden transcript regression, and Scoring Floor testing to Phase 3 (now days 13-22) is significant. The plan phase should pressure-test whether this fits in 10 days with swarm parallelism.

4. **Crystal filter classification accuracy is unvalidated.** The 10-15 test cases are specified but don't exist yet. They need to be authored (likely from the build brief's before/after examples) and included in the spec.

5. **28-day timeline is tighter.** The readiness gate moved from May 20 to May 25, which gives only 3 days of buffer before May 28 (the last business day before the workshop). If Phase 3 prompt-porting validation reveals quality issues, the fix window is narrow.

### Autopilot Best Practices Pass (Post-Solution-Doc Research)

Applied institutional knowledge from 13 prior autopilot builds (Run 033 primary reference). Added new section "Autopilot Build Requirements" covering:

| Pattern Added | Prevents | Source |
|---------------|----------|--------|
| Export Names Table | Import name mismatches (P0-1, 13 files broken in Run 033) | ethics-toolkit-platform-build solution doc |
| Cross-Boundary Wiring Section | Dead wiring (P0-6/7/8, functions exist but never called) | ethics-toolkit-platform-build solution doc |
| Data Ownership Table | Multi-writer table conflicts | chain-reaction-inter-service-contracts solution doc |
| Atomic Operations Prescriptions | Non-transactional multi-row ops (P0-2/4) | ethics-toolkit-platform-build solution doc |
| Schema Pre-Gate (Phase 2.0) | Type mismatches across agents | autopilot-swarm-orchestration solution doc |
| Mock Mode From Day 1 | API key dependency + divergent mock systems (P0-12) | ethics-toolkit-platform-build solution doc |
| Structured Outputs | Inability to parse LLM responses programmatically | New requirement for WRC (not needed in ethics toolkit) |
| Timeouts + Abort Signals | API stalls blocking users (P0-5) | ethics-toolkit-platform-build solution doc |
| "DO NOT" Scope Boundaries | Scope creep during swarm | ethics-toolkit spec pattern |
| 13-Section Spec Format | Spec completeness | ethics-toolkit spec structure |
| Spec Convergence Loop | Cross-section contradictions | spec-convergence-loop solution doc |
| Verification Pipeline + Wiring Check | Post-assembly integration failures | autopilot-swarm-orchestration + Run 033 review |

**New risk surfaced:** The WRC app has an integration seam that Run 033 didn't have: the seam between a designed framework (v1.4 system prompt for Claude Projects) and per-call API reconstruction. This is a novel failure mode with no prior solution doc. The prompt-porting validation section addresses it, but it's unproven at this complexity.

### NotebookLM Review Pass (Post-Source-Material Cross-Reference)

NotebookLM cross-referenced the brainstorm against 10 source documents. Findings applied:

| Finding | Status | Action |
|---------|--------|--------|
| P9 (register drift) cannot be a pre-LLM grep pass | **Fixed** | Reclassified P9 as LLM-judged with voice_protection tag. Added three-tier classification system. |
| Missing "characters not scripts" framing | **Fixed** | Added as architectural constraint #7 |
| Missing Closing Handoff rule | **Fixed** | Added as architectural constraint #8 |
| Two forms of unanswerability not defined | **Fixed** | Added as architectural constraint #9 with both forms specified |
| Mid-session error UX undefined | **Deferred to plan** | Added to plan-level gaps |
| Concurrent session handling undefined | **Deferred to plan** | Added to plan-level gaps |
| Schema fallback on malformed LLM output | **Deferred to plan** | Added to plan-level gaps |
| Serverless timeout risk | **Deferred to plan** | Each voice is a separate API call, not one long function. Noted for verification. |
| Prompt caching TTL (5-min) | **Deferred to plan** | Acceptable for beta. Noted for post-beta cost optimization. |
| Schema Pre-Gate can't validate LLM judgment | **Fixed** | Added classification test requirement alongside Zod pre-gate |

**NotebookLM findings rejected (hallucinations or misunderstandings):**
- "Opus 4.7" and "GPT-5.4" model references: hallucinated. These models don't exist.
- "Model Selection Guide" recommending different models for classification: hallucinated source.
- "Unanswerability" redefined as content moderation ("not a story" / "malicious"): misunderstands the WRC framework. Unanswerability is about interrogation depth, not content filtering.
- "Scoring Floor" redefined as "minimum viable narrative threshold" rejecting drafts: misunderstands the framework. Scoring Floor gates intake quality, not draft quality.
- Blueprint spec's simplified data contracts: less complete than the brainstorm's existing data model.
- Blueprint spec reorders build phases: contradicts the decided Editor-first approach.
