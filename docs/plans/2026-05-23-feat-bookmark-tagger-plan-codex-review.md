## Blockers
- The SSRF mitigation is knowingly insufficient for the app’s highest-risk path. In `URL Fetching` ([lines 151-163]) the plan calls scheme-only validation “sufficient,” but that still allows `http://127.0.0.1`, `http://169.254.169.254`, RFC1918 ranges, redirect chains into internal hosts, and DNS rebinding. The `feed_forward.risk` and `Least confident` sections ([lines 6-8], [292]) correctly identify this as the top risk, but the plan does not actually close it or formally accept it as a non-goal for a strictly local-only app. That must be decided before coding starts.
- The acceptance tests are not implementation-ready and do not answer “how will we know it worked?” The EARS criteria in `Acceptance Tests` ([lines 237-249]) are partial, and the verification commands ([251-265]) are manual, flaky, and nondeterministic. They depend on live internet access to `example.com`, require hand-substituting `TOKEN`, and do not verify most stated behaviors. This is not directly translatable into reliable test cases.
- The CSRF design is underspecified and likely wrong as written. `CSRF Protection` says “generate token in before_request, validate on POST” ([206-212]). If a new token is generated on every request before validation, POST validation can fail or rotate unexpectedly. The plan needs an explicit token lifecycle: where it is stored, when it is created, when it rotates, and what response happens on mismatch.
- The plan contains an architecture contradiction that will cause drift during implementation. The file tree says `__init__.py` handles “blueprint registration” ([51]), while `Key decisions` says “No blueprints” ([63]). That is a small app-level detail, but it is exactly the kind of inconsistency that turns into “figure it out while coding.”

## Concerns
- The plan over-focuses on SQL injection prevention for `/delete/<int:id>` ([133]) and under-specifies the real query surfaces. `Search` ([200-204]) says “LIKE with proper escaping,” but it does not explicitly require parameterized queries, define how `q` and tag filters compose, or say whether matching is case-insensitive.
- The EARS coverage is incomplete. Missing cases include: invalid/missing CSRF token, URL over 2048 chars, tag count over 20, tag length over 50, duplicate tags with case differences, non-HTML responses, bad charset headers, redirect behavior, delete of a nonexistent id, and verification that bookmark deletion removes join rows.
- `PRAGMA journal_mode=WAL` is being set in `get_db()` on every connection ([105-110]) even though the plan earlier says initialization should happen once at startup ([98]). That is the wrong level of abstraction. `foreign_keys=ON` belongs per connection; WAL mode usually belongs in initialization/setup.
- Silent truncation and silent dropping of tags ([222-223]) is a weak product decision. It creates invisible data mutation and makes debugging user reports harder. Either reject with a clear message or at least flash a warning.
- The “Hardest decision” in `Feed-Forward` ([290-291]) does not look like the hardest decision. Normalized tags vs flat text is an easy call once tag filtering exists. The hard decisions are fetch safety, deterministic testing, and whether server-side metadata fetching is worth the security/operational cost at all.
- The rejected alternatives list ([291]) is incomplete. The obvious simpler alternative is “don’t fetch remote metadata on the server.” Let the user enter title manually, or fetch client-side in the browser. That removes most of the security and test complexity.
- Observability is too thin. The plan has no logging or counters for fetch failures, CSRF failures, validation rejects, or slow fetches. If metadata fetching stops working in production-like use, you will not know whether it is network, parsing, content type, or blocking.
- The plan does not state what happens to orphaned tags after bookmark deletion. The join rows cascade, but unused tags remain unless explicitly cleaned. That is a product/data behavior decision and should not be left implicit.

## Suggestions
- Add a real quality gate section that explicitly answers the four questions in one place:
  “What changes,” “what must not change,” “how success is verified,” and “most likely failure mode.”
