---
title: "feat: Workshop Registration Hub"
type: feat
status: active
date: 2026-05-13
origin: docs/brainstorms/2026-05-13-workshop-registration-hub-brainstorm.md
swarm: true
feed_forward:
  risk: "Cross-stack API contract between Flask and Express is novel -- no prior swarm build has bridged two stacks. P0 contradictions most likely to hide here."
  verify_first: true
---

# feat: Workshop Registration Hub

## Deepening Key Improvements

**Deepened on:** 2026-05-13
**Research agents used:** Square Checkout API, Express proxy patterns, Supabase realtime browser JS, security-sentinel, performance-oracle, architecture-strategist

### Key Improvements
1. **Square Payment Links API** prescribed (resolves Feed-Forward "least confident" -- exact `quick_pay` pattern, `order_id` linkage, deprecated CreateCheckout avoided)
2. **3 missing wiring table entries** added (Agent 3->5 promotion, Agent 2->4 waitlist email, Agent 3->4 payment_failed email)
3. **Async sync + email** -- `threading.Thread` wraps both to prevent Flask blocking (performance HIGH fix)
4. **Rate limiting** added via `flask-limiter` on registration endpoint (security P1)
5. **Express proxy** prescribed as `http-proxy-middleware` with error handling and body parsing order
6. **Supabase realtime setup** -- `ALTER PUBLICATION`, `REPLICA IDENTITY FULL`, CDN script tag, `worker: true`

### New Considerations Discovered
- `email_log` UNIQUE constraint blocks re-registration confirmation emails -- changed to include `registration_attempt`
- SQLite needs `timeout=5` in `sqlite3.connect()` to handle concurrent writes gracefully
- Flask must run with `threaded=True` for concurrent request handling
- `.gitignore` is mandatory (credentials in `.env`)

## Overview

A 9-agent cross-stack swarm build producing a workshop registration system for the Amplify AI May 30 workshop. Flask (Python) backend with SQLite, Express (Node) frontend with EJS templates and Supabase realtime for admin live updates.

**Primary goal:** Stress-test the swarm autopilot with four new integration surfaces never attempted in prior builds: cross-stack coordination, dual data stores, real external APIs, and event-driven chains.

**Secondary goal:** Produce a functional registration tool (form, payment, email confirmation, admin dashboard, waitlist).

## Plan Quality Gate

1. **What exactly is changing?** New `workshop-registration/` directory in sandbox with Flask backend and Express frontend.
2. **What must not change?** All existing sandbox apps, CLAUDE.md, agent-pitfalls.md (read-only during build), shared spec templates in docs/templates/.
3. **How will we know it worked?** EARS acceptance tests below, plus swarm success criteria (zero structural failures, cross-stack contract holds, event chains fire).
4. **What is the most likely way this plan is wrong?** The cross-stack API contract has a gap that Flask and Express agents build against inconsistently -- specifically around error response shapes or the Square checkout redirect flow.

## Technical Approach

### Architecture

```
Browser <-> Express (port 3000) <-> Flask API (port 5000) <-> SQLite
                |                                              |
                +---- Supabase Realtime (admin live updates) <-+ (sync)
```

**Key architectural decision: Express proxies all API calls to Flask.** The browser never talks directly to Flask. This eliminates CORS configuration and CSRF cross-stack issues. Express uses `http-proxy-middleware` (see prescribed pattern below) to proxy requests to Flask.

Supabase realtime connects directly from the admin browser to Supabase using the anon key (read-only RLS). This is the only direct browser-to-external-service connection.

### Registrant Status State Machine

This is the shared contract that all 6 backend agents depend on. Every agent MUST reference these exact status values.

```
                         +---> payment_failed
                         |        |
  [form submit]          |        v (retry link sent)
      |                  |   pending_payment <---+
      v                  |        |              |
  pending_payment -------+        v              |
      |                       [Square webhook:   |
      |                        payment.updated   |
      |                        status=COMPLETED] |
      |                           |              |
      v                           v              |
  waitlisted -------> pending_payment            |
  (FIFO queue)    (auto-promote when             |
      |            spot opens)                   |
      v                           |              |
  cancelled                       v              |
                                paid             |
                                  |              |
                                  v              |
                              cancelled ----------+
                          (refund processed)
```

**Valid statuses:** `pending_payment`, `paid`, `waitlisted`, `cancelled`, `payment_failed`

**Valid transitions:**

| From | To | Trigger | Agent |
|------|----|---------|-------|
| (new) | pending_payment | Form submission, capacity available | Agent 2 |
| (new) | waitlisted | Form submission, capacity full | Agent 2 + 5 |
| pending_payment | paid | Square webhook: payment.updated, status=COMPLETED | Agent 3 |
| pending_payment | payment_failed | Square webhook: payment.updated, status=FAILED | Agent 3 |
| pending_payment | cancelled | Admin action or timeout | Agent 2 |
| payment_failed | pending_payment | Re-registration with same email | Agent 2 |
| waitlisted | pending_payment | Auto-promote (spot opened) | Agent 5 |
| waitlisted | cancelled | Registrant withdraws | Agent 2 |
| paid | cancelled | Refund processed (Square refund.created webhook) | Agent 3 |

**Capacity rule:** Only `paid` status counts against the 35-seat capacity. `pending_payment` does NOT count. This avoids the abandoned checkout problem.

### Cross-Stack API Contract

Express proxies all requests to Flask. The browser talks only to Express.

**Error response format (all endpoints):**
```json
{"error": "Human-readable message", "code": "MACHINE_CODE"}
```

**Error codes:** `VALIDATION_FAILED`, `DUPLICATE_EMAIL`, `UNAUTHORIZED`, `NOT_FOUND`, `INTERNAL_ERROR`

Note: `CAPACITY_FULL` and `PAYMENT_REQUIRED` are intentionally absent. When capacity is full, the system auto-waitlists (returns 201 with `status: "waitlisted"`). Payment is handled by Square redirect, not by an error response.

#### Endpoints

| Method | Flask Path | Request Body | Success Response | Error Responses | Auth | Owner |
|--------|-----------|-------------|-----------------|----------------|------|-------|
| POST | /api/register | `{"name": "str", "email": "str", "role": "str"}` | See full contract below | `400 VALIDATION_FAILED` | None | Agent 2 |
| POST | /api/webhooks/square | Square webhook payload | `200 ""` | `403` (invalid signature) | Square HMAC | Agent 3 |
| GET | /api/admin/registrants | -- | `200 {"registrants": [...], "total": int, "capacity": 35, "paid_count": int, "waitlist_count": int}` | `401 UNAUTHORIZED` | Basic auth | Agent 2 |
| GET | /api/admin/stats | -- | `200 {"total": int, "paid": int, "waitlisted": int, "cancelled": int, "pending_payment": int, "payment_failed": int}` | `401 UNAUTHORIZED` | Basic auth | Agent 2 |
| GET | /api/admin/export | -- | `200 text/csv` | `401 UNAUTHORIZED` | Basic auth | Agent 2 |
| GET | /api/health | -- | `200 {"status": "ok", "db": "connected", "supabase": "connected"\|"disconnected"}` | -- | None | Agent 1 |

#### POST /api/register -- Complete Response Contract

