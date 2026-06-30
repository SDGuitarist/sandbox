---
status: complete
priority: p1
issue_id: "072"
tags: [code-review, firebreak, g1, architecture, orchestrator, lifecycle]
dependencies: [071]
---

# P1 — Firebreak set-phase and deactivate lifecycle commands deferred (SKILL.md Step 17w/18w broken)

## Problem Statement

`python3 .claude/hooks/firebreak-activate.py set-phase tail` (Step 17w) and
`python3 .claude/hooks/firebreak-activate.py deactivate` (Step 18w) are DEFERRED
by the active firebreak for the same reason as #071 — bash_indirection defers
all python. This means the documented teardown cannot run unattended.

While `rm .claude/firebreak-active.json` is a confirmed GREEN fallback for
`deactivate`, the `set-phase tail` command has NO documented fallback, and the
`SKILL.md` Step 17w/18w do not document the non-python alternatives.

**Why it matters:** An unattended autopilot run cannot reliably tear down the
firebreak or flip phase=tail. This breaks the documented lifecycle and means the
firebreak cannot govern the tail cleanly (either it stays active and defers tail
python, or it's torn down via undocumented workaround).

## Findings

- **Evidence (run 079):** `python3 .claude/hooks/firebreak-activate.py set-phase tail`
  and `deactivate` deferred. Workaround: `rm .claude/firebreak-active.json` from
  the TRUSTED orchestrator → ALLOWED (confirmed by code trace in run 079 review).
- **Architecture reviewer finding:** Two distinct sub-issues:
  - `set-phase tail` — no documented non-python fallback. Write tool path exists
    (classifier lines 2122-2123 authorize TRUSTED Write to sentinel) but SKILL.md
    Step 17w does not document it. **P1.**
  - `deactivate` — `rm` fallback confirmed GREEN by code trace. **P2** (documented
    fallback exists; documentation gap only).
- **Root cause:** Same as #071 — bash_indirection at line 2070 is unconditional.

## Proposed Solutions

### Solution A: Update SKILL.md Steps 17w and 18w (IMMEDIATE hotfix — no code change)

Replace:
- Step 17w: `python3 .claude/hooks/firebreak-activate.py set-phase tail`
  → Write tool call updating `.claude/firebreak-active.json` to set `phase: tail`
- Step 18w: `python3 .claude/hooks/firebreak-activate.py deactivate`
  → `rm .claude/firebreak-active.json`

Both Write and `rm` are confirmed GREEN for TRUSTED orchestrator identity.
This is deployable immediately without any classifier code change.

**Pros:** Immediate fix; no blast radius to classifier.
**Cons:** Leaves the underlying classify issue (#071) unresolved.
**Effort:** Small (2 lines in SKILL.md)
**Risk:** Low.

### Solution B: Fix the classifier (#071) then update SKILL.md

Implement #071 first (trusted-tool allowlist), then restore the python-based
lifecycle commands in SKILL.md. Cleaner long-term (doesn't require SKILL.md to
work around classifier limits).

**Pros:** Clean architecture; python lifecycle commands work as documented.
**Cons:** Requires #071 to be implemented first.
**Effort:** Medium (depends on #071)
**Risk:** Low after #071 is verified.

## Recommended Action

Implement Solution A (SKILL.md hotfix) immediately to restore unattended lifecycle
correctness. Track Solution B as a follow-on after #071 is merged and validated.

## Technical Details

- **Affected files:**
  - `.claude/skills/autopilot/SKILL.md` — Step 17w (line ~984), Step 18w (line
    ~1047-1048)
  - `.claude/hooks/firebreak-activate.py` — deactivate (line 106), set_phase (line 87)
  - `.claude/hooks/firebreak-classify.py` — bash_indirection (line 1789), line 2070

## Acceptance Criteria

- [ ] SKILL.md Step 17w uses Write-tool or non-python path to flip phase=tail
- [ ] SKILL.md Step 18w uses `rm .claude/firebreak-active.json` or Write-tool
  to deactivate
- [ ] Both run cleanly in an unattended autopilot run with firebreak active
- [ ] Existing classifier tests still pass

## Work Log

- 2026-06-29: Created from run 079 review. Architecture reviewer classified:
  set-phase as P1 (no documented fallback), deactivate as P2 (rm fallback
  confirmed GREEN by code trace). Combined here as single lifecycle issue.
  In run 079, teardown done manually via `rm .claude/firebreak-active.json`
  (allowed, confirmed GREEN).
