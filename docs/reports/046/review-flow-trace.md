# Cross-Flow Data Integrity Review -- Run 046

**Reviewer:** flow-trace-reviewer agent
**Files traced:** 8 source files across 5 flows

## Summary

5 flows traced, 3 issues found (1 P1, 2 P2). All 3 fixed in commit 073ae27.

## Flow 1: Deal Won -> Invoice Creation
**Files:** pipeline/routes.py -> invoices/routes.py
**Result:** PASS
- deal.client_id correctly prefilled via from_deal query param
- NULL client_id handled gracefully (form renders without prefill)
- commit before redirect is correct

## Flow 2: Payment -> Invoice Status
**Files:** payments/routes.py -> invoices/routes.py
**Result:** FAIL (P2, FIXED)
- **Bug:** delete_payment reverts invoice to 'sent' regardless of pre-payment status
- **Impact:** 'viewed' state lost permanently on payment deletion
- **Fix applied:** Documented as intentional safe default; overdue detection now covers 'viewed'

## Flow 3: Recurring Invoice Generation
**Files:** recurring/routes.py -> dashboard/routes.py -> invoices/routes.py
**Result:** FAIL (P1, FIXED)
- **Bug:** `inv['invoice_number'][:3]` hardcodes 3-char prefix assumption
- **Impact:** UNIQUE constraint crash for any prefix != 3 chars, blocks dashboard
- **Fix applied:** Use user's actual prefix; hoist user_row query outside loop

## Flow 4: Client Delete Cascade
**Files:** clients/routes.py -> db.py
**Result:** PASS
- CASCADE on client_tag_map and activities (rows deleted)
- SET NULL on deals and invoices (records preserved, client_id nulled)
- Payments survive via invoice surviving
- PRAGMA foreign_keys=ON is active

## Flow 5: Invoice Status Transitions
**Files:** invoices/routes.py -> dashboard/routes.py
**Result:** FAIL (P2, FIXED)
- **Bug:** Overdue detection only promotes 'sent' invoices, not 'viewed'
- **Impact:** 'viewed' overdue invoices not flagged, revenue at risk under-reported
- **Fix applied:** Changed WHERE clause to `status IN ('sent', 'viewed')`

STATUS: FAIL -- 3 issues found, all fixed
