---
status: resolved
priority: p2
issue_id: "005"
tags: [code-review, architecture]
---

# Email Engine Fabricates Non-Functional Checkout URLs

## Problem Statement
`app/email/engine.py:118-122` constructs `https://amplifyai.to/checkout/{order_id}` which is not a real Square checkout URL. Promoted waitlist registrants and payment-failed registrants receive broken links.

## Proposed Solution
Use the Square redirect base URL from env var to construct the registration page URL instead, or store the actual `checkout_url` in the registrants table.

Simplest fix: point to the registration page instead: `f"{os.environ.get('SQUARE_REDIRECT_BASE', 'http://localhost:3000')}/register"` with a message to re-register.

## Acceptance Criteria
- [ ] Email checkout URLs point to a functional page
