# Deepening Corrections Applied — Run 063

**Date:** 2026-06-02
**Agents:** 4 (flask-sqlite-research, sortablejs-research, security-sentinel, architecture-strategist)

## Changes Applied

### From Flask+SQLite Research
1. **`autocommit=True` replaces `isolation_level=None`** — Python 3.12+ recommended approach. Same behavior, future-proof.
2. **Added `PRAGMA synchronous=NORMAL`** — safe with WAL mode, faster than default FULL. Applied to both get_db() and init_db().

### From Security Review
3. **`SESSION_COOKIE_SECURE = True`** added to app config — prevents session cookie over HTTP.
4. **Timing attack mitigation** prescribed for `authenticate()` — always call check_password_hash even when user not found (dummy hash pattern).
5. **`session.clear()` before login** — drops pre-auth session data.

### From Architecture Review
6. **3 missing cross-boundary wiring entries** added:
   - scenes routes -> location_models.get_locations (for location dropdown)
   - schedule routes -> scene_models.get_scenes + location_models.get_locations (for form dropdowns)
   - callsheets routes -> schedule_models.get_shoot_dates (for generate form)
7. **FTS5 entity_type and entity_id marked UNINDEXED** — prevents false positive search results matching metadata columns.
8. **Transaction contract gaps filled** — index_entity and remove_entity annotated as "does NOT commit". Compound write guidance added for scenes routes (update_scene + add_cast + index_entity in single transaction).

### From SortableJS Research
9. **Accessibility move up/down buttons** added to SortableJS contract table — WCAG 2.5.7 compliance (SortableJS has no keyboard support).

## Not Applied (deferred or out of scope)
- Agent rebalancing (departments/search underloaded): Keeping as-is for clean ownership boundaries. Merging would create mixed-concern agents.
- DOOD 0-shoot-days empty state: Template guidance only, not a spec correction. Agents should handle empty states per Coordinated Behaviors table.
