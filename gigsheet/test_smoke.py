"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re
import sys
import json
import tempfile

# Set secrets BEFORE any app imports
os.environ.setdefault("SECRET_KEY", "test-smoke-key")
os.environ.setdefault("SENDGRID_MODE", "mock")

# Add parent directory to path so `app` package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.db import init_db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

passed = 0
failed = 0
errors = []


def report(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  FAIL  {name} -- {detail}")


def csrf_token(response):
    """Extract CSRF token from a GET response."""
    html = response.data.decode()
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if match:
        return match.group(1)
    # Also try the meta-tag pattern some templates use
    match = re.search(r'name="csrf_token" content="([^"]+)"', html)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# App + Client Setup
# ---------------------------------------------------------------------------

app = create_app()
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = True  # keep CSRF on -- we extract tokens
app.config["SERVER_NAME"] = "localhost"

# Initialize the database with the schema
with app.app_context():
    init_db()

client = app.test_client()


# ---------------------------------------------------------------------------
# 1. Health check (no auth required)
# ---------------------------------------------------------------------------
print("\n=== Health & Public Routes ===")

r = client.get("/health")
report("GET /health -> 200", r.status_code == 200, f"got {r.status_code}")

data = json.loads(r.data)
report("GET /health body has status=ok", data.get("status") == "ok", f"got {data}")


# ---------------------------------------------------------------------------
# 2. Index redirect (not logged in)
# ---------------------------------------------------------------------------

r = client.get("/", follow_redirects=False)
report("GET / -> 302 (redirect to login)", r.status_code == 302, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 3. Auth pages
# ---------------------------------------------------------------------------
print("\n=== Auth Routes ===")

r = client.get("/auth/login")
report("GET /auth/login -> 200", r.status_code == 200, f"got {r.status_code}")

r = client.get("/auth/register")
report("GET /auth/register -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 4. Register a test user
# ---------------------------------------------------------------------------

r = client.get("/auth/register")
token = csrf_token(r)
report("CSRF token extractable from register page", token is not None, "no token found")

r = client.post("/auth/register", data={
    "csrf_token": token,
    "email": "smoketest@example.com",
    "password": "TestPass123!",
    "confirm_password": "TestPass123!",
    "display_name": "Smoke Tester",
}, follow_redirects=False)
report(
    "POST /auth/register -> 302",
    r.status_code == 302,
    f"got {r.status_code}",
)


# ---------------------------------------------------------------------------
# 5. Login with that user
# ---------------------------------------------------------------------------

r = client.get("/auth/login")
token = csrf_token(r)

r = client.post("/auth/login", data={
    "csrf_token": token,
    "email": "smoketest@example.com",
    "password": "TestPass123!",
}, follow_redirects=False)
report("POST /auth/login -> 302", r.status_code == 302, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 6. Workspace selection / creation
# ---------------------------------------------------------------------------
print("\n=== Workspace Routes ===")

r = client.get("/auth/workspaces")
report("GET /auth/workspaces -> 200", r.status_code == 200, f"got {r.status_code}")

token = csrf_token(r)

r = client.post("/auth/workspaces", data={
    "csrf_token": token,
    "name": "Smoke Workspace",
}, follow_redirects=False)
report("POST /auth/workspaces (create) -> 302", r.status_code == 302, f"got {r.status_code}")

# Select the workspace we just created
r = client.get("/auth/workspaces")
token = csrf_token(r)

r = client.post("/auth/workspaces/select", data={
    "csrf_token": token,
    "workspace_id": 1,
}, follow_redirects=False)
report("POST /auth/workspaces/select -> 302", r.status_code == 302, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 7. Dashboard (requires login + workspace)
# ---------------------------------------------------------------------------
print("\n=== Dashboard ===")

r = client.get("/dashboard/")
report("GET /dashboard/ -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 8. Leads
# ---------------------------------------------------------------------------
print("\n=== Lead Routes ===")

r = client.get("/leads/")
report("GET /leads/ -> 200", r.status_code == 200, f"got {r.status_code}")

r = client.get("/lead/new")
report("GET /lead/new -> 200", r.status_code == 200, f"got {r.status_code}")

token = csrf_token(r)

r = client.post("/lead/new", data={
    "csrf_token": token,
    "email": "venue@example.com",
    "venue_name": "The Blue Note",
    "contact_name": "Jane Booker",
    "capacity": "200",
    "location": "Chicago, IL",
    "genre_tags": "jazz",
    "phone": "312-555-1234",
    "website": "https://bluenote.example.com",
    "notes": "Smoke test lead",
}, follow_redirects=False)
report("POST /lead/new -> 302", r.status_code == 302, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 9. Tags
# ---------------------------------------------------------------------------
print("\n=== Tag Routes ===")

r = client.get("/tags/")
report("GET /tags/ -> 200", r.status_code == 200, f"got {r.status_code}")

token = csrf_token(r)

r = client.post("/tags/", data={
    "csrf_token": token,
    "name": "jazz-clubs",
    "color": "#ff5733",
}, follow_redirects=False)
report("POST /tags/ (create tag) -> 302", r.status_code == 302, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 10. Templates
# ---------------------------------------------------------------------------
print("\n=== Template Routes ===")

r = client.get("/templates/")
report("GET /templates/ -> 200", r.status_code == 200, f"got {r.status_code}")

r = client.get("/template/new")
report("GET /template/new -> 200", r.status_code == 200, f"got {r.status_code}")

token = csrf_token(r)

r = client.post("/template/new", data={
    "csrf_token": token,
    "name": "Booking Inquiry",
    "subject_line": "Booking inquiry for {{venue_name}}",
    "html_body": "<p>Hi {{contact_name}}, I'd love to play at {{venue_name}}.</p>",
}, follow_redirects=False)
report("POST /template/new -> 302", r.status_code == 302, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 11. Campaigns
# ---------------------------------------------------------------------------
print("\n=== Campaign Routes ===")

r = client.get("/campaigns/")
report("GET /campaigns/ -> 200", r.status_code == 200, f"got {r.status_code}")

r = client.get("/campaign/new")
report("GET /campaign/new -> 200", r.status_code == 200, f"got {r.status_code}")

token = csrf_token(r)

r = client.post("/campaign/new", data={
    "csrf_token": token,
    "name": "Smoke Campaign",
    "template_id": 1,
}, follow_redirects=False)
report("POST /campaign/new -> 302", r.status_code == 302, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 12. Pipeline
# ---------------------------------------------------------------------------
print("\n=== Pipeline Routes ===")

r = client.get("/pipeline/")
report("GET /pipeline/ -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 13. Analytics
# ---------------------------------------------------------------------------
print("\n=== Analytics Routes ===")

r = client.get("/analytics/")
report("GET /analytics/ -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 14. Workspace Settings
# ---------------------------------------------------------------------------
print("\n=== Workspace Settings Routes ===")

r = client.get("/workspace/")
report("GET /workspace/ -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 15. Members
# ---------------------------------------------------------------------------
print("\n=== Member Routes ===")

r = client.get("/members/")
report("GET /members/ -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 16. Files
# ---------------------------------------------------------------------------
print("\n=== File Routes ===")

r = client.get("/files/")
report("GET /files/ -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 17. Reports
# ---------------------------------------------------------------------------
print("\n=== Report Routes ===")

r = client.get("/reports/")
report("GET /reports/ -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 18. Import
# ---------------------------------------------------------------------------
print("\n=== Import Routes ===")

r = client.get("/import/")
report("GET /import/ -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 19. SendGrid Webhook (CSRF exempt)
# ---------------------------------------------------------------------------
print("\n=== Webhook Routes ===")

r = client.post("/webhooks/sendgrid",
    data=json.dumps([
        {
            "event": "delivered",
            "email": "venue@example.com",
            "sg_message_id": "mock-test123",
            "timestamp": 1716000000,
        }
    ]),
    content_type="application/json",
)
report("POST /webhooks/sendgrid -> 200", r.status_code == 200, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# 20. Auth-required redirect checks (logged out)
# ---------------------------------------------------------------------------
print("\n=== Auth Redirect Checks (new client, not logged in) ===")

anon_client = app.test_client()

auth_required_routes = [
    "/dashboard/",
    "/leads/",
    "/lead/new",
    "/templates/",
    "/template/new",
    "/campaigns/",
    "/campaign/new",
    "/tags/",
    "/pipeline/",
    "/analytics/",
    "/workspace/",
    "/members/",
    "/files/",
    "/reports/",
    "/import/",
]

for route in auth_required_routes:
    r = anon_client.get(route, follow_redirects=False)
    ok = r.status_code in (302, 303)
    report(f"GET {route} (anon) -> redirect", ok, f"got {r.status_code}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
total = passed + failed
print(f"Results: {passed}/{total} passed, {failed}/{total} failed")

if errors:
    print("\nFailed tests:")
    for e in errors:
        print(f"  - {e}")
    print(f"\n{failed} SMOKE TEST(S) FAILED")
    sys.exit(1)
else:
    print("\nALL SMOKE TESTS PASSED")
    sys.exit(0)
