---
name: advisory-audit
description: Non-blocking advisory audit for autopilot runs. Two modes -- "baseline" captures the start-of-run state, "report" generates the post-run advisory report. Neither mode can fail the run.
argument-hint: "baseline|report <run-id>"
allowed-tools: Read Edit Write Glob Grep Bash
---

# Advisory Audit

Non-blocking, best-effort advisory audit for sandbox autopilot runs. This
skill is called by the autopilot skill at two points:

1. `/advisory-audit baseline` -- immediately after BUILD_TRACKING.md is created
2. `/advisory-audit report <run-id>` -- after the mandatory tail, before Done

**Core rule: this skill cannot fail the autopilot run.** If anything errors,
log what you can and exit cleanly. Do not raise errors, do not output failure
markers, do not block the caller.

## Bash Command Rules (inherited from autopilot)

One command per Bash call. No `&&`, `;`, `for` loops, `cd && command`,
`source`, or `python3 -c`. Always.

---

## Mode: baseline

Capture the start-of-run state so the post-run report can identify what
changed during the run.

### Steps

1. Run `git rev-parse HEAD` and append the SHA to BUILD_TRACKING.md:
   ```
   ## Advisory Baseline
   baseline_sha: <the SHA output>
   ```

2. Run `mkdir -p docs/reports` (best-effort -- if it fails, skip the
   filesystem baseline and exit cleanly).

3. Run the sensitive-file scan and write output to the staging path:
   ```
   bash scripts/sensitive-file-scan.sh > docs/reports/advisory-filesystem-baseline.txt
   ```

If any step errors, skip the rest and exit cleanly. The report mode will
run in degraded mode (git-diff only) if the filesystem baseline is missing.

---

## Mode: report <run-id>

Generate the post-run advisory audit report. The `<run-id>` argument is
the run directory name under `docs/reports/` (e.g., `059`).

### Steps

1. Read the `baseline_sha` from the `## Advisory Baseline` section of
   BUILD_TRACKING.md. If missing, skip to Step 6.

2. Copy `docs/reports/advisory-filesystem-baseline.txt` into
   `docs/reports/<run-id>/advisory-filesystem-baseline.txt` for archival.
   If the staging file is missing, note this and continue without it.

3. Run `git diff --name-only --diff-filter=A <baseline_sha> HEAD` to find
   new tracked files. Filter for `.db`, `.sqlite`, `.sqlite3`, `.csv`,
   `.jsonl`, `.env*`, `.pem`, `.key`, `.p12`, `.pfx`, `.p8`, `.crt`,
   `credentials.json`, `*-credentials.json`, `*-service-account.json`,
   `.npmrc`, `.docker/config.json`, `kubeconfig`, `*.tfstate`,
   `*.tfstate.backup`, `*.tfvars`.

4. Re-run the filesystem scan:
   ```
   bash scripts/sensitive-file-scan.sh
   ```
   Diff the output against
   `docs/reports/<run-id>/advisory-filesystem-baseline.txt` to find new
   sensitive untracked/ignored files created during the run. If the
   baseline file is missing, list all current scan results instead.

5. Write the advisory audit report to
   `docs/reports/<run-id>/advisory-audit.md` with these sections:
   - New environment files
   - Newly tracked data files
   - New sensitive untracked/ignored files
   - Large databases (any `.db`/`.sqlite` over 10 MB)
   - New API-touching code (files with `fetch(`, `axios.`, `requests.`,
     `http.get`, `urllib`, `httpx`)
   - Git remotes / GitHub automation changes
   - Claude/agent config changes

6. If report generation fails at any point, try to append a one-line note
   to BUILD_TRACKING.md:
   ```
   ## Advisory Audit
   Advisory audit skipped: [reason]
   ```
   If that append also fails, exit cleanly anyway.
