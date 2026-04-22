---
title: "Lead Scraper V2 Phase 2: Opener Quality + Security Hardening"
date: 2026-04-21
project: lead-scraper
phase: plan
branch: feat/v2-phase2-opener-security
base: master
feed_forward:
  risk: "Haiku may over-index on contrastive FAIL examples and avoid the good patterns too. If benchmark regresses after adding FAILs, remove them and try rules-only approach."
  verify_first: true
---

## Plan Quality Gate

1. **What exactly is changing?** The opener system prompt (4 fixes), CSV import sanitization, Flask CSRF protection, and CSV phone column warning.
2. **What must NOT change?** Existing test suite (137 passing). Enrichment pipeline behavior. Campaign CRUD and queue workflow. Export CSV sanitization (already working).
3. **How will we know it worked?** Opener benchmark passes 4/5. New tests cover CSV injection and CSRF. All 139+ tests pass.
4. **Most likely way this plan is wrong?** Haiku is brittle with too many rules -- adding Fixes A-D all at once may degrade quality in other dimensions (e.g., openers become stiff/over-cautious). Mitigated by incremental benchmarking.

## Decision: Incremental Opener Benchmarking

Apply fixes one at a time, re-run 5-lead benchmark after each. Stop when 4/5 pass. This tells us which fix actually helped and avoids the brainstorm Feed-Forward risk of "over-correcting with too many rules."

Order: A (banned words) -> B (conversation-opening rule) -> C (contrastive FAIL example) -> D (stat-echo FAIL example). Rationale: A is cheapest (one line), B adds a rule, C and D add prompt length (Haiku context cost).

## Section 1: Opener Prompt Rewrite

**File:** `campaign.py` lines 125-145 (`_OPENER_SYSTEM_PROMPT`)

### Fix A: Banned Words

Add after rule 5:

```
6. NEVER use these words: "impressive", "amazing", "incredible", "remarkable", "inspiring". Use specific observations.
```

### Fix B: Conversation-Opening Rule

Add after rule 6:

```
7. End with something that implies shared context or curiosity -- not a compliment. Good: "the Dalida revival alone was worth showing up for." Bad: "that was really well done."
```

### Fix C: Contrastive FAIL Example (dead-end compliment)

Add after the existing 3 INPUT/OUTPUT pairs:

```
FAIL (dead-end compliment, do NOT write like this): Madison, Operation Max Wave was impressive — doubling engagement over four months takes real strategy.
WHY FAIL: "impressive" is filler. Echoes the stat. Ends as a compliment with no conversation hook.
PASS: Madison, the way Max Wave played the long game on socials reminded me of how album rollouts used to work. Four months is a real commitment.
```

### Fix D: Contrastive FAIL Example (stat echo)

Add after Fix C:

```
FAIL (stat echo, do NOT write like this): Pat, getting 30 muralists and 2,000 people to Barrio Logan is no small feat.
WHY FAIL: Copies the numbers directly from the hook. Reads like a LinkedIn comment.
PASS: Pat, the Barrio Logan Art Walk had a different energy this October. Walking through that many murals in one stretch changes how you see the neighborhood.
```

### Benchmark Protocol

After each fix (A, B, C, D):
1. Run the same 5 synthetic leads through `_generate_opener()`
2. Score against the 4-criterion rubric
3. Record scores in a benchmark log
4. If 4/5 pass, stop adding fixes -- remaining ones are unnecessary
5. If still failing after all 4, escalate: prompt may need structural change (out of scope)

## Section 2: CSV Formula Injection on Import

**File:** `ingest.py` line 97-98

**Problem:** Raw CSV values are read and stored without sanitization. A malicious CSV with `=HYPERLINK("http://evil.com","Click")` in the bio field gets stored verbatim and later exported (where `sanitize_csv_cell` catches it). But the bio is also displayed in the Flask UI, and stored in the DB as-is.

**Solution:** Apply `sanitize_csv_cell()` to all string values during import, before storing.

**Change:** In `import_from_csv()`, after line 97:
```python
val = (row.get(csv_col) or "").strip()
if val:
    mapped[field_name] = sanitize_csv_cell(val)
```

**Why at import, not just export:** Defense in depth. The DB should not contain formula-injection payloads. The Flask UI renders bio text -- if it ever renders without escaping, the payload is live.

## Section 3: CSRF on Flask Delete Endpoint

**File:** `app.py` line 72-75

**Problem:** `POST /leads/<id>/delete` has no CSRF protection. An attacker can craft a form on another page that submits to this endpoint, deleting leads.

**Decision:** Manual `X-Requested-With` header check (not Flask-WTF). Rationale: the app has one state-changing endpoint, no forms with tokens, and Flask-WTF adds a dependency + template changes for a single POST route. The gig-lead-responder CSRF doc confirms this pattern works.

