# HANDOFF -- Sandbox

**Date:** 2026-06-01
**Branch:** `feat/pitfall-eval-harness`
**Phase:** Compound complete (autonomy hardening). Eval harness spec-eval gate calibration still pending.

## Current State

Sandbox autonomy hardening is complete through the compound phase. The burn-zone safety model is shipped: `.gitignore` expanded to 77 patterns, secrets policy defined, advisory audit extracted to helper skill, data inventory completed, 2 sensitive CSVs untracked, destructive git rewrites added to CLAUDE.md forbidden actions. 5-agent review found and fixed 3 P1s. Solution doc written.

The eval harness spec-eval gate (Phases 1-5 code) is complete but calibration requires a real API key — that work is pending.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Plan | `docs/plans/2026-05-13-feat-sandbox-autonomy-hardening-plan.md` |
| Data Inventory | `docs/reports/data-inventory-2026-06-01.md` |
| Solution | `docs/solutions/2026-06-01-sandbox-autonomy-hardening-blast-radius.md` |
| Advisory Audit Skill | `.claude/skills/advisory-audit/SKILL.md` |
| Scan Script | `scripts/sensitive-file-scan.sh` |
| Spec Eval Gate Plan | `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md` |

## Deferred Items

- **Credential rotation:** 5 `.env` files with real API keys on disk. User committed to rotating. Priority: Anthropic keys (billing).
- **Contact data in git history:** 2 CSVs in public git history on origin/master (Option A: accept exposure). Remediation path: `git filter-repo` + force-push if sensitivity changes.
- **SKILL.md at 735 lines:** Still above 500-line concern. Future additions should evaluate second extraction.
- **Spec eval gate calibration:** Run with real ANTHROPIC_API_KEY against WRC and Ethics Toolkit specs, then add step 9w.8 to SKILL.md.

## Three Questions

1. **Hardest decision?** Keeping autopilot fully powerful and moving all safety to the perimeter. If a production credential enters the sandbox, no internal control catches it until the advisory audit — which is non-blocking.
2. **What was rejected?** Removing `dangerouslySkipPermissions`, adding blocking gates, relying on prose reminders, restricting agent file access, history rewriting for the 2 CSVs.
3. **Least confident about?** Whether the advisory audit will actually run consistently in practice. It's a numbered step (not prose), but explicitly marked non-blocking. FC11 shows optional steps get skipped under context pressure.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is the sandbox repo, an autopilot burn zone for compound engineering builds.
Autonomy hardening is complete. Next: run spec-eval gate calibration with a real API key (see eval-harness section of HANDOFF), then add step 9w.8 to SKILL.md.
```