This is the authoritative response contract for Agent 7 (Express consumer) and Agent 2 (Flask producer). Every possible response is listed.

| Condition | Status | Response Body |
|-----------|--------|---------------|
| New registration, capacity available | `201` | `{"registrant_id": int, "status": "pending_payment", "checkout_url": "https://sandbox.square.link/...", "queue_position": null}` |
| New registration, capacity full | `201` | `{"registrant_id": int, "status": "waitlisted", "checkout_url": null, "queue_position": int}` |
| Duplicate email, existing status = paid | `409` | `{"error": "Already registered", "code": "DUPLICATE_EMAIL"}` |
| Duplicate email, existing status = pending_payment | `409` | `{"error": "Registration pending payment", "code": "DUPLICATE_EMAIL", "checkout_url": "https://..."}` |
| Duplicate email, existing status = waitlisted | `409` | `{"error": "Already on waitlist", "code": "DUPLICATE_EMAIL", "queue_position": int}` |
| Duplicate email, existing status = cancelled or payment_failed | `201` | `{"registrant_id": int, "status": "pending_payment", "checkout_url": "https://...", "queue_position": null}` (re-registration, existing row updated) |
| Invalid input (missing/bad fields) | `400` | `{"error": "description", "code": "VALIDATION_FAILED"}` |

**Registrant object shape** (returned in arrays and used by Express):
```json
{
  "id": 1,
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "Composer",
  "status": "paid",
  "queue_position": null,
  "square_order_id": "YggCup2fBKScqYhpIglzWMpJxyaZY",
  "square_payment_id": "pay_xyz789",
  "created_at": "2026-05-14T10:30:00Z",
  "paid_at": "2026-05-14T10:35:00Z"
}
```

**Admin auth:** Express `basicAuth` middleware (Agent 8) protects `/admin/*` routes with a 401 + `WWW-Authenticate: Basic` challenge. When the admin enters credentials in the browser dialog, the browser caches them and automatically re-sends the `Authorization: Basic` header on ALL subsequent requests to the same origin -- including `fetch()` calls from `admin-realtime.js` to `/api/admin/*`. The Express proxy forwards this header to Flask, which validates against `ADMIN_PASSWORD` env var. **No password is ever embedded in browser JavaScript.**

**Square checkout redirect URL:**
- Success: `http://localhost:3000/register/success?registrant_id=X`

Flask passes this to Square when creating the checkout link. Express (Agent 7) renders the success page. **There is no cancel URL** -- the Square Payment Links API only supports a success redirect. If a customer abandons checkout, they simply close the tab. Their status stays `pending_payment` and is visible in the admin dashboard.

### Database Schema (SQLite -- Source of Truth)

```sql
-- workshop-registration/schema.sql

CREATE TABLE IF NOT EXISTS registrants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK(role IN ('Writer', 'Director', 'Composer', 'Post-Production', 'Student', 'Other')),
    status TEXT NOT NULL DEFAULT 'pending_payment'
        CHECK(status IN ('pending_payment', 'paid', 'waitlisted', 'cancelled', 'payment_failed')),
    queue_position INTEGER,
    square_order_id TEXT,
    square_payment_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    paid_at TEXT,
    cancelled_at TEXT
);

CREATE TABLE IF NOT EXISTS email_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registrant_id INTEGER NOT NULL REFERENCES registrants(id),
    template_type TEXT NOT NULL CHECK(template_type IN ('confirmation', 'reminder_7d', 'reminder_1d', 'post_workshop', 'waitlist_confirmation', 'waitlist_promotion', 'payment_failed')),
    resend_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'sent' CHECK(status IN ('sent', 'failed')),
    sent_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Note: No UNIQUE constraint on (registrant_id, template_type) because re-registration
-- after cancellation/payment_failed needs to send a new confirmation email.
-- Idempotency is checked by querying: "sent within last 24 hours for this type".

CREATE TABLE IF NOT EXISTS webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    square_event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    processed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_registrants_status ON registrants(status);
CREATE INDEX IF NOT EXISTS idx_registrants_email ON registrants(email);
CREATE INDEX IF NOT EXISTS idx_email_log_registrant ON email_log(registrant_id);
```

### Supabase Schema (Read-Optimized Mirror)

```sql
-- Run in Supabase SQL editor

CREATE TABLE IF NOT EXISTS registrants_realtime (
    id BIGINT PRIMARY KEY,
    status TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Anon read-only RLS: non-PII columns only
ALTER TABLE registrants_realtime ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_registrants"
    ON registrants_realtime
    FOR SELECT
    TO anon
    USING (true);

-- No write policies for anon
-- Writes come from Flask sync function using service role key
```

**RLS decision:** Anon can read all rows but the table only contains non-PII columns (no name, no email). Admin sees full registrant data via Flask API (proxied through Express), not Supabase.

