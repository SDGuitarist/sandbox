Review the plan as an external senior engineer.

Focus on:

1. **Quality Gate** -- Does it answer all four:
   - What exactly is changing?
   - What must not change?
   - How will we know it worked?
   - What is the most likely way this plan is wrong?
2. **EARS Acceptance Tests** -- Are they present, complete, and directly translatable to test cases? Do they include verification commands?
3. **Feed-Forward** -- Is the "least confident" item a real risk? Is "hardest decision" justified? Are rejected alternatives actually worse?
4. **Hidden assumptions** -- What does the plan assume that isn't proven?
5. **Missing implementation details** -- Anything that will force "figure it out while coding"?
6. **Scope creep** -- Anything beyond what the brainstorm specified?
7. **Rollout and migration risks** -- Data loss, downtime, backwards compatibility
8. **Testing gaps** -- Untested paths, missing edge cases, integration points
9. **Observability and operational gaps** -- Can you tell if this is working in production?
10. **Security or privacy concerns** -- OWASP top 10, auth, input validation
11. **Simpler alternatives or scope cuts** -- Could this be done with less complexity?

Return your answer in Markdown with exactly these sections:

## Blockers
Issues that must be resolved before implementation starts.

## Concerns
Risks or weaknesses that should be addressed but aren't showstoppers.

## Suggestions
Improvements that would make the plan stronger.

## Open Questions
Things the plan doesn't answer that someone should decide.

Keep the review concrete and opinionated. Prefer actionable criticism over praise.
If the plan is strong, say so briefly, but still try to find edge cases and missing details.

At the end, write a `## Claude Code Fix Prompt` section -- a copy-paste-ready prompt that tells Claude Code exactly what to fix in the plan, referencing specific sections and line numbers where possible.
