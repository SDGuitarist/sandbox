# NotebookLM Review Handoff: Writers Room Council App

**Date:** 2026-05-02
**Purpose:** Cross-reference the WRC app brainstorm against source materials, Opus 4.6 agent orchestration best practices, and Anthropic API patterns. Surface data accuracy issues, unstated assumptions, and claims without evidence before the spec is written.
**Process stage:** Brainstorm complete, Codex review applied, autopilot best practices applied. This is the NotebookLM pass before planning.

---

## WHAT TO LOAD INTO NOTEBOOKLM

Upload these documents as sources:

### Primary Review Target
1. **The brainstorm document** - `sandbox/docs/brainstorms/2026-05-02-writers-room-council-app-brainstorm.md`

### WRC Framework Source Materials (verify brainstorm accuracy against these)
2. **WRC v1.4 framework handoff** - `amplify-workshop/workshops/2026-04-25-amplify/writers-room-council-handoff.md` (the canonical framework description: 5 voices, 3 modes, developmental arc, Seed Council Mode design)
3. **Editor build brief v0.2** - `~/Downloads/ai-human-editor-build-brief-v0.2.md` (15 editorial principles with operational definitions, before/after examples, compounding model)
4. **Editor strategic handoff** - `~/Downloads/ai-human-editor-claude-code-handoff.md` (strategic decisions, build-time recommendations, scope)
5. **WRC live validation solution doc** - `amplify-workshop/playbook/docs/solutions/2026-04-25-writers-room-council-live-validation.md` (April 25 workshop proof: verb catch, group participation, what broke)
6. **Core Voice document** - `amplify-workshop/marketing/context/voice/core-voice.md` (all 5 tiers of banned vocabulary, voice DNA, hard language rules)

### Autopilot Build Precedent (verify build approach against these)
7. **Ethics toolkit platform spec** - `sandbox/docs/plans/2026-04-30-ethics-toolkit-platform-spec.md` (the spec format the WRC app should follow: 13 sections, YAML frontmatter, phasing with gates, swarm agent assignment)
8. **Ethics toolkit platform build solution doc** - `sandbox/docs/solutions/2026-04-30-ethics-toolkit-platform-build.md` (Run 033 results: 15 agents, 116 files, 12 P0s at integration seams, all failure modes documented)
9. **Spec convergence loop solution doc** - `sandbox/docs/solutions/2026-04-30-spec-convergence-loop.md` (the multi-tool spec hardening process: Claude Code + Codex + NotebookLM + human verification)

### Anthropic API / Opus 4.6 Best Practices (verify LLM integration assumptions)
10. **Any Anthropic API documentation you have** on: structured outputs, prompt caching, streaming, tool use, system prompts, and Claude Opus 4.6 capabilities and limitations
11. **Any agent orchestration documentation** on: multi-turn conversations via API, context window management, model behavior differences between Claude Projects and API calls

---

## WHAT TO REVIEW

### Category 1: Framework Accuracy

Cross-reference the brainstorm's descriptions of the WRC framework against the source materials. Flag any place where the brainstorm:

1. **Misrepresents the v1.4 framework.** Does the brainstorm's description of Seed Council Mode match the 5-beat sequence in the WRC handoff? Does the Standard Council description match the 5-voice sequence? Does the Returning Writer Protocol match? Check every framework claim against the source.

2. **Misrepresents the 15 editorial principles.** Does the brainstorm's description of the principles match the build brief v0.2? Are any principles missing, misnumbered, or described with the wrong trigger/flag/question? Does the Crystal Principle description match the source?

3. **Misrepresents the voice/register rules.** Does the brainstorm's Tier coverage claim match the Core Voice document? Are the banned vocabulary lists accurate? Does the em-dash rule match?

4. **Misrepresents the live validation results.** Does the brainstorm's account of the April 25 workshop match the solution doc? Did the verb catch actually work as described? Did group participation actually emerge?

5. **Omits critical framework rules.** Are there rules in the v1.4 handoff that the brainstorm should include but doesn't? For example: the Scoring Floor, the "characters not scripts" framing, the Closing Handoff requirement, the two forms of council-grade unanswerability.

### Category 2: Build Approach Accuracy

Cross-reference the brainstorm's autopilot build requirements against the Run 033 precedent:

6. **Does the brainstorm correctly apply Run 033 lessons?** The brainstorm claims specific P0s from Run 033 and prescribes prevention patterns. Verify each claim against the ethics toolkit build solution doc. Did P0-1 really involve 13 files with import mismatches? Did P0-6/7/8 really involve dead wiring? Are the prevention patterns correctly derived?

7. **Does the 4-phase structure make sense for this app's complexity?** Run 033 had 15 agents across 4 phases for 5 tools + realtime + payments. The WRC app has 4 modes + Editor persistence + signature learning + inline annotations + prompt porting. Compare complexity profiles. Is 4 phases enough? Are the day allocations realistic?

