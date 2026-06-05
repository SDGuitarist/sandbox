---
title: "Sandbox Autonomy Hardening: Blast Radius Reduction"
date: 2026-06-01
tags: [autonomy, control-plane, security, gitignore, advisory-audit, secrets-policy]
module: .claude/skills/autopilot, .claude/skills/advisory-audit, .gitignore, CLAUDE.md
problem: "Sandbox autopilot had full power but no perimeter controls — production credentials, real contact data, and sensitive files could enter the burn zone undetected"
lesson: "Safety for an intentionally powerful sandbox comes from controlling what enters the perimeter, not from restricting what agents do inside it"
severity: P1
root_cause: "No secrets policy, no gitignore coverage for sensitive file types, no post-run audit to detect what changed, no inventory of existing data"
---

# Sandbox Autonomy Hardening: Blast Radius Reduction

## Problem Statement

The sandbox repo (`~/Projects/sandbox`) runs autopilot with `dangerouslySkipPermissions: true` — agents can read, write, execute, and commit anything. This is by design. But there were no controls around what was *present* in the sandbox:

- **No secrets policy.** Real API keys (Anthropic, Apify, Hunter, Perplexity, SerpAPI, Supabase service_role) sat in `.env` files across 5 subprojects. Agents could read them freely.
- **No gitignore coverage.** The root `.gitignore` had 12 lines. No patterns for `.env.local`, `.env.production`, key files (`.pem`, `.key`), credential configs, Terraform state, or data files (`.csv`, `.jsonl`).
- **Real contact data tracked in git.** Two CSVs with scraped business names, emails, and phone numbers were committed to `origin/master` on a public GitHub repo.
- **No post-run visibility.** After an autopilot run, there was no way to see what new sensitive files appeared on disk or in git tracking.

The previous version of the hardening plan tried to solve this by restricting agents inside the sandbox (blocking gates, tail hardening, failure registry normalization). That approach was scrapped in favor of the burn-zone model.

## Root Cause

The sandbox was designed as a powerful autopilot workspace but lacked perimeter controls. The implicit assumption was that nothing sensitive would enter the sandbox — but over months of development, real credentials accumulated in `.env` files and real scraped data got committed. The repo went public on GitHub, making the exposure real.

## Solution

### Safety Model: The Autopilot Burn Zone

Instead of restricting agents inside the sandbox, move all safety boundaries around it:

1. **Keep dangerous things out** — secrets policy, gitignore, data inventory
2. **Audit what happened after** — non-blocking post-run advisory audit
3. **Promote manually** — sandbox results leave only through reviewed diffs or PRs

`dangerouslySkipPermissions: true` stays. No blocking gates added. No approval prompts.

### What Was Built (3 commits)

**Commit 1 — `c9d34f8`: Core implementation**
- `.gitignore` expanded from 12 to 68+ lines (env files, keys/certs, credential configs, data files, Terraform, Kubernetes, logs, uploads/results)
- `CLAUDE.md` updated with destructive history rewrite confirmation requirement
- `.claude/skills/autopilot/SKILL.md` got Step 1.55 (advisory baseline) and Advisory Audit step
- Data inventory completed — classified all tracked/on-disk files
- 2 sensitive CSVs untracked (`git rm --cached`)
- Plan document rewritten with burn-zone safety model

**Commit 2 — `cc41a24`: Review fixes**
- `.env.*` pattern broadened to catch `.env.production`, `.env.staging`, etc. (was only `.env.local`)
- Advisory Audit tracked-file filter aligned with Step 1.55 scan patterns (added sqlite, crt, npmrc, kubeconfig, tfstate, tfvars, credentials)
- Credential provider details redacted from data inventory report
- Verification `find` command aligned with canonical scan

**Commit 3 — `abcd982`: Deferred simplifications**
- Advisory audit extracted to `.claude/skills/advisory-audit/SKILL.md` (SKILL.md dropped from 794 to 735 lines)
- Sensitive-file scan centralized to `scripts/sensitive-file-scan.sh` (eliminated 3-way duplication)
- SSH key, Java keystore, PGP patterns added to `.gitignore`

### Files Changed

