# Security Brief Compatibility Analysis

> Maps the security audit brief against Alex's existing infrastructure.
> Created: 2026-06-01.

## Core Architecture: Three Layers

```
Layer 3: Autonomous Agents     <-- what acts (autonomous-agent-plan.md)
Layer 2: Eval Harness           <-- what tests constraints work (eval-harness)
Layer 1: Security Governance    <-- what constrains actions (security-audit-brief.md)
```

Currently building Layer 3 on top of a partial Layer 1.

## Principle Alignment

The brief's thesis -- "The AI should propose. Deterministic controls should
dispose." -- is already partially embedded in the autopilot pipeline:

| Brief Principle | Implementation | Scope |
|---|---|---|
| Propose, don't dispose | Spec gates block swarm before launch | Build pipeline only |
| Visible | BUILD_TRACKING.md, solution docs | Build pipeline only |
| Scoped | CLAUDE.md forbidden actions, bash rules | Sandbox repo only |
| Reversible | "Git commit before multi-file edits" | Inconsistent |
| Contained | SQLite-only, no production DB | Strong in sandbox |
| Auditable | Solution docs, agent pitfalls log | Build pipeline only |
| Policy-governed | Spec completeness + eval gates | Build pipeline only |

Pattern: **build pipeline has strong controls, broader local environment doesn't.**

## Already Implemented (Strong)

| Brief Section | Existing Equivalent | Status |
|---|---|---|
| Sec 11: High-risk actions | CLAUDE.md forbidden actions + safety rule | Solid |
| Sec 10: Permission levels | 3 autonomy classes (manual/solo/swarm) | Partial (L0, L3, L3) |
| Sec 13: Deterministic gates | Spec completeness, spec eval, smoke tests | Strong for builds |
| Sec 12: Consequence prompting | Feed-Forward framework ("least confident") | Strong |
| Sec 15: Evidence capture | BUILD_TRACKING.md, solution docs, reports | Build pipeline only |
| Sec 9: Sandbox boundaries | SQLite-only, no production DB | Strong |

## Partially Implemented (Gaps)

| Brief Section | Gap | Risk |
|---|---|---|
| Sec 5: Asset inventory | No systematic inventory of projects, APIs, credentials | ~15+ projects, multiple API keys, Railway/Supabase untracked |
| Sec 6: Data classification | No Public/Internal/Sensitive/Critical labels | Agent memory stores business context unclassified |
| Sec 7: Secrets audit | Memory warns about .env but no systematic scan | 4 DB data loss incidents suggest hygiene isn't systematic |
| Sec 8: Dependency review | Not done across projects | requirements.txt exists, no supply-chain audit |
| Sec 10: Permission levels | dangerouslySkipPermissions = L3-4 with no intermediate gates | Autopilot agents get full shell access |
| Sec 14: Per-project checklist | Ad-hoc memory entries, not formal checklist | No systematic per-project review |

## Not Implemented (Critical Gaps)

| Brief Section | What's Missing | Priority |
|---|---|---|
| Sec 1-3: Freeze + inventory | No pre-audit backup or read-only discovery | HIGH |
| Sec 5: Asset inventory table | No single document listing all projects with sensitivity/credentials/API access | HIGH |
| Sec 9: Sandbox boundary diagram | No visual/written map of what can access what | MEDIUM |
| Sec 10: Formal agent permission matrix | 3 coarse levels vs. brief's 5 levels | MEDIUM |
| Sec 17: Audit deliverables | None of the 10 deliverables exist as formal documents | LOW (build incrementally) |

## Key Tension: Autonomous Agents vs. Security Governance

The autonomous agent plan (Level 5) envisions agents acting proactively.
The security brief says this requires Layer 1 governance first.

Specific conflicts:

1. **Checkout Monitor Agent** needs Level 3 permissions (hits URLs, checks
   responses, sends alerts). Brief requires: scoped, reversible, logged,
   reviewed, blast radius known, secrets excluded, rollback available.

2. **Autopilot** uses dangerouslySkipPermissions which disables OS-level
   permission gates. Brief's Section 13 wants structural enforcement
   (filesystem permissions, containers), not just prompt-level (CLAUDE.md).

3. **Agent memory** stores business context (client names, pricing, strategy)
   without data classification. Brief's Section 6 would require classification
   before agents can access it.

## Permission Level Mapping

| Brief Level | Current Equivalent | Coverage |
|---|---|---|
| L0: Read-only | Interactive Claude Code (no auto-accept) | Unused in practice |
| L1: Drafting | Claude Code with review before apply | Rare |
| L2: Sandbox editor | Claude Code with auto-accepted Read/Edit/Write | Daily use |
| L3: Controlled executor | Autopilot with dangerouslySkipPermissions | Swarm builds |
| L4: Production-adjacent | git push, Railway deploy, Supabase access | Manual only |

Gap: No formal gate between L2 and L3. dangerouslySkipPermissions is binary
(on/off), not granular.

## Correct Sequencing

The brief and existing plans are fully compatible but sequenced wrong:

1. Security audit (brief Sections 1-7) -- inventory, classify, scan secrets
2. Deterministic gates (brief Sections 9, 10, 13) -- permission matrix, boundaries
3. Autonomous agents -- built on governed foundation
4. Eval harness extensions -- multi-parallel testing validates governance works

## Recommended First Actions

1. **Asset inventory** -- single document listing all projects, sensitivity,
   credentials, API access, risk rating
2. **Secrets scan** -- read-only search across all projects for .env, tokens, keys
3. **Data classification** -- label each project and memory file
4. **Permission matrix** -- map each tool/agent to a formal permission level
5. **Sandbox boundary diagram** -- document what can access what
