---
status: pending
priority: p2
issue_id: "011"
tags: [code-review, architecture, quality]
---

# Unify 5 Duplicated Persist/UPDATE Functions

## Problem Statement
Five locations in `enrich.py` do the same COALESCE-based UPDATE on the leads table: `_persist_enrichment`, `_persist_bio_enrichment`, `_persist_hunter_result`, plus 2 inline SQL blocks in `enrich_websites_deep` and `enrich_with_venue_scraper`. Each new enrichment step copy-pastes the pattern.

## Findings
- **Source:** Architecture Strategist + Simplicity Reviewer
- **File:** `enrich.py` lines 102, 202, 382, 566, 711
- **Evidence:** All do `UPDATE leads SET email = COALESCE(email, :email)...` with minor column differences.

## Proposed Solution
Extract single `_persist_lead_update(lead_id, updates, db_path)` that handles all enrichment columns. All 5 callers become one-line calls. Removes ~60 lines.

## Acceptance Criteria
- [ ] Single persist function handles email, phone, website, social_handles
- [ ] All 5 existing persist sites replaced
- [ ] COALESCE behavior preserved (never overwrite existing data)
- [ ] All 91 tests pass