**Admin realtime contract:** Supabase is a **change signal only**, not a data source for the admin UI. When `admin-realtime.js` receives an INSERT or UPDATE event from Supabase, it calls `fetch('/api/admin/registrants')` (no explicit auth header -- the browser's cached basic auth credentials are sent automatically). The Express proxy forwards the request to Flask, which validates and returns full registrant data (with PII). The Supabase event payload is used only to know *that* something changed, not *what* changed. This avoids PII in Supabase and keeps `ADMIN_PASSWORD` out of browser JavaScript.

### Data Ownership Table

| Table | Location | Writer | Readers |
|-------|----------|--------|---------|
| registrants | SQLite | Agent 2 (registration), Agent 3 (payment status), Agent 5 (waitlist status) | All Flask agents, Express via /api/* |
| email_log | SQLite | Agent 4 (email engine) | Agent 6 (idempotency check) |
| webhook_events | SQLite | Agent 3 (idempotency) | Agent 3 only |
| registrants_realtime | Supabase | Agent 1 sync function ONLY | Express admin UI (Agent 8) via Supabase anon key |

**Rule:** No agent writes to Supabase directly except Agent 1's sync function. No Express agent writes to SQLite.

### Export Names Table

#### Flask Exports

| Name | Type | File | Used By | Notes |
|------|------|------|---------|-------|
| `create_app` | function | `app/__init__.py` | `run.py` | App factory, registers all blueprints |
| `get_db` | context manager | `app/db.py` | All Flask agents | MUST use `with get_db() as conn:`. Connection uses `timeout=5` for busy wait. |
| `init_db` | function | `app/db.py` | `create_app()` | Called once at startup |
| `sync_registrant` | function | `app/supabase_sync.py` | Agents 2, 3, 5 | Fire-and-forget, 3 retries |
| `register_attendee` | function | `app/models.py` | Agent 2 | Returns `int` (registrant ID). Usage: `rid = register_attendee(conn, name, email, role)` |
| `get_registrant` | function | `app/models.py` | Agents 2, 3, 4, 5 | Returns `sqlite3.Row \| None` |
| `get_registrant_by_email` | function | `app/models.py` | Agent 2 | Returns `sqlite3.Row \| None` |
| `update_status` | function | `app/models.py` | Agents 2, 3, 5 | `update_status(conn, registrant_id, new_status, **kwargs)` |
| `get_paid_count` | function | `app/models.py` | Agents 2, 5 | Returns `int`. Usage: `count = get_paid_count(conn)` |
| `get_next_waitlisted` | function | `app/models.py` | Agent 5 | Returns `sqlite3.Row \| None` (lowest queue_position) |
| `send_email` | function | `app/email/engine.py` (re-exported via `app/email/__init__.py`) | Agents 2, 3, 5, 6 | `send_email(registrant_id: int, template_type: str) -> bool`. Import: `from app.email import send_email` |
| `create_checkout_link` | function | `app/registration/routes.py` | Agents 2, 5 | `create_checkout_link(registrant_id: int, email: str) -> tuple[str, str]` Returns `(checkout_url, order_id)`. |
| `try_promote_next` | function | `app/waitlist/routes.py` | Agent 3 | `try_promote_next(conn) -> None`. Called after refund to auto-promote next waitlisted. Handles checkout link + email internally. |
| `verify_square_signature` | function | `app/webhooks.py` | Agent 3 | Returns `bool` |
| `registration_bp` | Blueprint | `app/registration/routes.py` | `create_app()` | url_prefix="/api" |
| `payments_bp` | Blueprint | `app/payments/routes.py` | `create_app()` | url_prefix="/api" |
| `waitlist_bp` | Blueprint | `app/waitlist/routes.py` | `create_app()` | url_prefix="/api" |
| `admin_bp` | Blueprint | `app/admin/routes.py` | `create_app()` | url_prefix="/api/admin" |

#### Express Exports

| Name | Type | File | Used By | Notes |
|------|------|------|---------|-------|
| `createApp` | function | `frontend/app.js` | `frontend/server.js` | Express app factory |
| `flaskProxy` | middleware | `frontend/middleware/flask-proxy.js` | All routes | Proxies to Flask API |
| `basicAuth` | middleware | `frontend/middleware/auth.js` | Admin routes | Checks ADMIN_PASSWORD env var |

### Cross-Boundary Wiring Table

| Function | Defined In | Called From | Import Path | Arguments |
|----------|-----------|------------|-------------|-----------|
| `send_email` | `app/email` | `app/payments/routes.py` (Agent 3) | `from app.email import send_email` | `(registrant_id, "confirmation")` |
| `send_email` | `app/email` | `app/waitlist/routes.py` (Agent 5) | `from app.email import send_email` | `(registrant_id, "waitlist_promotion")` |
| `send_email` | `app/email` | `app/scheduler/jobs.py` (Agent 6) | `from app.email import send_email` | `(registrant_id, template_type)` |
| `sync_registrant` | `app/supabase_sync.py` | `app/registration/routes.py` (Agent 2) | `from app.supabase_sync import sync_registrant` | `(registrant_id)` |
| `sync_registrant` | `app/supabase_sync.py` | `app/payments/routes.py` (Agent 3) | `from app.supabase_sync import sync_registrant` | `(registrant_id)` |
| `sync_registrant` | `app/supabase_sync.py` | `app/waitlist/routes.py` (Agent 5) | `from app.supabase_sync import sync_registrant` | `(registrant_id)` |
| `get_paid_count` | `app/models.py` | `app/registration/routes.py` (Agent 2) | `from app.models import get_paid_count` | `(conn)` |
| `get_paid_count` | `app/models.py` | `app/waitlist/routes.py` (Agent 5) | `from app.models import get_paid_count` | `(conn)` |
| `get_next_waitlisted` | `app/models.py` | `app/waitlist/routes.py` (Agent 5) | `from app.models import get_next_waitlisted` | `(conn)` |
| `register_attendee` | `app/models.py` | `app/registration/routes.py` (Agent 2) | `from app.models import register_attendee` | `(conn, name, email, role)` |
| `verify_square_signature` | `app/webhooks.py` | `app/payments/routes.py` (Agent 3) | `from app.webhooks import verify_square_signature` | `(body, signature)` |
| `try_promote_next` | `app/waitlist/routes.py` | `app/payments/routes.py` (Agent 3) | `from app.waitlist.routes import try_promote_next` | `(conn)` |
| `create_checkout_link` | `app/registration/routes.py` | `app/waitlist/routes.py` (Agent 5) | `from app.registration.routes import create_checkout_link` | `(registrant_id, email)` |
| `send_email` | `app/email` | `app/registration/routes.py` (Agent 2) | `from app.email import send_email` | `(registrant_id, "waitlist_confirmation")` |
| `send_email` | `app/email` | `app/payments/routes.py` (Agent 3) | `from app.email import send_email` | `(registrant_id, "payment_failed")` |

### Race Condition Mitigations

**Last-seat race (Critical):** The capacity check and registration insert MUST be a single SQLite transaction using `BEGIN IMMEDIATE`:

```python
# Agent 2: registration route -- PRESCRIBED SQL
def register_attendee(conn, name, email, role):
    """Atomic registration with auto-waitlist. Returns registrant ID (int).
    If capacity is full, inserts with status='waitlisted' instead of 'pending_payment'.
    Never raises a capacity error -- always succeeds with one of those two statuses."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        paid_count = conn.execute(
            "SELECT COUNT(*) FROM registrants WHERE status = 'paid'"
        ).fetchone()[0]

        capacity = int(os.environ.get("WORKSHOP_CAPACITY", 35))
        if paid_count >= capacity:
            conn.execute(
                "INSERT INTO registrants (name, email, role, status, queue_position) "
                "VALUES (?, ?, ?, 'waitlisted', "
                "(SELECT COALESCE(MAX(queue_position), 0) + 1 FROM registrants WHERE status = 'waitlisted'))",
                (name, email, role)
            )
        else:
            conn.execute(
                "INSERT INTO registrants (name, email, role, status) VALUES (?, ?, ?, 'pending_payment')",
                (name, email, role)
            )

        rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        return rid
    except Exception:
        conn.rollback()
        raise
```

**Webhook idempotency (insert-first contract):** Agent 3 attempts `INSERT INTO webhook_events (square_event_id, event_type, payload)` first. If the UNIQUE constraint on `square_event_id` raises `IntegrityError`, the event was already processed -- return 200 immediately. This is safe under concurrent duplicate delivery because SQLite serializes writes.

```python
# Agent 3: webhook handler idempotency pattern
try:
    conn.execute(
        "INSERT INTO webhook_events (square_event_id, event_type, payload) VALUES (?, ?, ?)",
        (event["event_id"], event["type"], json.dumps(event))
    )
except sqlite3.IntegrityError:
    return "", 200  # Already processed, ack to Square
```

**Payment amount validation:** Before marking a registrant as `paid`, Agent 3 MUST verify `event["data"]["object"]["payment"]["amount_money"]["amount"] == int(os.environ.get("WORKSHOP_PRICE_CENTS", 17500))`. If mismatched, log the discrepancy and do NOT update status. Return 200 to Square (ack receipt) but flag for manual review.

**Webhook-before-row race:** Store `square_order_id` in the registrant row at creation time. Webhook handler looks up by `square_order_id`. If not found, return 200 (ack to Square) and log for manual reconciliation. Square retries for up to 72 hours.

**Waitlist promotion race:** Atomic claim pattern:
```python
cursor = conn.execute(
    "UPDATE registrants SET status = 'pending_payment', queue_position = NULL "
    "WHERE id = (SELECT id FROM registrants WHERE status = 'waitlisted' "
    "ORDER BY queue_position ASC LIMIT 1) AND status = 'waitlisted'"
)
if cursor.rowcount == 0:
    return None  # Another promotion claimed it
```

### Email Template Interface

Agent 4 exposes a single function. It is the ONLY module that imports the `resend` package.

```python
def send_email(registrant_id: int, template_type: str) -> bool:
    """
    Send an email to a registrant.

    Args:
        registrant_id: SQLite registrant ID
        template_type: One of 'confirmation', 'reminder_7d', 'reminder_1d',
                       'post_workshop', 'waitlist_confirmation', 'waitlist_promotion',
                       'payment_failed'

    Returns:
        True if sent (or already sent), False if failed after retries.

    Idempotency: checks email_log for "sent within last 24 hours for this type" before sending.
    Retries: 3 attempts, exponential backoff (1s, 2s, 4s).
    Threading: Called via threading.Thread from webhook/promotion handlers so Flask never blocks.
    """
```

**Template variables** (Agent 4 looks up registrant data internally):

| Template | Subject | Variables |
|----------|---------|-----------|
| confirmation | "You're registered! Amplify AI Workshop - May 30" | name, workshop_date, location, time |
| reminder_7d | "One week until the Amplify AI Workshop" | name, workshop_date, location, time |
| reminder_1d | "Tomorrow! Amplify AI Workshop" | name, workshop_date, location, time |
| post_workshop | "Thank you for attending!" | name |
| waitlist_confirmation | "You're on the waitlist (#N)" | name, queue_position |
| waitlist_promotion | "A spot opened up! Complete your registration" | name, checkout_url |
| payment_failed | "Payment issue with your registration" | name, checkout_url |

### Supabase Sync Function

Owned by Agent 1. **Truly fire-and-forget** -- runs in a background thread so Flask never blocks.

```python
# app/supabase_sync.py
import os
import time
import logging
import threading
from datetime import datetime, timezone
from supabase import create_client

logger = logging.getLogger(__name__)

_client = None

def _get_client():
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if url and key:
            _client = create_client(url, key)
    return _client

def sync_registrant(registrant_id: int):
    """Fire-and-forget: spawns a background thread for sync. Returns immediately."""
    thread = threading.Thread(target=_sync_impl, args=(registrant_id,), daemon=True)
    thread.start()

def _sync_impl(registrant_id: int):
    """Internal: sync with 3 retries, exponential backoff. Runs in background thread."""
    from app.db import get_db
    from app.models import get_registrant

    client = _get_client()
    if client is None:
        logger.warning("Supabase not configured, skipping sync")
        return

    with get_db() as conn:
        reg = get_registrant(conn, registrant_id)
        if reg is None:
            return

    row = {
        "id": reg["id"],
        "status": reg["status"],
        "role": reg["role"],
        "created_at": reg["created_at"],
        "paid_at": reg["paid_at"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    for attempt in range(3):
        try:
            client.table("registrants_realtime").upsert(row).execute()
            return
        except Exception as e:
            logger.error(f"Supabase sync attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s
```

### Supabase Realtime Setup Requirements

Before the admin dashboard can receive live updates, run these in the Supabase SQL editor:

```sql
-- Enable table for realtime
ALTER PUBLICATION supabase_realtime ADD TABLE registrants_realtime;

-- Enable full row data on UPDATE/DELETE events
ALTER TABLE registrants_realtime REPLICA IDENTITY FULL;
```

The admin dashboard loads supabase-js via CDN and connects with `worker: true` for background tab resilience:

```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script>
  var sb = supabase.createClient('<%= process.env.SUPABASE_URL %>', '<%= process.env.SUPABASE_ANON_KEY %>', {
    realtime: { worker: true }
  });

  // Supabase is a CHANGE SIGNAL only -- refetch full data from Flask on each event.
  // No auth header needed here: the browser already authenticated via basic auth
  // dialog when loading /admin/. It automatically re-sends the cached Authorization
  // header on all fetch() calls to the same origin.
  sb.channel('admin-registrants')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'registrants_realtime' },
      function () {
        fetch('/api/admin/registrants')
          .then(function (r) { return r.json(); })
          .then(function (data) { renderRegistrantTable(data.registrants); });
      })
    .subscribe();
</script>
```

### Square Payment Links API (Checkout Flow)

Use the Payment Links API (`client.checkout.payment_links.create`), NOT the deprecated CreateCheckout endpoint. Use `quick_pay` for a single fixed-price item.

```python
# In app/registration/routes.py (Agent 2) -- checkout creation lives here, not in payments
from square import Square
from square.environment import SquareEnvironment
import uuid, os

square_client = Square(
    token=os.environ.get("SQUARE_ACCESS_TOKEN"),
    environment=SquareEnvironment.SANDBOX,
)

def create_checkout_link(registrant_id: int, email: str) -> tuple[str, str]:
    """Create a Square Payment Link. Returns (checkout_url, order_id)."""
    response = square_client.checkout.payment_links.create(
        idempotency_key=str(uuid.uuid4()),
        quick_pay={
            "name": "Amplify AI Workshop - May 30, 2026",
            "price_money": {"amount": int(os.environ.get("WORKSHOP_PRICE_CENTS", 17500)), "currency": "USD"},
            "location_id": os.environ.get("SQUARE_LOCATION_ID"),
        },
        checkout_options={
            "redirect_url": f"{os.environ.get('SQUARE_REDIRECT_BASE', 'http://localhost:3000')}/register/success?registrant_id={registrant_id}",
        },
        pre_populated_data={"buyer_email": email},
        payment_note=f"registrant:{registrant_id}",
    )
    # Store order_id to link webhook back to registrant
    # response.payment_link.order_id -> UPDATE registrants SET square_order_id = ? WHERE id = ?
    return response.payment_link.url, response.payment_link.order_id
```

**Webhook lookup:** Agent 3 finds the registrant via `square_order_id` (which stores `order_id`). The webhook payload contains `data.object.payment.order_id`.

**Important:** There is no `payment.completed` event. Subscribe to `payment.updated` and check `status == "COMPLETED"`.

### Square Webhook Verification

```python
# app/webhooks.py
import hmac
import hashlib
import base64
import os

SQUARE_SIGNATURE_KEY = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "")
SQUARE_WEBHOOK_URL = os.environ.get("SQUARE_WEBHOOK_URL", "")

def verify_square_signature(body: str, signature: str) -> bool:
    """Verify Square webhook HMAC-SHA256 signature.
    IMPORTANT: Caller must pass request.get_data(as_text=True), NOT request.json."""
    if not SQUARE_SIGNATURE_KEY or not SQUARE_WEBHOOK_URL:
        return False

    combined = SQUARE_WEBHOOK_URL + body
    expected = base64.b64encode(
        hmac.new(
            SQUARE_SIGNATURE_KEY.encode("utf-8"),
            combined.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    return hmac.compare_digest(expected, signature)
```

### Scheduler / Cron

**Trigger mechanism:** Flask CLI command. No APScheduler, no Celery.

```bash
# To run reminders manually:
cd workshop-registration && python -m flask send-reminders

# To set up cron (local only):
# 0 9 * * * cd /path/to/workshop-registration && python -m flask send-reminders
```

**Timezone:** All SQLite timestamps stored in UTC. Workshop datetime: `2026-05-30T17:00:00Z` (10am PDT). Reminder windows calculated in UTC:
- 7-day reminder: send on or after `2026-05-23T17:00:00Z`
- 1-day reminder: send on or after `2026-05-29T17:00:00Z`
- Post-workshop follow-up: send on or after `2026-06-01T17:00:00Z` (2 days after)

### Validation Rules (Shared: Agent 2 server-side + Agent 7 client-side)

| Field | Required | Type | Constraints | Error Message |
|-------|----------|------|-------------|---------------|
| name | yes | string | 1-100 chars, trimmed | "Name is required" / "Name must be under 100 characters" |
| email | yes | string | Valid email format, lowercased | "Valid email address required" |
| role | yes | enum | Writer, Director, Composer, Post-Production, Student, Other | "Please select a role" |

### Express Proxy Middleware

Use `http-proxy-middleware` v3.x. **Mount BEFORE body parsing** -- this is critical, otherwise POST bodies are consumed before proxying.

```js
// frontend/middleware/flask-proxy.js
const { createProxyMiddleware } = require('http-proxy-middleware');

const FLASK_URL = process.env.FLASK_API_URL || 'http://127.0.0.1:5000';

const flaskProxy = createProxyMiddleware({
  target: FLASK_URL,
  changeOrigin: true,
  timeout: 30000,
  proxyTimeout: 30000,
  xfwd: true,
  on: {
    error: (err, req, res) => {
      if (res.headersSent) return;
      const status = err.code === 'ECONNREFUSED' ? 502
        : (err.code === 'ETIMEDOUT' ? 504 : 502);
      res.status(status).json({ error: 'API server unavailable', code: err.code });
    }
  }
});

module.exports = flaskProxy;
```

**Middleware order in `app.js`:** (1) express.static, (2) helmet, (3) `/api` proxy, (4) express.json + urlencoded, (5) EJS page routes, (6) 404 handler, (7) error handler.

### Rate Limiting

Add `flask-limiter` to prevent spam registrations and API quota exhaustion.

```python
# In app/__init__.py (Agent 1)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(get_remote_address, default_limits=["60 per minute"])

def create_app():
    app = Flask(__name__)
    limiter.init_app(app)
    # ...
```

**Per-endpoint limits:**
- `POST /api/register`: 5 per minute per IP (prevents spam registration + Square API abuse)
- `POST /api/webhooks/square`: 30 per minute per IP (Square may burst webhooks)
- `GET /api/admin/*`: 60 per minute per IP (default)

Add `flask-limiter` to `requirements.txt`.

### .gitignore (Mandatory)

```gitignore
.env
*.db
__pycache__/
node_modules/
.DS_Store
```

### Global Error Handler

```python
# In app/__init__.py (Agent 1)
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({"error": "Internal server error", "code": "INTERNAL_ERROR"}), 500
```

### Environment Variables

```env
# Flask
FLASK_SECRET_KEY=dev-fallback-change-in-prod
ADMIN_PASSWORD=changeme
WORKSHOP_PRICE_CENTS=17500
WORKSHOP_CAPACITY=35
WORKSHOP_DATE=2026-05-30T17:00:00Z

# Square (sandbox)
SQUARE_ACCESS_TOKEN=sandbox-token
SQUARE_LOCATION_ID=sandbox-location
SQUARE_WEBHOOK_SIGNATURE_KEY=sandbox-sig-key
SQUARE_WEBHOOK_URL=http://localhost:5000/api/webhooks/square
SQUARE_ENVIRONMENT=sandbox

# Resend
RESEND_API_KEY=re_test_key
RESEND_FROM_EMAIL=Amplify AI <noreply@amplifyai.to>

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=service-role-key
SUPABASE_ANON_KEY=anon-key

# Express
EXPRESS_PORT=3000
FLASK_API_URL=http://localhost:5000
```

## Implementation Phases

### Phase 1: Core Foundation (Agent 1)

Agent 1 builds first. All other agents depend on these files.

**Files:**
- `workshop-registration/run.py`
- `workshop-registration/requirements.txt`
- `workshop-registration/app/__init__.py` (create_app factory)
- `workshop-registration/app/db.py` (get_db context manager, init_db)
- `workshop-registration/app/models.py` (all model functions)
- `workshop-registration/schema.sql`
- `workshop-registration/app/supabase_sync.py`
- `workshop-registration/app/webhooks.py` (verify_square_signature)
- `workshop-registration/.env.example`
- `workshop-registration/.gitignore`

**run.py must use `threaded=True`:**
```python
app = create_app()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
```

Agent 1 also implements the `GET /api/health` endpoint directly in `create_app()` (no blueprint needed -- simple inline route returning `{"status": "ok", "db": "connected", "supabase": "connected"|"disconnected"}`).

**Gate 1:** `models.py` exists with all exported functions. `get_db` is importable. `schema.sql` creates all tables. `GET /api/health` returns 200.

### Phase 2: Backend APIs (Agents 2, 3, 4, 5, 6 -- parallel)

All backend agents run in parallel after Phase 1 gate passes.

**Agent 2 -- Registration + Admin API:**
- `app/registration/__init__.py`
- `app/registration/routes.py` (POST /api/register with atomic capacity check)
- `app/admin/__init__.py`
- `app/admin/routes.py` (GET /api/admin/registrants, /stats, /export with basic auth validation)

**Agent 3 -- Payment Webhooks:**
- `app/payments/__init__.py`
- `app/payments/routes.py` (POST /api/webhooks/square with HMAC verification)

**Agent 4 -- Email Engine:**
- `app/email/__init__.py`
- `app/email/engine.py` (send_email function, Resend integration, templates)

**Agent 5 -- Waitlist + Capacity:**
- `app/waitlist/__init__.py`
- `app/waitlist/routes.py` (promotion logic, called by Agent 3 after refund)

**Agent 6 -- Notification Scheduler:**
- `app/scheduler/__init__.py`
- `app/scheduler/jobs.py` (send_reminders CLI command)

**Gate 2:** All Flask blueprints register. Smoke test: POST /api/register returns 201 (with mock Square). GET /api/health returns 200.

### Phase 3: Express Frontend (Agents 7, 8 -- parallel)

Both Express agents run in parallel after Phase 2 gate passes (they need the API contract verified).

**Agent 7 -- Public Registration Page:**
- `frontend/package.json`
- `frontend/server.js`
- `frontend/app.js` (createApp factory)
- `frontend/middleware/flask-proxy.js`
- `frontend/views/register.ejs` (form)
- `frontend/views/success.ejs` (post-payment redirect landing)
- `frontend/public/css/style.css`
- `frontend/public/js/validation.js`

**Agent 8 -- Admin UI:**
- `frontend/middleware/auth.js` (basic auth)
- `frontend/views/admin/dashboard.ejs` (registrant table, stats, capacity meter)
- `frontend/views/admin/layout.ejs`
- `frontend/public/js/admin-realtime.js` (Supabase change signal -> refetch full data from Flask /api/admin/registrants)
- `frontend/routes/admin.js`

**Gate 3:** Express starts on port 3000. Registration form renders. Admin dashboard renders with basic auth.

### Phase 4: Integration Wiring (Agent 9)

Runs after all other agents complete.

**Agent 9 checklist:**
- [ ] Flask `create_app()` registers all 4 blueprints (registration, payments, waitlist, admin)
- [ ] Flask scheduler CLI command is registered
- [ ] Express `app.js` mounts all routes (register, admin, proxy)
- [ ] Express flask-proxy middleware correctly proxies to Flask API URL
- [ ] Express admin auth middleware protects /admin/* routes
- [ ] Supabase anon key is loaded in admin-realtime.js
- [ ] admin-realtime.js uses Supabase as change signal only (subscribes to events, refetches from /api/admin/registrants on each event, never renders Supabase payload directly)
- [ ] All cross-boundary imports resolve (per Wiring Table)
- [ ] Smoke test: full registration flow (form -> API -> response)
- [ ] Smoke test: admin dashboard loads with data from Flask
- [ ] Smoke test: Square webhook endpoint returns 200 (with valid test signature)
- [ ] Health endpoint returns connected status for DB and Supabase
- [ ] All env vars documented in .env.example

## Swarm Agent Assignment

**Total agents:** 9
**Total files:** 37
**Validation:** No file appears in multiple assignments

### Shared Interface Spec

Every agent receives this complete spec. Do not implement anything that contradicts it.

**Valid statuses:** `pending_payment`, `paid`, `waitlisted`, `cancelled`, `payment_failed`

**Capacity rule:** Only `paid` counts against the 35-seat cap. `pending_payment` does NOT count.

**Error response shape (all Flask endpoints):**
```json
{"error": "Human-readable message", "code": "MACHINE_CODE"}
```
Valid codes: `VALIDATION_FAILED`, `DUPLICATE_EMAIL`, `UNAUTHORIZED`, `NOT_FOUND`, `INTERNAL_ERROR`

**Flask Export Names (exact -- do not rename):**

| Name | Signature | File |
|------|-----------|------|
| `create_app` | `() -> Flask` | `app/__init__.py` |
| `get_db` | context manager | `app/db.py` |
| `init_db` | `() -> None` | `app/db.py` |
| `sync_registrant` | `(registrant_id: int) -> None` | `app/supabase_sync.py` |
| `register_attendee` | `(conn, name, email, role) -> int` | `app/models.py` |
| `get_registrant` | `(conn, id) -> sqlite3.Row \| None` | `app/models.py` |
| `get_registrant_by_email` | `(conn, email) -> sqlite3.Row \| None` | `app/models.py` |
| `update_status` | `(conn, registrant_id, new_status, **kwargs) -> None` | `app/models.py` |
| `get_paid_count` | `(conn) -> int` | `app/models.py` |
| `get_next_waitlisted` | `(conn) -> sqlite3.Row \| None` | `app/models.py` |
| `send_email` | `(registrant_id: int, template_type: str) -> bool` | `app/email/__init__.py` (re-export from engine.py) |
| `create_checkout_link` | `(registrant_id: int, email: str) -> tuple[str, str]` | `app/registration/routes.py` |
| `verify_square_signature` | `(body: str, signature: str) -> bool` | `app/webhooks.py` |
| `try_promote_next` | `(conn) -> None` | `app/waitlist/routes.py` |
| `registration_bp` | Blueprint | `app/registration/routes.py` (url_prefix="/api") |
| `payments_bp` | Blueprint | `app/payments/routes.py` (url_prefix="/api") |
| `waitlist_bp` | Blueprint | `app/waitlist/routes.py` (url_prefix="/api") |
| `admin_bp` | Blueprint | `app/admin/routes.py` (url_prefix="/api/admin") |

**Express Export Names (exact -- do not rename):**

| Name | Type | File |
|------|------|------|
| `createApp` | function | `frontend/app.js` |
| `flaskProxy` | middleware | `frontend/middleware/flask-proxy.js` |
| `basicAuth` | middleware | `frontend/middleware/auth.js` |

**Cross-boundary imports (use these exact paths):**
- `from app.email import send_email`
- `from app.supabase_sync import sync_registrant`
- `from app.models import register_attendee, get_registrant, get_registrant_by_email, update_status, get_paid_count, get_next_waitlisted`
- `from app.webhooks import verify_square_signature`
- `from app.waitlist.routes import try_promote_next`
- `from app.db import get_db`

**Data ownership (no agent may write outside its assigned tables):**
- `registrants` table: Agents 2 (insert/update), 3 (status update), 5 (status update)
- `email_log` table: Agent 4 only
- `webhook_events` table: Agent 3 only
- `registrants_realtime` (Supabase): Agent 1 sync function only

**Middleware order in Express `app.js`:** (1) express.static, (2) helmet, (3) `/api` proxy, (4) express.json + urlencoded, (5) EJS page routes, (6) 404 handler, (7) error handler. The proxy MUST mount before body parsing.

**SQLite connection:** Always use `with get_db() as conn:`. Connection requires `timeout=5`.

**Flask startup:** `app.run(host='0.0.0.0', port=5000, threaded=True)`

**Supabase realtime rule:** `admin-realtime.js` uses Supabase as a change signal only. On any event, call `fetch('/api/admin/registrants')` and re-render. Never render Supabase payload data directly.

---

### Agent: core-foundation

**Files:**
- `workshop-registration/run.py`
- `workshop-registration/requirements.txt`
- `workshop-registration/schema.sql`
- `workshop-registration/.env.example`
- `workshop-registration/.gitignore`
- `workshop-registration/app/__init__.py`
- `workshop-registration/app/db.py`
- `workshop-registration/app/models.py`
- `workshop-registration/app/supabase_sync.py`
- `workshop-registration/app/webhooks.py`

**Responsibility:** Build the entire Flask foundation -- app factory, DB layer, all model functions, Supabase sync, and webhook signature verification -- so all Phase 2 agents can import from these files without modification.

**Phase:** 1 (all other agents depend on this agent completing first)

**Gate:** `models.py` exports all functions in the shared spec table above. `get_db` is importable. `schema.sql` creates all three tables. `run.py` starts Flask with `threaded=True`.

---

### Agent: registration-admin-api

**Files:**
- `workshop-registration/app/registration/__init__.py`
- `workshop-registration/app/registration/routes.py`
- `workshop-registration/app/admin/__init__.py`
- `workshop-registration/app/admin/routes.py`

**Responsibility:** Implement `POST /api/register` with atomic capacity check and Square checkout creation, plus the three admin read endpoints (`/api/admin/registrants`, `/api/admin/stats`, `/api/admin/export`) protected by basic auth header validation against `ADMIN_PASSWORD` env var.

**Phase:** 2 (parallel with Agents 3, 4, 5, 6)

**Key constraints:**
- `register_attendee` must use `BEGIN IMMEDIATE` transaction (prescribed SQL in plan)
- `create_checkout_link` uses Square Payment Links API `quick_pay` pattern (prescribed in plan)
- Re-registration for `cancelled` or `payment_failed` status updates the existing row, returns 201
- Rate limit `POST /api/register` to 5 per minute per IP using `limiter` from `app/__init__.py`

---

### Agent: payment-webhooks

**Files:**
- `workshop-registration/app/payments/__init__.py`
- `workshop-registration/app/payments/routes.py`

**Responsibility:** Implement `POST /api/webhooks/square` with HMAC signature verification, idempotency via `webhook_events` insert-first pattern, payment amount validation, status transitions (`pending_payment` -> `paid` or `payment_failed`), and waitlist promotion trigger on refund.

**Phase:** 2 (parallel with Agents 2, 4, 5, 6)

**Key constraints:**
- Call `request.get_data(as_text=True)` for signature verification, NOT `request.json`
- Insert into `webhook_events` first; on `IntegrityError` return `"", 200` immediately
- Subscribe to `payment.updated` event (not `payment.completed` -- that event does not exist)
- Validate `amount_money.amount == WORKSHOP_PRICE_CENTS` before marking `paid`
- After marking `cancelled` on refund events (`refund.created`), call `try_promote_next(conn)` to auto-promote next waitlisted
- Rate limit this endpoint to 30 per minute per IP

---

### Agent: email-engine

**Files:**
- `workshop-registration/app/email/__init__.py`
- `workshop-registration/app/email/engine.py`

**Responsibility:** Implement `send_email(registrant_id, template_type) -> bool` using the Resend API with idempotency check, 3-retry exponential backoff, and all 7 email templates; re-export `send_email` from `__init__.py` so callers use `from app.email import send_email`.

**Phase:** 2 (parallel with Agents 2, 3, 5, 6)

**Key constraints:**
- This is the ONLY module that imports `resend`
- Idempotency: query `email_log` for sent within last 24 hours for this `(registrant_id, template_type)` before sending
- Retries: 3 attempts at 1s, 2s, 4s backoff
- Look up registrant data internally using `get_db` + `get_registrant` -- callers pass only `registrant_id`
- Valid `template_type` values: `confirmation`, `reminder_7d`, `reminder_1d`, `post_workshop`, `waitlist_confirmation`, `waitlist_promotion`, `payment_failed`

---

### Agent: waitlist-capacity

**Files:**
- `workshop-registration/app/waitlist/__init__.py`
- `workshop-registration/app/waitlist/routes.py`

**Responsibility:** Implement `try_promote_next(conn)` using the atomic claim UPDATE pattern and export it for Agent 3 to call; also expose `waitlist_bp` Blueprint for blueprint registration.

**Phase:** 2 (parallel with Agents 2, 3, 4, 6)

**Key constraints:**
- Atomic claim pattern (prescribed in plan): single UPDATE with subquery, check `cursor.rowcount == 0` to detect race
- After promotion: call `create_checkout_link` from `app.registration.routes`, update row with new `square_order_id`, then call `send_email(registrant_id, "waitlist_promotion")` via `threading.Thread`
- Call `sync_registrant(registrant_id)` after status change

---

### Agent: notification-scheduler

**Files:**
- `workshop-registration/app/scheduler/__init__.py`
- `workshop-registration/app/scheduler/jobs.py`

**Responsibility:** Implement a Flask CLI command `send-reminders` that queries paid registrants and sends time-windowed reminder and post-workshop emails using `send_email`, respecting idempotency so re-runs are safe.

**Phase:** 2 (parallel with Agents 2, 3, 4, 5)

**Key constraints:**
- Register CLI command via `@app.cli.command("send-reminders")` in `jobs.py`, called from `create_app()` in `app/__init__.py`
- Reminder windows (UTC): 7-day on/after `2026-05-23T17:00:00Z`, 1-day on/after `2026-05-29T17:00:00Z`, post-workshop on/after `2026-06-01T17:00:00Z`
- Only target registrants with `status = 'paid'`
- `send_email` idempotency handles re-runs -- no extra dedup logic needed here

---

### Agent: public-registration-ui

**Files:**
- `workshop-registration/frontend/package.json`
- `workshop-registration/frontend/server.js`
- `workshop-registration/frontend/app.js`
- `workshop-registration/frontend/middleware/flask-proxy.js`
- `workshop-registration/frontend/views/register.ejs`
- `workshop-registration/frontend/views/success.ejs`
- `workshop-registration/frontend/public/css/style.css`
- `workshop-registration/frontend/public/js/validation.js`

**Responsibility:** Build the Express app factory, proxy middleware, public registration form (EJS), success page, client-side validation, and all static assets; wire middleware in the correct order so POST bodies reach Flask.

**Phase:** 3 (parallel with Agent 8)

**Key constraints:**
- Mount `/api` proxy BEFORE `express.json()` (prescribed middleware order above)
- `app.js` exports `createApp` function; `server.js` calls it
- `flask-proxy.js` exports `flaskProxy` middleware, targets `FLASK_API_URL` env var
- `validation.js` enforces shared validation rules: name 1-100 chars, valid email, role from enum
- Success page renders `registrant_id` from query string
- Node packages: `express`, `ejs`, `http-proxy-middleware`, `helmet`, `compression`, `dotenv`

---

### Agent: admin-ui

**Files:**
- `workshop-registration/frontend/middleware/auth.js`
- `workshop-registration/frontend/routes/admin.js`
- `workshop-registration/frontend/views/admin/dashboard.ejs`
- `workshop-registration/frontend/views/admin/layout.ejs`
- `workshop-registration/frontend/public/js/admin-realtime.js`

**Responsibility:** Build the Express basic-auth middleware, admin route handler, dashboard EJS template with registrant table and capacity meter, and the Supabase realtime change-signal script that refetches full data from Flask on each event.

**Phase:** 3 (parallel with Agent 7)

**Key constraints:**
- `auth.js` exports `basicAuth` middleware; returns 401 + `WWW-Authenticate: Basic` if `Authorization` header is absent or credentials do not match `ADMIN_PASSWORD` env var
- `admin-realtime.js` subscribes to `registrants_realtime` table via `@supabase/supabase-js@2` CDN script; on any event calls `fetch('/api/admin/registrants')` and re-renders the table -- never renders Supabase payload directly
- Supabase client uses `{ realtime: { worker: true } }` option
- No `ADMIN_PASSWORD` in browser JavaScript; credentials flow only through the browser's cached `Authorization` header

---

### Agent: integration-wiring

**Files:** (no new files -- patches wiring into files owned by earlier agents)

**Responsibility:** Verify all 4 Flask blueprints are registered in `create_app()`, the scheduler CLI command is registered, Express `app.js` mounts all routes in the correct middleware order, all cross-boundary imports resolve per the Wiring Table, and run the three smoke tests from the plan's Gate 3 checklist.

**Phase:** 4 (runs after all other agents complete)

**Key constraints:**
- Must not introduce new files -- only patch `app/__init__.py` (owned by Agent core-foundation) and `frontend/app.js` (owned by Agent public-registration-ui) if wiring gaps are found
- Use the Agent 9 checklist from the Implementation Phases section as the verification list
- If a smoke test fails, fix the import/wiring gap and re-run before marking complete

---

STATUS: PASS

## Acceptance Tests (EARS Format)

### Happy Path
- WHEN a visitor submits a valid registration form THE SYSTEM SHALL create a registrant with status "pending_payment" and redirect to Square checkout
- WHEN Square sends a payment.updated webhook with status COMPLETED THE SYSTEM SHALL update the registrant to "paid" and send a confirmation email
- WHEN an admin visits /admin with correct credentials THE SYSTEM SHALL display all registrants with payment status badges
- WHEN a new registration is paid THE SYSTEM SHALL trigger a Supabase realtime event that causes the admin dashboard to refetch full registrant data from Flask and re-render the table

### Capacity & Waitlist
- WHEN the 36th person registers (35 paid seats full) THE SYSTEM SHALL add them to the waitlist with status "waitlisted" and queue_position=1
- WHEN a paid registrant is refunded THE SYSTEM SHALL change their status to "cancelled" and auto-promote the next waitlisted person
- WHEN a waitlisted person is promoted THE SYSTEM SHALL send them a promotion email with a new payment link

### Payment Edge Cases
- WHEN Square sends a webhook with an invalid signature THE SYSTEM SHALL return 403 and NOT update any registrant
- WHEN Square sends a duplicate webhook (same event ID) THE SYSTEM SHALL return 200 and NOT process it again
- WHEN a registrant with status "payment_failed" re-registers with the same email THE SYSTEM SHALL update their existing row and generate a new checkout link

### Email
- WHEN a confirmation email fails to send THE SYSTEM SHALL retry up to 3 times with exponential backoff and log the failure
- WHEN the scheduler runs 7 days before the workshop THE SYSTEM SHALL send reminder emails only to registrants who haven't received one yet

### Security
- WHEN an unauthenticated request hits /api/admin/* THE SYSTEM SHALL return 401
- WHEN a visitor tries to access the admin dashboard without basic auth THE SYSTEM SHALL prompt for credentials

### Cross-Stack
- WHEN Express proxies a request to Flask and Flask is down THE SYSTEM SHALL return 502 to the browser (ECONNREFUSED) or 504 (ETIMEDOUT)
- WHEN Supabase is unreachable THE SYSTEM SHALL still complete the registration (SQLite is source of truth) and log the sync failure

### Verification Commands
```bash
# Start both servers
cd workshop-registration && python run.py &
cd workshop-registration/frontend && node server.js &

# Health check
curl http://localhost:5000/api/health | jq .

# Register
curl -X POST http://localhost:3000/api/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","role":"Composer"}' | jq .

# Admin (basic auth)
curl -u admin:changeme http://localhost:3000/admin/ -o /dev/null -w "%{http_code}"

# Webhook test (would need valid HMAC signature in real test)
curl -X POST http://localhost:5000/api/webhooks/square \
  -H "Content-Type: application/json" \
  -d '{"event_id":"evt_test_123","type":"payment.updated","data":{"object":{"payment":{"status":"COMPLETED","order_id":"YggCup2fBKScqYhpIglzWMpJxyaZY","amount_money":{"amount":17500,"currency":"USD"}}}}}' \
  -w "%{http_code}"
```

## Dependencies & Prerequisites (Pre-Build Setup)

1. **Square sandbox credentials:** Create app in Square Developer Console, get sandbox access token, location ID, and webhook signature key
2. **Resend API key:** Create account at resend.com, get API key (use onboarding@resend.dev as sender for testing)
3. **Supabase project:** Create new project in Supabase dashboard, get URL + service role key + anon key. Run the Supabase schema SQL above.
4. **Python packages:** `flask`, `flask-limiter`, `resend`, `squareup`, `supabase` (Python client), `email-validator`, `python-dotenv`
5. **Node packages:** `express`, `ejs`, `http-proxy-middleware`, `helmet`, `compression`, `dotenv`
6. **Browser CDN (no npm):** `@supabase/supabase-js@2` via jsDelivr script tag (admin dashboard only)

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cross-stack API contract has gaps | HIGH | Agents build against wrong assumptions | Spec convergence loop + human verification of API contract |
| Square webhook verification fails in Python | MEDIUM | Payments not confirmed | External research done (above). Manual HMAC fallback if SDK fails. |
| Supabase sync function blocks Flask responses | LOW | Slow registration | Fire-and-forget pattern prescribed. Flask never waits for sync. |
| Agent invents status values not in state machine | MEDIUM | Cross-agent data corruption | State machine prescribed with CHECK constraints in SQL schema |
| Last-seat race condition | LOW | Overselling workshop | BEGIN IMMEDIATE transaction prescribed with exact SQL |

## External API Declarations

Per CLAUDE.md line 19, all external API calls must be declared:

1. **Square API** (sandbox mode): Create checkout links, receive payment webhooks
2. **Resend API** (test mode): Send transactional emails (confirmation, reminders, follow-up)
3. **Supabase API** (dev project): Upsert registrant rows for realtime mirror, realtime subscription from browser

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-05-13-workshop-registration-hub-brainstorm.md](../brainstorms/2026-05-13-workshop-registration-hub-brainstorm.md) -- Key decisions: 9 agents, clean backend/frontend split, SQLite+Supabase, FIFO waitlist, Express proxy to Flask

### Internal References
- Flask app factory: `task-tracker-categories/app/__init__.py:1-33`
- Flask DB pattern: `task-tracker-categories/app/db.py:1-30`
- Express app factory: `notes-api/app.js:1-30`
- Webhook HMAC signing: `webhook-delivery/signing.py:1-9`
- Resend email integration: `ethics-toolkit/src/lib/email/send.ts:99-220`
- Square entitlements schema: `ethics-toolkit/supabase/migrations/001_initial_schema.sql:108-117`
- Flask shared spec template: `docs/templates/shared-spec-flask.md`
- Node shared spec template: `docs/templates/shared-spec-node.md`

### External References
- Square webhook verification: `squareup` pip package v44.0.1, `square.utils.webhooks_helper.verify_signature`
- Square webhook header: `x-square-hmacsha256-signature` (HMAC-SHA256 of URL+body, base64 encoded)
- Square payment events: `payment.updated` (check status field for COMPLETED/FAILED), `refund.created`
- Resend Python SDK: `resend` pip package v2.30.1, `resend.Emails.send()`, 5 req/s rate limit, no built-in retry
- Resend test sender: `onboarding@resend.dev` (pre-verified, for testing without custom domain)

### Solution Docs Referenced
- `2026-04-30-ethics-toolkit-platform-build.md` -- Integration seam failures, export name table
- `2026-04-30-spec-convergence-loop.md` -- P0s are cross-section contradictions
- `2026-03-30-chain-reaction-inter-service-contracts.md` -- Data ownership prevents double writes
- `2026-05-03-writers-room-council-swarm-build.md` -- Schema barrel gate, phased verification
- `2026-03-30-swarm-scale-shared-spec.md` -- Spec scaling formula, structural contracts

## Feed-Forward

- **Hardest decision:** Express proxying to Flask (instead of direct browser-to-Flask with CORS). This simplifies auth and CSRF but means Express is a bottleneck for all API traffic. If performance matters, the proxy can be replaced with direct calls + CORS later.
- **Rejected alternatives:** Direct browser-to-Flask (CORS complexity), Jinja2+HTMX (no cross-stack test), feature verticals (violates one-agent-one-job)
- **Least confident:** The `http-proxy-middleware` body parsing order interaction. Research confirms proxy must mount before `express.json()`, but the exact behavior when Express EJS form routes also need parsed bodies has not been tested in this codebase. The prescribed middleware order should work, but this is the integration seam most likely to cause subtle bugs (empty POST bodies reaching Flask).