**Change:**
```python
@app.post("/leads/<int:lead_id>/delete")
def delete(lead_id):
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return "CSRF check failed", 403
    delete_lead(lead_id)
    return redirect(url_for("index"))
```

**Frontend change:** The delete button/link must send the header. If it's currently a `<form>` POST, convert to a `fetch()` call with the header. Check `templates/index.html` for the current implementation.

## Section 4: CSV Phone Column Warning

**File:** `ingest.py` in `import_from_csv()`

**Problem:** Users put phone numbers in their CSV, but `ingest_leads()` doesn't write phone (it's an enrichment column). The phone data is silently dropped, confusing users.

**Change:** After header mapping, check if any CSV column maps to a known-but-ignored field:

```python
ignored_columns = {"phone"}
mapped_fields = set(header_map.values())
ignored_present = ignored_columns & {h.lower().strip() for h in (reader.fieldnames or [])}
if ignored_present:
    print(f"Note: {', '.join(ignored_present)} column(s) found but not imported. "
          f"Phone numbers come from the enrichment pipeline, not CSV import.")
```

## Implementation Order

1. Fix A (banned words) -> benchmark -> commit
2. Fix B (conversation rule) -> benchmark -> commit (if needed)
3. Fix C (contrastive FAIL) -> benchmark -> commit (if needed)
4. Fix D (stat echo FAIL) -> benchmark -> commit (if needed)
5. CSV import sanitization -> test -> commit
6. CSRF protection -> test -> commit
7. Phone column warning -> test -> commit

Commits ~50-100 lines each. Run full test suite after every commit.

## Acceptance Tests

### Happy Path
- WHEN 5 synthetic leads are processed through _generate_opener() THE SYSTEM SHALL produce openers where at least 4/5 pass the rubric (Alex voice, hook-specific, 1-2 sentences, opens conversation)
- WHEN a CSV file with clean data is imported THE SYSTEM SHALL insert leads and sanitize all string values via sanitize_csv_cell()
- WHEN a user clicks delete on a lead via the web UI THE SYSTEM SHALL include X-Requested-With header and successfully delete
- WHEN a CSV with a "phone" column is imported THE SYSTEM SHALL print a warning explaining phone comes from enrichment

### Error Cases
- WHEN a CSV cell contains "=HYPERLINK(...)" in the bio field THE SYSTEM SHALL store it with a leading apostrophe prefix ("'=HYPERLINK(...)")
- WHEN a POST to /leads/1/delete lacks the X-Requested-With header THE SYSTEM SHALL return 403 and not delete the lead
- WHEN a CSV cell starts with "+", "-", "@", or "|" THE SYSTEM SHALL prefix with apostrophe on import

### Verification Commands
- `./venv/bin/python -m pytest tests/ -v` -- all tests pass (139+)
- Opener benchmark script (inline in work session) -- 4/5 pass
- `curl -X POST http://127.0.0.1:5000/leads/1/delete` -- returns 403
- `curl -X POST http://127.0.0.1:5000/leads/1/delete -H "X-Requested-With: XMLHttpRequest"` -- returns 302

## Codex Handoff Prompt

```
You are working on the lead-scraper project (~/Projects/sandbox/lead-scraper).
Branch: feat/v2-phase2-opener-security (create from master).

Read these files for context:
- docs/plans/2026-04-21-lead-scraper-v2-phase2-plan.md (this plan)
- docs/brainstorms/2026-04-21-lead-scraper-v2-phase2-brainstorm.md (benchmark results)
- campaign.py (opener prompt at _OPENER_SYSTEM_PROMPT)
- ingest.py (import_from_csv function)
- app.py (Flask delete endpoint)
- utils.py (sanitize_csv_cell)

Implement Sections 1-4 in the order specified. For Section 1, apply fixes
incrementally with benchmarking after each (requires ANTHROPIC_API_KEY from .env).
Run pytest after every commit. Target: 139+ tests passing, opener benchmark 4/5.
```

## Feed-Forward

- **Hardest decision:** Incremental vs all-at-once opener fixes. Chose incremental because the brainstorm Feed-Forward explicitly warned about Haiku brittleness with too many rules. Slower but diagnostic.
- **Rejected alternatives:** Flask-WTF for CSRF (too heavy for one endpoint). Sanitizing at display time only (defense in depth says sanitize at storage too). Skipping the CSRF fix ("it's just a local tool" -- but security review flagged it and we fix what we flag).
- **Least confident:** Whether the X-Requested-With CSRF check works with the existing delete UI. Need to check `templates/index.html` to see if delete is a form POST or a link. If it's a form, converting to fetch() is more work than expected.
