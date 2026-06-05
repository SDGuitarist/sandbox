---
title: "feat: Sandbox Autonomy Hardening"
type: feat
status: approved
date: 2026-05-13
revised: 2026-06-01
origin: "2026-05-13 sandbox autonomy analysis"
build_method: manual
swarm: false
feed_forward:
  risk: "Existing tracked .db, .csv, and .jsonl files may already contain sensitive material. The inventory phase must classify them before any git hygiene changes."
  verify_first: true
---

# feat: Sandbox Autonomy Hardening

## Purpose

This plan reduces the blast radius of sandbox autopilot without reducing its power. The safety model is not "restrict the agent inside sandbox." The safety model is **"keep secrets, valuable originals, and sensitive data out of the sandbox; audit and promote manually."**

`/Users/alejandroguillen/Projects/sandbox` is an **autopilot burn zone** — a workspace where agents operate at full autonomy. Safety comes from what is and is not present in the burn zone, not from limiting what agents can do inside it.

## Core Constraint

Sandbox autopilot must not be reduced, interrupted, or slowed down. The setting `dangerouslySkipPermissions: true` stays. No approval prompts, confirmation gates, or blocking hooks are added by this plan. Every control introduced here is either preventive (keep dangerous things out) or advisory (report what happened after).

## Operating Principle: The Autopilot Burn Zone

`/Users/alejandroguillen/Projects/sandbox` is designated as the autopilot burn zone. Inside this directory, agents may:

- Read, write, create, and delete any file
- Execute arbitrary shell commands
- Spawn worktrees and parallel agents
- Run tests, builds, and dev servers
- Branch, commit, merge, and manage worktrees freely
- Install dependencies and run package managers

The existing sandbox operating contract in `CLAUDE.md` explicitly requires human confirmation for `git push --force` and `git reset --hard`. **New recommendation from this plan:** extend that confirmation requirement to all destructive history rewrites (e.g., `git rebase` that rewrites published commits, `git filter-repo`, `git filter-branch`, amending pushed commits). This is a proposed update to `CLAUDE.md`, not a claim that it is already covered.

**Because agents have full power here, the sandbox must not contain:**

- Production credentials or API keys with real billing/access
- Irreplaceable original files (source recordings, signed contracts, client deliverables)
- Private or client data (PII, financial records, health data)
- High-value assets that cannot be regenerated
- Credentials for services where exposure would cause harm

Safety is achieved by controlling what enters the burn zone, not by restricting what happens inside it.

## Plan Quality Gate

### 1. What exactly is changing?

Seven documentation and hygiene changes:

1. **Secrets policy** — define what credentials are and are not allowed in sandbox
2. **Git hygiene controls** — expand `.gitignore` to prevent accidental tracking of sensitive file types
3. **Data inventory requirement** — classify existing tracked/generated data files before any hygiene changes
4. **Manual promotion rule** — formalize that autopilot results leave sandbox only through human review
5. **Post-run advisory audit** — add a non-blocking read-only report of potentially sensitive new files after each run, requiring one narrow non-blocking addition to `.claude/skills/autopilot/SKILL.md`
6. **Destructive git recommendation** — propose extending the `CLAUDE.md` confirmation requirement to all history rewrites, not just force-push and hard-reset
7. **Verification commands** — provide read-only commands to check compliance

### 2. What must NOT change?

- `dangerouslySkipPermissions: true` — stays enabled
- Autopilot execution flow — no new gates, prompts, or blockers added to the mandatory pipeline
- `.claude/settings.local.json` — not edited by this plan
- Existing tracked files — nothing is untracked, deleted, or moved without an explicit human-reviewed inventory and remediation plan first
- The compound engineering workflow (brainstorm, plan, work, review, compound)
- Global hooks, commands, or settings outside sandbox

