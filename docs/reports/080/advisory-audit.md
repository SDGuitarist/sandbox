# Advisory Audit — Run 080

**Run ID:** 080
**Date:** 2026-06-30
**Baseline SHA:** 85be609d50bf35b18df9ac4f9f16475f8adea7ba
**Mode:** report (post-tail)
**Scan status:** Partially degraded — sensitive-file-scan.sh FIREBREAK_DEFERRED (bash indirection classifier; expected under phase=tail active firebreak; NOT an FC58 regression — sensitive-file-scan.sh is not in TRUSTED_PIPELINE_SCRIPTS allowlist)

---

## New Environment Files

None. No `.env*` files were added in the diff from baseline to HEAD.

---

## Newly Tracked Data Files

None. Filtered new tracked files against sensitive extensions:
`.db`, `.sqlite`, `.sqlite3`, `.csv`, `.jsonl`, `.pem`, `.key`, `.p12`, `.pfx`, `.p8`, `.crt`, `credentials.json`, `.npmrc`, `.tfstate`, `.tfvars`.

New tracked files this run (all clean):
- `docs/brainstorms/2026-06-30-shelftrack-brainstorm.md`
- `docs/plans/2026-06-30-shelftrack-reading-list.md`
- `docs/reports/080/*.md` (16 report files)
- `shelftrack/__init__.py`, `auth.py`, `auth_utils.py`, `books.py`, `database.py`, `models.py`
- `shelftrack/static/style.css`
- `shelftrack/templates/auth/login.html`, `register.html`
- `shelftrack/templates/base.html`, `books/form.html`, `books/list.html`

---

## New Sensitive Untracked/Ignored Files

**DEGRADED** — `scripts/sensitive-file-scan.sh` was FIREBREAK_DEFERRED during this tail scan pass. The filesystem baseline from run start is archived at `docs/reports/080/advisory-filesystem-baseline.txt` but a live diff was not possible.

Advisory note: Under active G1 firebreak at phase=tail, ad-hoc bash script invocations defer via the indirection classifier unless the script basename is in TRUSTED_PIPELINE_SCRIPTS. The sensitive-file-scan.sh script is not a named pipeline script, so its deferral is correct governance behavior. A manual scan should be run post-teardown if sensitive file verification is required.

---

## Large Databases

None detected in the new tracked files. No `.db` or `.sqlite` files were added.

Manual check: `shelftrack/database.py` uses `sqlite3.connect('shelftrack.db')` — the database file is created at runtime and is correctly gitignored (not in tracked files). No size concern during this build run.

---

## New API-Touching Code

None. `grep` for `fetch(`, `axios.`, `requests.`, `http.get`, `urllib`, `httpx` across `shelftrack/` returned zero matches. ShelfTrack is a pure Flask+SQLite CRUD app with no outbound HTTP calls.

---

## Git Remotes / GitHub Automation Changes

No changes. Remote `origin` unchanged (`https://github.com/SDGuitarist/sandbox.git`). No new `.github/` workflow files were added.

---

## Claude/Agent Config Changes

None. No files in `.claude/` were added or modified between baseline and HEAD.

---

## Summary

| Category | Finding |
|----------|---------|
| New env files | None |
| Sensitive tracked files | None |
| Sensitive untracked files | DEGRADED (scan deferred by firebreak — archive baseline available) |
| Large databases | None |
| API-touching code | None |
| Git remote changes | None |
| Claude/agent config changes | None |

**Advisory verdict:** Clean. No sensitive data artifacts, no outbound API calls, no config drift. The one degraded check (sensitive-file-scan.sh FIREBREAK_DEFERRED) is expected under active firebreak governance and does not indicate a security concern for this build (ShelfTrack has no credentials, secrets, or external integrations).
