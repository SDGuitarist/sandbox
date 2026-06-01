# Data Inventory — Sandbox Autonomy Hardening

**Date:** 2026-06-01
**Plan:** docs/plans/2026-05-13-feat-sandbox-autonomy-hardening-plan.md
**Purpose:** Classify all tracked and on-disk data files before applying gitignore changes.

## Tracked Data Files

| File path | Size | Classification | Notes |
|-----------|------|----------------|-------|
| `email_classifier_results.jsonl` | 37 KB | Generated | LLM eval output with synthetic email scenarios. Names/emails are fabricated. |
| `eval-harness/reports/2026-05-23-2217.jsonl` | 22 KB | Generated | Eval harness scenario results. LLM-generated code, no user data. |
| `eval-harness/reports/2026-05-23-2218.jsonl` | 1.1 MB | Generated | Eval harness scenario results. |
| `eval-harness/reports/2026-05-24-1336.jsonl` | 1.8 MB | Generated | Eval harness scenario results. |
| `eval-harness/reports/2026-05-24-2049.jsonl` | 1.8 MB | Generated | Eval harness scenario results. |
| `eval-harness/reports/2026-05-24-2142.jsonl` | 90 KB | Generated | Eval harness scenario results. |
| `file_upload_service/uploads.db` | 36 KB | Safe | Small SQLite DB — likely empty schema or minimal test data for demo app. |
| `lead-scraper/sd_candidates_enriched.csv` | 16 KB | **Sensitive** | Contains real business names, emails, phone numbers, and websites scraped from San Diego businesses. |
| `lead-scraper/tests/fixtures/venue_outreach.csv` | 578 B | Safe | Test fixture with synthetic data (Studio A, 555-1234). |
| `url_health_monitor/health_monitor.db` | 28 KB | Safe | Small SQLite DB for URL health checks. Likely contains only URLs, no PII. |
| `venue-scraper/results/master_outreach.csv` | 1.7 KB | **Sensitive** | Contains real business names, emails, and websites scraped from venues. |

### Summary: 2 tracked files classified as Sensitive

- `lead-scraper/sd_candidates_enriched.csv` — real scraped contact data
- `venue-scraper/results/master_outreach.csv` — real scraped contact data

Both contain business contact information obtained from public web sources. Not PII in the privacy-regulation sense, but real contact data that should not be in a git-tracked sandbox repo.

## Untracked .env Files on Disk (with real credentials)

**WARNING:** The following `.env` files exist on disk and contain real API keys and secrets. None are tracked by git. All should be treated as potentially exposed per the sandbox secrets policy (agents run with `dangerouslySkipPermissions: true`).

| File path | Tracked? | Contains real credentials? | Notes |
|-----------|----------|---------------------------|-------|
| `.env` (root) | No | Yes | Anthropic API key |
| `lead-scraper/.env` | No | Yes | Apify, Hunter, Perplexity, Anthropic API keys + email |
| `venue-scraper/.env` | No | Yes | SerpAPI, Anthropic API keys |
| `workshop-registration/.env` | No | Yes | Flask secret key, admin password |
| `writers-room-council/.env.local` | No | Yes | Supabase URL + keys (including service_role), Anthropic API key |

**Recommendation:** All credentials in these files should be treated as potentially exposed and rotated if they have real value. The sandbox secrets policy says dev-only low-limit keys are acceptable; production/billing keys are not.

## Untracked Database Files on Disk

| Location | Count | Notes |
|----------|-------|-------|
| `lead-scraper/leads.backup-*.db` | ~130 files | Database backups. May contain scraped lead data (business names, emails, phones). |
| `lead-scraper/leads.db` | 1 | Active database. Contains scraped lead data. |
| Various app `instance/*.db` | ~8 files | Flask app instance databases (command-center, restaurantops, intake-dashboard, venueconnect, invoice-crm, gigsheet, cpaa-shadow-lab, client-music-planner). Likely dev/test data. |
| Other app `.db` files | ~7 files | bookmark-manager, job-queue, task_scheduler, webhook-delivery, project-tracker, workshop-registration, api-key-manager, coworkflow, recipe-organizer, url-shortener, task-tracker. Dev/test data. |

None of these are tracked by git. The lead-scraper backups are the largest concern — 130+ backup files likely containing real business contact data.

## Untracked CSV Files on Disk

| File path | Notes |
|-----------|-------|
| `lead-scraper/leads.csv` | Likely export of scraped leads — real contact data |
| `lead-scraper/san_diego_leads.csv` | Scraped San Diego leads |
| `lead-scraper/sd_attendees.csv` | Scraped attendee data |
| `lead-scraper/sd_promoters.csv` | Scraped promoter data |

None tracked. All likely contain real scraped business contact information.

## Untracked Results Directories

| Directory | Contents |
|-----------|----------|
| `venue-scraper/results/` | Multiple CSV/JSONL files with scraped venue data (batch2, batch3, batch3c subdirs, contacts.jsonl, outreach.csv) |

One file from this directory IS tracked: `venue-scraper/results/master_outreach.csv` (classified Sensitive above).

## Key and Certificate Files

None found (tracked or untracked). Clean.

## Credential/Config Files

None found (no `.npmrc`, `credentials.json`, `service-account.json`, `.tfstate`, `kubeconfig`). Clean.

## Classification Summary

| Category | Tracked | Untracked |
|----------|---------|-----------|
| **Sensitive** | 2 files (lead-scraper CSV, venue-scraper CSV) | 5 .env files, 130+ lead-scraper .db backups, ~4 CSVs, results directory |
| **Generated** | 6 files (eval harness reports, email classifier) | 0 |
| **Safe** | 3 files (test fixture, small DBs) | ~15 app databases (dev/test data) |
| **Unknown** | 0 | 0 |

## Decisions Needed (Human Review)

1. **Tracked sensitive files (2 files):** `lead-scraper/sd_candidates_enriched.csv` and `venue-scraper/results/master_outreach.csv` are tracked and contain real contact data. Per the plan, these require a separate human-approved remediation plan before untracking. Options:
   - Untrack with `git rm --cached` (keeps on disk, removes from git)
   - Assess whether git history cleanup is needed
   - Decide if this data matters enough to warrant history rewriting

2. **Untracked .env files with real credentials:** These are not a git problem but a sandbox safety problem. Per the secrets policy, credentials used in a `dangerouslySkipPermissions` sandbox should be treated as potentially exposed. Decide whether to rotate them.

3. **Lead-scraper backup database accumulation:** 130+ `.db` backup files in `lead-scraper/`. Not tracked, but they represent significant unmanaged data on disk. Not blocking for this plan, but worth noting.