**One narrow edit is allowed:** `.claude/skills/autopilot/SKILL.md` receives two non-blocking advisory additions: (a) a baseline-capture step immediately after Step 1.5 creates BUILD_TRACKING.md (writes git SHA to BUILD_TRACKING.md and filesystem snapshot to a fixed staging path), and (b) an advisory audit step appended after the existing mandatory tail (copies the staging file into the run-id directory, generates the report). Neither step can fail the run. See [Integration point](#integration-point) and [Baseline method](#baseline-method) for details.

### 3. How will we know it worked?

See [Verification Commands](#verification-commands) below. All verification is read-only — no command modifies state.

### 4. What is the most likely way this plan is wrong?

**Existing data may already be sensitive.** The inventory phase may reveal that tracked `.db`, `.csv`, or `.jsonl` files contain real user data, API responses with PII, or eval results with proprietary content. If so, this plan does not prescribe what to do with them — it only requires classification and a separate remediation plan. A follow-up decision is needed for any file classified as sensitive.

**Git hygiene may be incomplete.** The `.gitignore` additions cover common patterns but may miss project-specific paths. The inventory phase should surface gaps.

## Secrets Policy

### Credential types covered

This policy applies to all of the following:

- API keys and API secret tokens (any provider — e.g., Stripe secret keys, Twilio auth tokens, SendGrid API keys, OpenAI/Anthropic keys)
- OAuth client secrets and refresh tokens
- Database connection strings and passwords
- SSH private keys and keypairs
- Cloud provider credentials (AWS access keys, GCP service account JSON, Azure client secrets)
- Service account JSON files (e.g., Firebase Admin SDK JSON, GCP service accounts)
- TLS/SSL certificates and private keys
- Webhook signing secrets (e.g., Stripe webhook secrets, GitHub webhook secrets)
- Deploy tokens and CI/CD secrets
- Package registry tokens (npm `.npmrc` authTokens, PyPI, RubyGems)
- Docker registry authentication (`.docker/config.json`)
- Terraform state files and `.tfvars` with secrets
- HashiCorp Vault tokens
- JWT signing keys and HMAC shared secrets
- Kubernetes kubeconfigs and cluster credentials
- Apple `.p8` push notification keys
- GitHub fine-grained personal access tokens
- Supabase `service_role` keys (the `anon` key is public by design; `service_role` bypasses RLS)
- Exported cookies or session tokens
- Password manager exports

### Allowed in sandbox

- **`.env.example` files** with placeholder values documenting required variables
- **Fake/dummy values** (e.g., `sk-test-fake-1234`, `password123`, `localhost` URLs)
- **Dev-only credentials** with low rate limits, no billing, and no access to real data (e.g., free-tier API keys for development, Supabase dev project `anon` keys)

### Not allowed in sandbox

- **Production credentials** — any credential type listed above that accesses real services with real data or billing
- **Real user data** — even for testing; use synthetic data instead
- **Credentials shared with production** — if a key works in prod, it does not belong here

### Handling real credentials when needed

If a task genuinely requires a real credential (e.g., testing an API integration):

1. Inject it manually into a `.env.local` file (not `.env` or `.env.example`)
2. Verify `.env.local` is in `.gitignore` before use
3. Remove the credential after the task completes
4. If the credential was used in a sandbox that ran with `dangerouslySkipPermissions`, treat it as potentially exposed and rotate it if it matters

### Rules for agents

- Do not print, log, or echo secret values to stdout or files
- Do not auto-edit `.env`, `.env.local`, or credential files without explicit human approval
- Do not commit `.env.local` or files matching `.env.*.local`
- If a task requires credentials that are not present, stop and ask — do not fabricate real-looking keys

## Git Hygiene Controls

### Recommended `.gitignore` additions

Add the following patterns to the root `.gitignore`:

```gitignore
# Environment files with real values (NOT .env.example — those are safe)
.env.local
.env.*.local

# Claude Code volatile/local state (skills, agents, settings.json stay tracked)
.claude/worktrees/
.claude/agent-memory/
.claude/settings.local.json
.claude/cache/
.claude/todos/
.claude/logs/

# Dependencies and build artifacts
node_modules/
.next/
__pycache__/
*.pyc
.venv/
venv/
dist/
build/

# Data files that may contain sensitive content
*.csv
*.jsonl
*.db
*.sqlite
*.sqlite3

# Key and certificate files
*.pem
*.key
*.p12
*.pfx
*.crt
*.p8

# Service account, credential, and auth config files
*-service-account.json
*-credentials.json
credentials.json
service-account.json
.npmrc
.docker/config.json

# Terraform state (may contain secrets in plaintext)
*.tfstate
*.tfstate.backup
*.tfvars

# Kubernetes config
kubeconfig
.kube/

# Logs
*.log
logs/

# Upload and result directories
uploads/
results/

# Advisory audit staging file (overwritten each run)
docs/reports/advisory-filesystem-baseline.txt
```

### What stays tracked

The following `.claude/` paths are project-local control surfaces and must remain tracked:

- `.claude/skills/` — autopilot and other skill definitions
- `.claude/agents/` — agent definitions
- `.claude/settings.json` — project-level settings (not `.local`)

### Implementation rules

- **This change must not affect autopilot execution.** Gitignore only affects what git tracks, not what agents can read or write.
- **Before untracking any currently tracked file**, produce a proposed list with classification (sensitive / not sensitive / unknown) and get human approval. Do not run `git rm --cached` blindly.
- **Do not delete files.** Untracking removes from git, not from disk. Agents can still use untracked files.
- **Do not ignore `.env.example`** — these files document required variables with placeholder values and are safe to track.

## Existing Data Inventory

This is the prerequisite step. It must complete before any `.gitignore` changes or untracking.

### Sequence (this exact order)

1. **Inventory** — scan for all tracked and generated data files matching the patterns below. Record each file with its path, size, tracking status, and classification.
2. **Update ignore rules** — add new `.gitignore` patterns to prevent future files from being tracked. This only affects files created after the change. Already-tracked files are not affected by `.gitignore` — their tracking status does not change.
3. **Stop here** — do not untrack or delete any existing files at this stage. The inventory and ignore rules are complete. No further action on existing files.
4. **If sensitive data is found** — create a separate, human-approved remediation plan that covers:
   - Which specific files to untrack (with `git rm --cached`), listed by name
   - Whether git history cleanup is needed (e.g., `git filter-repo`) and for which files
   - Whether any credentials found in those files need rotation
   - Whether the sensitive data was pushed to a remote (check with `git log --remotes --oneline -- <file>`)
   - Who may have cloned or pulled the repo since the sensitive data was committed, and whether they need to be notified
   - A notification/coordination plan if the data reached external parties
   - A verification step confirming the files are removed from tracking but still on disk
   - Human reviews and approves the remediation plan before any execution

### File types to inventory

| Pattern | Why it matters |
|---------|---------------|
| `*.db`, `*.sqlite`, `*.sqlite3` | May contain application data, user records, or eval results |
| `*.csv` | May contain exported data, scraped results, or PII |
| `*.jsonl` | May contain API responses, eval logs, or structured data |
| `uploads/`, `results/` directories | May contain user-uploaded or generated content |
| Eval reports (`eval-harness/calibration/`, `output/`) | May contain model outputs or proprietary prompts |
| API output logs | May contain response data from external services |
| `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.p8` | Private keys or certificates |
| `*-service-account.json`, `credentials.json` | Cloud provider credentials |
| `.npmrc`, `.docker/config.json` | Package/container registry auth |
| `*.tfstate`, `*.tfvars` | Terraform state and variables |
| `kubeconfig` | Kubernetes cluster credentials |

### Inventory format

For each file found, record:

| File path | Tracked by git? | Size | Classification | Notes |
|-----------|-----------------|------|----------------|-------|
| `example.db` | Yes | 2.1 MB | Unknown — needs review | Created by habit-tracker app |

### Classification categories

- **Safe** — synthetic data, empty schemas, test fixtures with no real information
- **Sensitive** — contains real user data, API responses with PII, production exports, or real credentials
- **Unknown** — needs human review before deciding
- **Generated** — reproducible output that can be regenerated (eval results, build artifacts)

**No file is deleted, moved, or untracked based on this inventory alone.** The inventory is input for a human decision. If any file is classified as Sensitive or Unknown, a separate remediation plan is required before taking action.

## Manual Promotion Rule

Autopilot works inside sandbox copies and worktrees only. Valuable projects outside sandbox receive changes only through:

- **Reviewed diffs** — human reads the diff before applying
- **Pull requests** — changes go through normal PR review
- **Manual copy after audit** — human copies specific files after inspecting them

Autopilot does not push directly to repos outside `~/Projects/sandbox/`. Autopilot does not create PRs in external repos without human initiation. The sandbox is a drafting table, not a deployment pipeline.

## Post-Run Advisory Audit

After the mandatory autopilot pipeline completes, a best-effort advisory audit runs. Its findings are informational only — they cannot fail the run and are not checked for pass/fail status.

### Integration point

The audit requires two narrow, non-blocking additions to `.claude/skills/autopilot/SKILL.md`:

**Addition 1 — Baseline capture (immediately after Step 1.5):**

After Step 1.5 creates BUILD_TRACKING.md, before any planning or work begins, record the advisory baseline. This is the earliest reliable point because BUILD_TRACKING.md must exist as the write target for the git SHA. The filesystem snapshot is written to the fixed staging path `docs/reports/advisory-filesystem-baseline.txt` (not inside `<run-id>/`, which does not exist yet). See [Baseline method](#baseline-method) for details.

**Addition 2 — Advisory audit step (after mandatory tail, before Done):**

Placed after all mandatory tail steps (BUILD_TRACKING completion, solution doc, learnings propagation, HANDOFF, self-audit) and before the final `<promise>DONE</promise>` emission.

Execution order:

1. Step 1.5 creates BUILD_TRACKING.md
2. Advisory baseline is captured (git SHA to BUILD_TRACKING.md, filesystem snapshot to `docs/reports/advisory-filesystem-baseline.txt`)
3. ... all planning, work, review, and mandatory tail steps (including Step 6.1 which creates `docs/reports/<run-id>/`) ...
4. Advisory audit copies `docs/reports/advisory-filesystem-baseline.txt` into `docs/reports/<run-id>/` for archival, then generates the report (best-effort, non-blocking)
5. `<promise>DONE</promise>` is emitted

Neither addition can fail the run. Neither addition modifies any existing mandatory step.

### Audit failure handling

The advisory audit is best-effort at every layer:

1. **If report generation succeeds:** copy the staging baseline into `docs/reports/<run-id>/advisory-filesystem-baseline.txt` for archival, then write the report to `docs/reports/<run-id>/advisory-audit.md`.
2. **If the baseline staging file is missing** (e.g., baseline capture was skipped or failed): generate the report without the filesystem diff — report only git-diff-based findings and note that the filesystem comparison was unavailable.
3. **If report generation fails** (exception, timeout, scan error): try to append a one-line note to `BUILD_TRACKING.md` under a `## Advisory Audit` heading: `"Advisory audit skipped: [reason]"`.
4. **If the BUILD_TRACKING.md append also fails:** proceed to `<promise>DONE</promise>` anyway. The audit is advisory — no failure at any layer blocks Done.

There is no status check on advisory findings. The `<promise>DONE</promise>` emission happens regardless of audit outcome.

### Baseline method

Immediately after Step 1.5 creates BUILD_TRACKING.md — and before any planning or work begins — record two baselines:

**1. Git baseline** — run `git rev-parse HEAD` and write the SHA to BUILD_TRACKING.md:

```markdown
## Advisory Baseline
baseline_sha: abc1234def5678...
```

**2. Filesystem baseline** — run the sensitive-file scan (see below) and write the output to the fixed staging path `docs/reports/advisory-filesystem-baseline.txt`. This file is overwritten at the start of each run. It captures which sensitive-pattern files already exist on disk before the run, so the post-run audit can distinguish pre-existing files from new ones.

The staging path is used because `docs/reports/<run-id>/` does not exist until Step 6.1. The advisory audit step (which runs after Step 6.1) copies the staging file into `docs/reports/<run-id>/advisory-filesystem-baseline.txt` for archival before generating the report.

**Implementation note:** The baseline capture step should best-effort create `docs/reports/` (e.g., `mkdir -p docs/reports`) before writing the staging file. If the directory creation fails, skip the filesystem baseline and proceed — the audit will run in degraded mode (git-diff only, no filesystem comparison).

The post-run audit uses both baselines:

- **New tracked files:** `git diff --name-only --diff-filter=A <baseline_sha> HEAD`
- **Modified tracked files:** `git diff --name-only --diff-filter=M <baseline_sha> HEAD`
- **New untracked/ignored sensitive files:** re-run the filesystem scan and diff against `docs/reports/advisory-filesystem-baseline.txt` to find files that appeared during the run

### Sensitive-file filesystem scan

This scan catches files that `.gitignore` intentionally hides — exactly the category the audit needs to surface. It uses direct filesystem scanning instead of `git ls-files --others --exclude-standard`, which would miss ignored files.

The canonical scan is defined in `scripts/sensitive-file-scan.sh`. Both the baseline capture (Step 1.55) and the post-run audit reference this single script to avoid duplication.

```bash
bash scripts/sensitive-file-scan.sh
```

No `-maxdepth` limit — the scan walks the full tree. Generated/dependency directories are excluded by path to keep it fast and noise-free.

### What the audit reports

| Check | How to detect |
|-------|--------------|
| **New `.env` or `.env.local` files** | Filesystem scan diff against baseline |
| **Newly tracked data files** | `git diff --name-only --diff-filter=A <baseline_sha> HEAD` filtered to `.db`, `.csv`, `.jsonl` |
| **New sensitive untracked/ignored files** | Filesystem scan diff against `docs/reports/advisory-filesystem-baseline.txt` |
| **Large local databases** | Any `.db`/`.sqlite` file over 10 MB via `find` + `stat` |
| **New API-touching code** | New/modified files containing `fetch(`, `axios.`, `requests.`, `http.get`, `urllib`, `httpx` |
| **Outbound service config** | New entries in config files pointing to external URLs or services |
| **New git remotes or GitHub automation** | `git remote -v` changes, new `.github/workflows/` files |
| **Changes to `.claude/`** | Modified agent settings, skills, or autopilot configuration in the diff |

### Report format

```markdown
## Post-Run Advisory Audit — [run-id]
Git baseline: [baseline_sha from BUILD_TRACKING.md]
Filesystem baseline: docs/reports/[run-id]/advisory-filesystem-baseline.txt
Head: [current HEAD]

### New environment files
- (none found)

### Newly tracked data files
- eval-harness/calibration/spec-eval/results.jsonl (2.3 KB, added this run)

### New sensitive untracked/ignored files
- (none new since baseline)

### Large databases
- (none over 10 MB)

### New API-touching code
- src/api/client.ts:14 — fetch('https://api.example.com/v1/...')

### Outbound service config
- (none found)

### Git remotes / GitHub automation
- (no changes)

### Claude/agent config changes
- .claude/skills/autopilot/SKILL.md — advisory audit step added
```

### Enforcement

**This audit is advisory only.** It runs after the mandatory pipeline completes. It does not gate, block, or fail any step. A human may choose to act on findings, but the audit itself is passive. There is no status check on advisory findings.

If a human explicitly requests enforcement (e.g., "fail the run if new .env files appear"), that is a separate policy decision outside this plan.

## Acceptance Tests

### Happy Path

- WHEN autopilot runs in sandbox THEN the system SHALL complete all mandatory steps without new approval prompts or blocking gates introduced by this plan
- WHEN `.env.local` exists in the sandbox root THEN `git check-ignore .env.local` SHALL confirm it is ignored
- WHEN the post-run audit runs THEN it SHALL produce a report at `docs/reports/<run-id>/advisory-audit.md` comparing current state against the baseline, and then `<promise>DONE</promise>` SHALL be emitted regardless of findings
- WHEN the advisory filesystem baseline is captured THEN it SHALL be written to `docs/reports/advisory-filesystem-baseline.txt` before any work begins, and copied into `docs/reports/<run-id>/` by the advisory audit step for archival
- WHEN a data inventory is requested THEN it SHALL list all matching files with size, tracking status, and classification
- WHEN the post-run audit fails to generate THEN a best-effort one-line note SHALL be appended to BUILD_TRACKING.md; if that also fails, the run SHALL proceed to Done anyway

### Error Cases

- WHEN a production credential is found in a tracked file THEN the inventory SHALL classify it as "Sensitive" for human review — it SHALL NOT auto-delete or auto-rotate
- WHEN `.gitignore` additions would untrack a currently tracked file THEN the system SHALL produce a proposed list for human approval before any `git rm --cached`
- WHEN the inventory classifies a file as Sensitive THEN a separate remediation plan SHALL be created before any untracking or history cleanup
- WHEN sensitive data was pushed to a remote THEN the remediation plan SHALL include a check for who cloned/pulled and a notification plan

## Verification Commands

All commands are read-only. None modifies state.

```bash
# Show current working tree status
git status --short

# Find tracked data files that should potentially be gitignored
git ls-files | rg '\.(db|sqlite|sqlite3|csv|jsonl)$|(^|/)node_modules/|(^|/)\.next/'

# Find environment files on disk (including ignored ones)
find . -maxdepth 3 -type f \( -name '.env' -o -name '.env.local' -o -name '.env.*.local' \) -not -path '*/.git/*'

# Check whether sensitive patterns are gitignored
git check-ignore -v .env.local .claude/worktrees .claude/agent-memory node_modules .next

# Find tracked key/certificate files
git ls-files | rg '\.(pem|key|p12|pfx|crt|p8)$'

# Find tracked credential files
git ls-files | rg '(credentials|service-account)\.json$|\.npmrc$|\.tfstate$|\.tfvars$|kubeconfig$'

# Full sensitive-file filesystem scan (catches gitignored files)
find . -type f \( -name '.env' -o -name '.env.*' -o -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.csv' -o -name '*.jsonl' -o -name '*.pem' -o -name '*.key' -o -name '*.p12' -o -name '*.pfx' -o -name '*.p8' -o -name '*.crt' -o -name 'credentials.json' -o -name '*-credentials.json' -o -name '*-service-account.json' -o -name '.npmrc' -o -name 'kubeconfig' -o -name '*.tfstate' -o -name '*.tfstate.backup' -o -name '*.tfvars' -o -name '.docker/config.json' \) -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/venv/*' -not -path '*/.next/*' -not -path '*/dist/*' -not -path '*/build/*' -not -path '*/.claude/worktrees/*'
```

### Expected results after implementation

- `git check-ignore -v .env.local` — reports ignored by `.gitignore` rule
- `git check-ignore -v .claude/worktrees` — reports ignored by `.gitignore` rule
- `git check-ignore -v .claude/agent-memory` — reports ignored by `.gitignore` rule
- `git check-ignore -v node_modules` — reports ignored by `.gitignore` rule
- `git ls-files | rg '\.(db|sqlite|sqlite3|csv|jsonl)$'` — only files that passed human review remain tracked
- `git ls-files | rg '\.(pem|key|p12|pfx|p8)$'` — returns empty (no private keys tracked)
- `.claude/skills/` and `.claude/agents/` — remain tracked and visible in `git ls-files`

## Feed-Forward

- **Hardest decision:** Keeping autopilot fully powerful and moving all safety boundaries around the sandbox rather than inside it. This means trusting that the burn zone perimeter (what's present in the directory) is the right control surface, not agent permissions. If sensitive material enters the sandbox, no internal control will catch it in time.
- **Rejected alternatives:** (1) Removing `dangerouslySkipPermissions` — rejected because it breaks unattended autopilot, the sandbox's core purpose. (2) Adding blocking prompts or confirmation gates — rejected because they interrupt autopilot flow and defeat the burn zone model. (3) Relying on agent reminders or prose instructions — rejected because they are non-deterministic and already proven unreliable (FC11 history). (4) Restricting agent file access within sandbox — rejected because partial restrictions create a false sense of security while breaking legitimate operations. (5) Ignoring all of `.claude/` — rejected because `.claude/skills/`, `.claude/agents/`, and `.claude/settings.json` are project-local control surfaces that must remain tracked; only volatile state (worktrees, agent-memory, settings.local.json, cache, todos, logs) should be ignored. (6) Shallow filesystem scan (`find -maxdepth 4`) — rejected because this repo has nested subprojects; full-depth scan with directory exclusions is more reliable and only marginally slower.
- **Least confident:** Whether existing tracked `.db`, `.csv`, and `.jsonl` files contain sensitive material. The inventory phase will answer this, but until it runs, there is an unknown risk that the git history already contains data that should not have been committed. If so, the remediation (history rewriting or rotation) is a separate, more invasive plan that requires human approval, including checking whether the data reached any remote or clone.
