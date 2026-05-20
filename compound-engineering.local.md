# Review Context -- Sandbox (Client Music Planner, Run 048)

## Risk Chain

**Brainstorm risk:** "Token-based portal access is novel territory. The @require_portal_token decorator is the critical security boundary."

**Plan mitigation:** Prescriptive decorator code blocks in spec. Cross-Boundary Wiring section with exact usage patterns for g.portal_event. Coordinated Behaviors table for all 20 agents.

**Work risk (from Feed-Forward):** "Drag-and-drop reorder persistence (SortableJS -> /api/playlist/reorder -> batch UPDATE). Three things must align across 3 agents."

**Review resolution:** 5 agents found 4 P1, ~14 P2, ~16 P3. All P1s fixed. Flow-trace reviewer found the only P1 (CSS class mismatch) that 4 other reviewers missed. portal_playlist was the only agent that needed full rewrite (23 contract failures).

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| client-music-planner/app/portal_playlist/routes.py | Full rewrite in assembly fix (original had 13 contract failures) | g.portal_event usage, db.commit() |
| client-music-planner/app/repertoire_import/routes.py | Assembly fix (5 failures) + P1 fix (exception leakage) | CSV parsing, bulk_create_songs call |
| client-music-planner/app/api_playlist/routes.py | Reorder endpoint -- validates parallel arrays | Length check, set equality |
| client-music-planner/app/static/js/playlist.js | SortableJS + move buttons + error recovery | CSS class selectors match template |
| client-music-planner/app/templates/portal_playlist/playlist.html | DnD template with data-item-id, move buttons | data attributes, block name |

## Plan Reference

`docs/plans/client-music-planner-plan.md`