8. **Does the spec format prescription match what actually worked?** The brainstorm prescribes the 13-section format from the ethics toolkit spec. Verify that the 13 sections listed actually match what the spec contained.

### Category 3: Anthropic API / Opus 4.6 Assumptions

The brainstorm makes several assumptions about Claude Opus 4.6 behavior via API. Cross-reference against current documentation:

9. **Prompt caching.** The brainstorm assumes voice templates and framework rules can be cached via Anthropic's prompt caching. Is this feature available for Opus 4.6? What are the constraints (minimum token count, cache duration, cost implications)?

10. **Structured outputs.** The brainstorm assumes every API call can return structured data (Zod schemas for verdicts, suggestions, beat responses). What are the current capabilities for structured output with Claude? Are there limitations on output schema complexity?

11. **Streaming.** The brainstorm requires streaming LLM responses for Council voices ("characters not scripts"). How does streaming interact with structured outputs? Can you stream AND get structured data?

12. **Context window management.** A full Standard Council session accumulates context across 5 voices + user responses. The brainstorm mentions estimating context window budget per call. What is the actual context window for Opus 4.6? How much context can realistically be passed per call (system prompt + fingerprint + project calibration + session transcript + user input)?

13. **Quality parity between Claude Projects and API.** The brainstorm flags prompt-porting as a risk. Are there documented differences in behavior between Claude Projects (persistent system prompt) and per-call API usage? Does the model behave differently with a persistent context vs. reconstructed context?

14. **Cost estimation.** The brainstorm estimates ~$0.50-1.00 per full council session with Opus. Is this realistic given current Opus 4.6 pricing? A full Standard Council session involves 10+ API calls (5 voices + user responses + structured output parsing). Estimate actual cost.

### Category 4: Cross-Section Consistency

This is the highest-value check for NotebookLM. Look for claims in one section of the brainstorm that contradict claims in another section:

15. **Phase 0 serves both Council and Editor.** The Phase 0 section (Decision 6) describes 8 inputs across 3 layers. The Editor section describes the Crystal Principle filter using "Phase 0 register baseline." The Council section describes voices calibrated to fingerprint data. Do all three sections reference the same data fields? Are there fields promised in one section that don't exist in another?

16. **Project data model completeness.** Decision 7 lists specific per-session record fields. The verdict handoff (Decision 14) references central question, revision map, and verdict explanation. The RWP description says it reads "previous central question and verdict from project record." Do all three descriptions reference the same fields? Is anything referenced that isn't in the data model?

17. **Crystal filter classification + Principles 7-9 bypass.** The Crystal filter section says the LLM tags suggestions as structural_catch or voice_formalization. Principles 7-9 bypass the filter because they're pre-LLM grep passes. But Principle 9 (register drift) is described as both "pre-LLM" and "contextual" (bypasses only when register matches). Is Principle 9 actually pre-LLM (deterministic) or does it require LLM judgment? If it requires judgment, it can't bypass the filter the same way P7 and P8 do.

18. **"Never rewrites" constraint consistency.** The architectural constraint says the app "can name the problem and describe the shape of the fix." The Editor's 15 principles include specific flag text like "Two or more data points stacked here. Stacking creates a 'stats barrage' that works against any single point landing." Is describing a "stats barrage" naming the problem, or is it getting close to telling the user what to write? Where exactly is the line between "describing the shape of the fix" and "suggesting what to write"?

19. **Build phase timeline vs. scope.** Phase 2 (Editor, days 4-12) includes 9 major deliverables in 9 days. Phase 3 (Council, days 13-22) includes 3 modes + prompt porting validation + golden transcript regression in 10 days. Phase 4 (Polish, days 23-28) includes demo prep + Alex's data + edge cases in 6 days. Are these allocations consistent with the complexity described in each section?

### Category 5: Missing Information

20. **What does the brainstorm assume that it doesn't state?** For example: Does it assume Vercel function timeouts are 60 seconds? Does it assume Supabase RLS works a certain way? Does it assume Opus 4.6 has a specific context window size? List every unstated assumption you can find.

21. **What questions should the spec author ask that the brainstorm doesn't answer?** For example: How does the app handle concurrent sessions (two tabs open)? What happens if the LLM returns malformed structured output? What's the error UX when an API call fails mid-Council-session?

---

## OUTPUT FORMAT

```
## NotebookLM Findings

### Data Accuracy Issues
- [finding with source reference]

### Cross-Section Contradictions
- [finding referencing both sections]

### Unstated Assumptions
- [assumption with potential impact]

### Missing Information
- [gap that the spec author needs to fill]

### API / Opus 4.6 Concerns
- [finding with documentation reference]

### Build Approach Concerns
- [finding with Run 033 reference]
```

Prioritize cross-section contradictions and data accuracy issues. These are the P0s that become integration failures in the swarm build.