| File | Change |
|------|--------|
| `.gitignore` | 12 lines -> 77 lines |
| `CLAUDE.md` | +1 line (destructive history rewrites) |
| `.claude/skills/autopilot/SKILL.md` | +6 lines net (after extraction) |
| `.claude/skills/advisory-audit/SKILL.md` | New (100 lines) |
| `scripts/sensitive-file-scan.sh` | New (29 lines) |
| `docs/plans/2026-05-13-feat-sandbox-autonomy-hardening-plan.md` | Full rewrite |
| `docs/reports/data-inventory-2026-06-01.md` | New |

## What Worked

1. **Burn-zone model is coherent.** Reviewers (5 agents) found 0 violations of the core constraint (no reduced autopilot functionality). Every control is either preventive (gitignore, secrets policy) or advisory (post-run audit).

2. **Data inventory before gitignore changes.** The sequence (inventory -> ignore rules -> stop -> remediation plan) prevented accidental data loss. The inventory found 2 tracked sensitive files and 5 `.env` files with real credentials — all correctly classified.

3. **Skill extraction pattern.** Moving the advisory audit to a helper skill followed the same pattern as `update-learnings-noninteractive`. The autopilot SKILL.md calls `/advisory-audit baseline` and `/advisory-audit report <run-id>` as single-line steps. This keeps the orchestrator's instruction surface manageable.

4. **Centralized scan script.** `scripts/sensitive-file-scan.sh` is the single source of truth for sensitive-file patterns. Both the baseline capture and the post-run audit call the same script. The plan references it by path instead of duplicating the `find` command.

5. **Review caught real gaps.** The `.env.*` pattern gap (P1) would have missed `.env.production` files — a common framework pattern. The audit filter misalignment (P1) would have silently dropped sqlite, kubeconfig, and tfstate files from the tracked-file diff.

## What to Watch

1. **Credentials still on disk.** 5 `.env` files with real API keys exist on disk. They are not tracked by git, but agents can read them. The user committed to rotating them — track whether that happens.

2. **Contact data in public git history.** Two CSVs with real scraped contact data remain in git history on `origin/master` (Option A: accept exposure). If the sensitivity assessment changes, `git filter-repo` + force-push is the remediation path.

3. **Advisory audit is non-blocking by design.** Per FC11 history, non-blocking steps can be skipped. The audit is placed as a numbered step in the autopilot skill (not prose in CLAUDE.md), which mitigates but does not eliminate the skip risk. If the audit consistently produces empty reports, the orchestrator may start deprioritizing it.

4. **SKILL.md at 735 lines.** Still above the 500-line concern threshold from the original plan's Feed-Forward. The extraction helped but the file remains large. Future additions should consider whether a second extraction is needed.

## Risk Resolution

| Feed-Forward Risk | Resolution |
|---|---|
| "Whether existing tracked .db, .csv, and .jsonl files contain sensitive material" | **Resolved.** Inventory completed. 2 sensitive files found and untracked. 9 remaining files classified as Safe or Generated. |

## Stats

- **Commits:** 3 (feat + fix + refactor)
- **Plan revisions:** 5 rounds (initial rewrite + 4 Codex review cycles)
- **Review agents:** 5 (security, architecture, simplicity, pattern, learnings)
- **Review findings:** 3 P1s fixed, 4 P2s (1 fixed, 3 deferred), 5 P3s (1 fixed, 4 accepted)
- **Net new lines:** ~200 (across gitignore, skills, script, plan, inventory)

## Feed-Forward

- **Hardest decision:** Keeping autopilot fully powerful and moving all safety to the perimeter. This means if a real production credential enters the sandbox, no internal control catches it until the post-run audit — which is advisory and non-blocking.
- **Rejected alternatives:** (1) Removing `dangerouslySkipPermissions`. (2) Adding blocking gates. (3) Relying on prose reminders. (4) Restricting agent file access. (5) Ignoring all of `.claude/`. (6) History rewriting for the 2 CSVs.
- **Least confident:** Whether the advisory audit will actually run consistently in practice. It's a numbered step (not prose), but it's explicitly marked non-blocking. FC11 shows that "optional" steps get skipped under context pressure. First real autopilot run with the audit will tell.
