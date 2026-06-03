---
status: complete
priority: p2
issue_id: "065"
tags: [code-review, performance, export, n-plus-1, run-064]
dependencies: []
---

# P2: export_user_prompts_csv Uses N+1 Query Pattern

## Problem Statement

`export_user_prompts_csv()` in `app/models/export_models.py` runs N+1 queries: one for all prompts, then one per prompt for components. A user with 100 prompts triggers 101 queries.

## Findings

- **File:** `app/models/export_models.py` lines 7-42
- **Pattern:** `for prompt in prompts: conn.execute('SELECT ... WHERE prompt_id = ?', ...)`
- **Fixed in:** `export_all_prompts_json()` (same file) uses proper JOIN approach
- **Impact:** Slow export for users with many prompts

## Proposed Solution

**Option A (Recommended):** Use JOIN to fetch all components in one query

```python
def export_user_prompts_csv(conn, user_id):
    rows = conn.execute(
        '''SELECT p.title, p.completeness, p.created_at, i.name as industry_name,
                  cd.name as component_name, pc.content
           FROM prompts p
           JOIN industries i ON p.industry_id = i.id
           LEFT JOIN prompt_components pc ON pc.prompt_id = p.id
           LEFT JOIN component_definitions cd ON pc.component_id = cd.id
           WHERE p.user_id = ?
           ORDER BY p.created_at, cd.position''',
        (user_id,)
    ).fetchall()
    # Group by prompt in Python
    ...
```

**Effort:** Medium (restructure loop logic)
**Risk:** Low

## Acceptance Criteria

- [ ] `export_user_prompts_csv` uses a single JOIN query (no per-prompt queries in loop)
- [ ] CSV output is semantically identical to before

## Work Log

- 2026-06-02: Found during Run 064 tail review.
