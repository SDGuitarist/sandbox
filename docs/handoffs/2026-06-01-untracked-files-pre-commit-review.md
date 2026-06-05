# Pre-Commit Review: Untracked Files in Sandbox

**Date:** 2026-06-01
**Branch:** `feat/pitfall-eval-harness`
**Context:** After compound phase + gitignore cleanup, 7 untracked items remain that need triage.

## Files to Review

### 1. `writers-room-council/` -- Nested Git Repo

This is a **separate git repository** (has its own `.git/`). It should NOT be committed to sandbox -- it would create a gitlink submodule entry.

**Contents:** Next.js app (Supabase + Vercel), 23 council transcript JSONs, drafts, scripts, docs, todos. Has its own `HANDOFF.md`, `BUILD_TRACKING.md`, `compound-engineering.local.md`.

**Security concern:** Contains `.env.local` (Supabase keys, API keys). Verify this file is covered by its own `.gitignore` and is NOT tracked in the WRC repo.

**Action needed:**
- [ ] Add `writers-room-council/` to sandbox `.gitignore` (it's a separate project, not a submodule)
- [ ] Verify `.env.local` is in WRC's own `.gitignore` and not tracked
- [ ] Consider moving to `~/Projects/writers-room-council/` to avoid nesting repos

### 2. Cross-Feature Docs (5 untracked handoffs + 1 brief)

These are Codex review handoffs and briefs from prior sessions. They belong to features that were planned/reviewed but may not have been committed.

| File | Feature | Type |
|------|---------|------|
| `docs/briefs/2026-05-22-client-intake-dashboard-brief.md` | Client Intake Dashboard | Brief |
| `docs/handoffs/2026-05-22-client-intake-dashboard-codex-review.md` | Client Intake Dashboard | Codex review |
| `docs/handoffs/2026-05-23-autopilot-phase-agent-delegation-codex-review.md` | Autopilot Delegation | Codex review |
| `docs/handoffs/2026-05-23-cpaa-codex-pre-brainstorm.md` | CPAA Shadow Lab | Codex pre-brainstorm |
| `docs/handoffs/2026-05-24-cpaa-revised-architecture.md` | CPAA Shadow Lab | Architecture doc |
| `docs/handoffs/2026-05-24-cpaa-shadow-lab-event-replay-simulator-codex-review.md` | CPAA Shadow Lab | Codex review |

**Note:** `docs/handoffs/` already has 3 tracked files (`2026-05-25-*` and `2026-06-01-*`). `docs/briefs/` has 1 tracked file (`2026-05-23-autopilot-agent-delegation-brief.md`).

**Action needed:**
- [ ] Verify no secrets in any of the 6 files (grep for `sk-`, `key=`, `password`)
- [ ] Commit all 6 as cross-feature documentation (they're reference material, not feature code)
- [ ] Or defer to their respective feature branches if those branches exist

## Pre-Commit Checklist

```bash
# 1. Check WRC .env.local is gitignored in its own repo
git -C writers-room-council/ check-ignore .env.local

# 2. Scan cross-feature docs for secrets
grep -rl 'sk-\|api_key\|password\|secret' docs/briefs/ docs/handoffs/

# 3. Add WRC to sandbox gitignore
echo "writers-room-council/" >> .gitignore

# 4. Stage and commit cross-feature docs (if clean)
git add docs/briefs/2026-05-22-client-intake-dashboard-brief.md \
       docs/handoffs/2026-05-22-client-intake-dashboard-codex-review.md \
       docs/handoffs/2026-05-23-autopilot-phase-agent-delegation-codex-review.md \
       docs/handoffs/2026-05-23-cpaa-codex-pre-brainstorm.md \
       docs/handoffs/2026-05-24-cpaa-revised-architecture.md \
       docs/handoffs/2026-05-24-cpaa-shadow-lab-event-replay-simulator-codex-review.md
```

## Prompt for Next Session

```
Read docs/handoffs/2026-06-01-untracked-files-pre-commit-review.md.
Run the pre-commit checklist. Triage the 7 untracked items.
```
