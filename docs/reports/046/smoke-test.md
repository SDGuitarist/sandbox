# Smoke Test Report -- Run 046

## Results

20/20 routes tested. All passed.

### Unauthenticated Routes
| Method | Path | Expected | Actual | Status |
|--------|------|----------|--------|--------|
| GET | /auth/login | 200 | 200 | PASS |
| GET | /auth/register | 200 | 200 | PASS |
| GET | / | 302 | 302 | PASS |
| GET | /clients/ | 302 | 302 | PASS |
| GET | /pipeline/ | 302 | 302 | PASS |
| GET | /invoices/ | 302 | 302 | PASS |
| GET | /catalog/ | 302 | 302 | PASS |
| GET | /reports/ | 302 | 302 | PASS |
| GET | /settings/ | 302 | 302 | PASS |
| GET | /search/?q=test | 302 | 302 | PASS |

### Auth Flow
| Action | Expected | Actual | Status |
|--------|----------|--------|--------|
| POST /auth/register | 302 | 302 | PASS |
| POST /auth/login | 302 | 302 | PASS |
| GET / (authenticated) | 200 | 200 | PASS |

### Authenticated Routes
| Method | Path | Expected | Actual | Status |
|--------|------|----------|--------|--------|
| GET | /clients/ | 200 | 200 | PASS |
| GET | /pipeline/ | 200 | 200 | PASS |
| GET | /invoices/ | 200 | 200 | PASS |
| GET | /catalog/ | 200 | 200 | PASS |
| GET | /reports/ | 200 | 200 | PASS |
| GET | /settings/ | 200 | 200 | PASS |
| GET | /search/?q=test | 200 | 200 | PASS |

## Assembly Fix Applied
- Missing `email-validator>=2.0` dependency (WTForms Email() validator requires it)

STATUS: PASS
