# Security Audit Brief for Local AI Projects, Sandboxes, and Agentic Workflows

> Source: Alex's original research. Saved: 2026-06-01.
> Core principle: "The AI should propose. Deterministic controls should dispose."

## 1. Purpose

This audit is designed to secure local AI projects, experimental sandboxes, code
repositories, scripts, model workflows, and any agentic systems that can read files,
write files, run commands, call APIs, or modify project state.

The audit should not assume that an LLM or agent can reliably predict downstream
consequences. Instead, the system should be designed so that unsafe actions are
prevented, reversible, contained, logged, or manually approved before impact.

## 2. Audit Philosophy

The goal is to make the local environment:

- **Visible:** You know what exists.
- **Scoped:** Each tool or agent has only the access it needs.
- **Reversible:** Accidents can be rolled back.
- **Contained:** Failures stay inside the sandbox.
- **Auditable:** You can reconstruct what happened.
- **Policy-governed:** High-risk actions are blocked before execution.

The biggest mistake would be allowing an AI agent to operate directly across your
local drive, cloud accounts, API keys, GitHub repositories, and shell environment
without layered boundaries.

## 3. Correct Order of Audit Layers

Run the audit in this order:

1. Freeze and back up the current environment
2. Inventory projects, files, repos, scripts, credentials, and APIs
3. Classify data and systems by sensitivity
4. Identify what tools or agents can read, write, execute, or transmit
5. Search for secrets and sensitive data exposure
6. Review dependencies and supply-chain risk
7. Review local permissions and sandbox boundaries
8. Review agent/tool execution permissions
9. Add deterministic policy gates
10. Test in sandbox only
11. Add logging, rollback, and post-action review
12. Document residual risk

Do not start by running agents, cleanup scripts, auto-fixers, or scanners with
write permissions. Begin with read-only discovery.

## 4. Scope of the Audit

### Local files and project folders

AI project folders, code repositories, scripts, notebooks, prompt libraries,
generated outputs, downloaded datasets, configuration files, local databases,
.env files, hidden folders, temporary folders, exported ChatGPT or Claude
artifacts, API test files.

### Development tools

IDEs, terminal tools, package managers, Git clients, local databases, Docker
containers, virtual environments, automation scripts, task runners, browser
extensions, AI coding tools.

### External connections

GitHub, Google Drive, AWS or cloud accounts, OpenAI/Anthropic/Google AI APIs,
Zapier/Make/n8n workflows, calendar/email integrations, file-sync tools,
payment/CRM/business platforms, webhook endpoints.

## 5. Asset Inventory Checklist

Create an inventory table with these columns:

| Column | Description |
|---|---|
| Asset / Project | Name |
| Location | Path or URL |
| Owner | Who maintains it |
| Purpose | What it does |
| Contains sensitive data? | yes/no |
| Contains credentials? | yes/no/unknown |
| Has external API access? | yes/no |
| Can execute code? | yes/no |
| Can modify files? | yes/no |
| Connected to cloud or GitHub? | yes/no |
| Risk rating | low / medium / high / critical |
| Required action | What needs to happen |

High-priority assets: anything containing credentials, personal data, client
data, business records, production code, cloud access, or automated execution.

## 6. Data Classification

| Level | Description | Examples |
|---|---|---|
| **Public** | Safe to share externally | Open-source repos, published workshop materials |
| **Internal** | Not secret but not public | Drafts, research notes, planning docs |
| **Sensitive** | Business/client/personal data | Client info, business plans, unpublished work, contracts |
| **Critical** | Account-compromising or legally exposing | API keys, passwords, tokens, production credentials, financial records |

Rule: AI agents should not receive broad access to sensitive or critical folders
by default.

## 7. Secrets and Credential Audit

Search for: API keys, .env files, OAuth tokens, SSH keys, cloud credentials,
GitHub tokens, database URLs, private certificates, webhook secrets, service
account files, credentials pasted into notebooks or markdown files.

Best practices:
- Move secrets out of project files
- Use a password manager or secrets manager
- Rotate any credential that may have been exposed to an AI tool, Git repo,
  shared file, or cloud sync folder
- Add .env, key files, database dumps, and private config files to .gitignore
- Never let an agent "clean up" secrets automatically without backup + proposed
  change list
- Any discovered live credential should be treated as potentially exposed until
  rotated

## 8. Dependency and Supply-Chain Review

For each project, identify: package manager, dependency files, lock files,
outdated libraries, abandoned packages, unknown install scripts, post-install
hooks, local packages from GitHub/URLs, copied code snippets from unknown
sources, AI-generated code with unclear provenance.

Pay special attention to packages that: execute install scripts, request broad
filesystem access, call external URLs, handle authentication, process uploaded
files, parse untrusted input, run shell commands.

Treat dependencies like delegated code execution, not like passive libraries.

## 9. Sandbox Boundary Audit

Check whether your sandbox can: access full home folder, read Desktop/Documents/
Downloads/iCloud/Dropbox/Google Drive, access SSH keys, access browser cookies,
access password manager exports, call the internet, use cloud credentials, write
to real project folders, run destructive shell commands, push to GitHub, delete
files, modify system settings.

Recommended boundary:
```
Real local drive
    | limited copy only
Sandbox project folder
    | controlled test execution
Disposable runtime / container / virtual environment
    | reviewed output only
Manual promotion back to real project
```

Do not give an AI agent direct access to the original version of valuable work.
Give it a copy.