- Rewrite `Acceptance Tests` into deterministic, executable cases. Use a local fixture server or mocked `fetch_meta` responses for HTML, non-HTML, timeout, redirect, charset, and failure cases. Include concrete commands or test names for every EARS statement.
- Specify the CSRF contract precisely: token stored in session, rendered in hidden input, validated against session value on POST, and mismatch behavior (`400`/`403` plus message).
- Clarify search behavior: whether `q` and tag filter are combined with `AND`, whether search is case-insensitive, how `%` and `_` are escaped, and whether clicking a tag preserves the current `q`.
- Move WAL configuration into `init_db()` or first-run database setup. Keep `foreign_keys=ON` in `get_db()` per connection.
- Decide whether orphan tags should be cleaned up. If yes, add the delete behavior and a test. If no, state that explicitly.
- If the goal is truly “keep it minimal,” cut scope by removing server-side metadata fetch entirely or making it best-effort behind a clearly documented local-only assumption. That is the largest simplification available.

## Open Questions
- Is this app guaranteed to run only on a developer’s laptop, or must it still be safe if someone exposes it on `0.0.0.0`?
- Should redirects be followed? If yes, what validation happens after each redirect hop?
- What is the expected behavior for orphan tags after the last associated bookmark is deleted?
- Should over-limit tags be rejected, truncated with warning, or silently modified?
- How do `q` and tag filters interact: `AND` or `OR`?
- Is blank metadata acceptable whenever parsing fails, or do you want any fallback extraction behavior beyond `<title>` and `<meta name="description">`?
- Are tests expected to run offline/in CI, or is live internet access considered acceptable?

## Claude Code Fix Prompt
```md
Revise this plan so it is implementation-ready. Focus on the following issues and update the relevant sections directly.

1. Fix the SSRF gap in `URL Fetching` (around lines 151-163) and `Feed-Forward` (around line 292).
- Either:
  - explicitly scope the app as local-only/dev-only and state that scheme-only validation is an accepted non-goal for wider exposure, or
  - add a real SSRF policy: block localhost, loopback, RFC1918, link-local, metadata IPs, and validate redirect targets on every hop.
- Update acceptance tests to cover the chosen policy.

2. Rewrite `Acceptance Tests` and `Verification Commands` (around lines 235-265).
- Keep EARS style, but make every requirement directly translatable into a deterministic test.
- Do not depend on `example.com` or any live external site.
- Add verification for:
  - valid add with fetched metadata
  - add when fetch fails
  - non-http/https rejection
  - non-HTML response handling
  - CSRF failure
  - tag normalization/deduplication/limits
  - search by title, URL, and tag
  - tag click filter behavior
  - delete cascade on `bookmark_tags`
- Provide exact commands or test names with expected outcomes.

3. Specify the CSRF lifecycle in `CSRF Protection` (around lines 206-212).
- State where the token is stored, when it is created, whether it rotates, how it is rendered, and what happens on mismatch.
- Remove the ambiguity created by “generate token in before_request, validate on POST.”

4. Resolve the architecture inconsistency between the file tree and `Key decisions` (around line 51 vs line 63).
- If there are no blueprints, remove blueprint references.
- If routes live in `app/__init__.py`, say so explicitly, or add a route module and document it.

5. Add missing implementation details that would otherwise be decided during coding.
- In `Search`, define:
  - parameterized SQL requirement
  - case sensitivity
  - escaping rules for `%` and `_`
  - whether `q` + tag filter are combined with `AND`
  - result ordering
- In delete behavior, define whether unused tags are left behind or cleaned up.

6. Tighten the database section.
- Move `PRAGMA journal_mode=WAL` out of per-request `get_db()` and into initialization/setup.
- Keep `PRAGMA foreign_keys = ON` per connection.
- Add any needed indexes if search/filter performance matters even modestly.

7. Improve `Feed-Forward`.
- Replace the current “Hardest decision” if needed; the real hard tradeoff is likely fetch safety/testing complexity, not schema normalization.
- Make “Least confident” actionable: what will be verified first, and what decision depends on that result.
- Expand rejected alternatives to include the simpler option of not doing server-side metadata fetching at all.

Keep the plan minimal, but remove ambiguity. The result should be something an implementer can execute without inventing behavior mid-flight.
```
