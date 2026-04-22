---
title: "V2 Phase 2: Incremental Opener Benchmarking + Security Hardening"
date: 2026-04-21
project: lead-scraper
phase: compound
tags: [prompt-engineering, benchmark, csrf, csv-sanitization, incremental-testing, haiku]
problem: Opener generation scored 2/5 on quality rubric. Flask delete had no CSRF protection. CSV import stored unsanitized formula payloads.
resolution: Two prompt rules fixed opener to 5/5. X-Requested-With CSRF check on delete. sanitize_csv_cell() at import time.
feed_forward:
  risk: "Opener benchmark used synthetic leads only. First real campaign may reveal patterns the synthetic set didn't cover."
  verify_first: true
---

## Context

PR #4 (`feat/v2-phase2-opener-security`) addressed the opener quality failure from the Phase 2 brainstorm benchmark plus 3 security/UX items from the Phase 1 review P3 deferrals.

## Pattern 1: Incremental LLM Prompt Benchmarking

**Problem:** Opener generation scored 2/5 on a 4-criterion rubric (Alex voice, hook-specific, 1-2 sentences, opens conversation). Three failure patterns: hook parroting, "impressive" filler word repetition, dead-end compliments.

**Approach:** Apply fixes one at a time, re-benchmark after each, stop when the threshold is met. Four fixes were planned in cost order:
- Fix A: Banned words list (1 line)
- Fix B: Conversation-opening rule (1 line)
- Fix C: Contrastive FAIL/PASS example for dead-end compliments
- Fix D: Contrastive FAIL/PASS example for stat echoing

**Result:**
- Fix A alone: still 2/5 (banned words didn't address the root cause)
- Fix A+B: **5/5 pass** (conversation-opening rule was the key fix)
- Fixes C and D: never needed

**Lesson: The simplest behavioral rule beat the sophisticated technique.** The contrastive pair pattern (from gig-lead-responder) was the plan's "best bet," but a one-line rule ("End with something that implies shared context or curiosity, not a compliment") solved the entire problem. The model already knew how to write good openers -- it just needed to be told not to end with compliments.

**Lesson: Banned words are necessary but not sufficient.** Removing "impressive" didn't improve scores because the model found other generic filler words. The root cause was structural (dead-end compliments), not vocabulary.

**Lesson: Incremental benchmarking saves prompt bloat.** If we'd applied all 4 fixes at once, we'd have a prompt with 2 unnecessary contrastive examples adding ~200 tokens per call. At scale (thousands of leads), that's real cost with zero benefit.

**Reusable benchmark protocol:**
1. Define rubric with pass/fail criteria per output
2. Establish baseline score
3. Order fixes by cost (lines added, tokens consumed)
4. Apply one fix, re-run same inputs, record score
5. Stop when threshold met -- remaining fixes are unnecessary

## Pattern 2: CSRF via X-Requested-With on Single-Endpoint Flask Apps

**Problem:** `POST /leads/<id>/delete` had zero CSRF protection. Any cross-origin form could delete leads.

**Solution:** Check `X-Requested-With: XMLHttpRequest` header. Convert the HTML form to a `fetch()` call with the header. Return 403 without header, 204 with header.

**Why not Flask-WTF:** One state-changing endpoint doesn't justify a full CSRF library with session tokens and template macros. The X-Requested-With check works because browsers block custom headers on cross-origin simple requests.

**Implementation detail:** The delete button was a `<form method="post">` -- converting to `fetch()` required adding a small inline `<script>` with a `confirm()` dialog. The `onclick` handler calls `fetch()` with the header, then `location.reload()` on success.

**Limitation (documented by review):** If CORS is ever loosened or XSS exists on the same origin, this check is bypassable. Upgrade to Flask-WTF if the app goes on-network.

## Pattern 3: CSV Sanitization at Import Time (Defense in Depth)

**Problem:** CSV values were stored raw in SQLite. A malicious bio like `=HYPERLINK("http://evil.com","Click")` would be stored verbatim.

**Solution:** Apply `sanitize_csv_cell()` to all string values during `import_from_csv()`, before DB storage. The same function already runs at export time.

**Why both import AND export:** Defense in depth. The DB should not contain formula-injection payloads because:
1. The Flask UI displays bios directly (Jinja2 autoescaping prevents XSS, but not formula interpretation)
2. Future export paths might skip `sanitize_csv_cell()`
3. The apostrophe prefix (`'`) is not in the dangerous character set, so double-application is idempotent

**Review finding (validated as non-issue):** The learnings researcher flagged double-sanitization risk. Verified that `'` (the prefix character) is not in the dangerous set `{=, -, +, @, |}`, so re-sanitizing a prefixed value is a no-op.

## Pattern 4: Warn on Ignored CSV Columns

**Problem:** Users put phone numbers in their CSV and expect them to be imported. But phone is an enrichment column (populated by bio parsing, Hunter.io, venue scraper). The data was silently dropped.

**Solution:** Check if `"phone"` appears in the CSV headers and print a message: "Phone numbers come from the enrichment pipeline."

**Simplicity lesson (from review):** First implementation used a `set` intersection pattern to handle multiple ignored fields (YAGNI). Simplified to a direct `"phone" in {headers}` check after code simplicity review flagged it.

## Verification

- Opener benchmark: 5/5 pass (up from 2/5 baseline)
- Tests: 142 passing (up from 139 baseline, +3 new tests)
- 4-agent review: 0 P1s, 3 P2s (all accepted or fixed), 4 P3s (1 fixed, 3 deferred)

## Feed-Forward

- **Hardest decision:** Whether to apply all 4 opener fixes at once or incrementally. Incremental was slower but proved only 2 of 4 were needed, saving ~200 tokens per API call at scale.
- **Rejected alternatives:** Flask-WTF for CSRF (too heavy for one endpoint). Sanitizing only at export (leaves DB dirty). Applying all prompt fixes without benchmarking (would've added unnecessary complexity).
- **Least confident:** Opener benchmark used 5 synthetic leads. Real campaign leads may have hooks that trigger different failure patterns not covered by the synthetic set. First real campaign should re-run the benchmark with production data.