## 10. Agentic AI Permission Model

| Level | Name | Can Do | Cannot Do |
|---|---|---|---|
| 0 | Read-only assistant | Inspect selected files, advise | Write, execute, delete, install, push, call APIs |
| 1 | Drafting assistant | Generate proposed files/patches | Apply them directly |
| 2 | Sandbox editor | Write inside disposable copy | Access secrets, home dir, cloud, production, external APIs |
| 3 | Controlled executor | Run approved commands in sandbox | Unrestricted network/filesystem access |
| 4 | Production-adjacent operator | Affect GitHub, cloud staging, client data | Operate without hard policy gates, logs, approval, rollback |

For local projects, most agents should stay at Level 0-2.

## 11. High-Risk Action Classes

Require manual confirmation before any AI system performs:

- deleting files or folders
- running recursive commands
- changing permissions
- modifying .env, credentials, or SSH files
- installing packages globally
- changing shell profiles
- modifying Git history
- force-pushing
- calling external APIs with real credentials
- modifying cloud resources
- changing CI/CD workflows
- editing authentication or authorization code
- altering payment, billing, client, or legal records
- sending emails or messages externally
- syncing private data to cloud services

For these actions, the agent must produce: proposed action, files/resources
affected, expected result, second-order risks, rollback plan, evidence needed
before approval.

## 12. Consequence Prompting Policy

Before risky actions, ask the agent:

1. List direct, second-order, and third-order consequences
2. For each risk, identify the specific file, dependency, service, credential,
   user, or workflow affected
3. Separate verified risks from generic possible risks
4. List what evidence would confirm or dismiss each risk

The key distinction:
- Useful: "This script deletes /exports, which is used by the backup job in
  backup_config.yml."
- Weak: "This may cause data loss or operational disruption."

Generic risks are not evidence. Require the agent to tie each risk to a concrete
system component.

## 13. Deterministic Safety Gates

Add hard controls that do not rely on model judgment:

- read-only mode by default
- deny access to home directory
- deny access to cloud-sync folders
- deny access to secrets
- require allowlisted folders
- require allowlisted commands
- block destructive commands
- block outbound network calls unless approved
- block Git pushes unless approved
- require diffs before writes
- require backups before edits
- require tests before promotion
- require human approval for high-risk classes

The model should not be able to override these controls through prompting.

## 14. Local Project Security Checklist

### Repository hygiene
- .gitignore excludes secrets and generated sensitive files
- No credentials committed
- Branches are clean and understandable
- AI-generated changes reviewed before merge
- Large data files not accidentally tracked
- Repo remotes point to expected destinations

### Configuration hygiene
- Secrets not hardcoded
- Environment variables documented
- Defaults are safe
- Debug mode off unless needed
- Logging does not expose credentials or personal data

### Code hygiene
- Inputs validated
- Outputs sanitized
- File paths constrained
- Shell calls minimized
- External calls authenticated and rate-limited
- Error messages do not leak sensitive context
- Generated code treated as untrusted until reviewed

### Dependency hygiene
- Dependencies known and necessary
- Lock files present where appropriate
- Unused packages removed
- Vulnerable packages updated or justified
- Unknown install scripts reviewed

### Runtime hygiene
- Scripts run in virtual environment or container
- Project does not require admin privileges
- Network calls documented
- Temporary files cleaned safely
- Logs retained without exposing secrets

### AI-specific hygiene
- Agent memory does not store secrets
- Prompts do not include credentials
- Tool access is scoped
- Prompt injection risks considered when reading untrusted files
- Agent outputs validated before execution
- Agent cannot directly act on sensitive data without review

## 15. Evidence to Capture

For each audit run, save: date, projects reviewed, tools used, files scanned,
credentials discovered, dependencies reviewed, permissions reviewed, findings,
risk rating, remediation action, owner, status, residual risk, next review date.

## 16. Risk Rating Matrix

| Rating | Description | Action |
|---|---|---|
| **Critical** | Could expose secrets, compromise accounts, delete important data, affect clients, cause legal exposure | Stop, isolate, back up, rotate credentials, remediate before continuing |
| **High** | Could cause major project loss, leak sensitive data, break automation | Remediate before giving agents write or execution access |
| **Medium** | Could cause local breakage, inaccurate outputs, dependency risk | Remediate or document compensating control |
| **Low** | Minor hygiene issue with limited blast radius | Fix during normal cleanup |

## 17. Recommended Audit Deliverables

1. Asset inventory
2. Sensitive data map
3. Secrets exposure report
4. Dependency risk report
5. Agent permission matrix
6. Sandbox boundary diagram
7. High-risk action policy
8. Rollback and recovery plan
9. Remediation backlog
10. Residual risk statement

## 18. Practical Operating Rule

No AI agent gets direct write, delete, shell, cloud, GitHub, or API authority
over valuable assets unless:

1. the action is scoped
2. the action is reversible
3. the action is logged
4. the action is reviewed
5. the blast radius is known
6. secrets are excluded
7. rollback is available

## 19. Immediate Next Steps

1. Back up important project folders
2. Inventory all local AI projects and sandboxes
3. Search for secrets, .env files, tokens, and private keys
4. Separate real projects from disposable sandbox copies
5. Define what each AI tool is allowed to read, write, execute, and transmit

The most important shift is architectural: do not rely on the model to decide
what is safe. Build a local environment where unsafe actions are impossible,
contained, or require explicit approval before they can happen.
