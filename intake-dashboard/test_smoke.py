"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re

os.environ.setdefault("SECRET_KEY", "test-smoke-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-strong-pw-123")
os.environ.setdefault("ADMIN_USERNAME", "admin")

from app import create_app

app = create_app()
client = app.test_client()

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS: {name}")
        passed += 1
    else:
        print(f"FAIL: {name} -- {detail}")
        failed += 1


# --- Phase 1: Public routes (no auth) ---

r = client.get("/health")
check("GET /health (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/intake")
check("GET /intake (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/intake/thank-you")
check("GET /intake/thank-you (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/login")
check("GET /login (200)", r.status_code == 200, f"got {r.status_code}")

# Admin routes redirect to login when not authenticated
r = client.get("/admin/")
check("GET /admin/ (302 to login)", r.status_code == 302, f"got {r.status_code}")

r = client.get("/admin/submissions")
check("GET /admin/submissions (302 to login)", r.status_code == 302, f"got {r.status_code}")

# --- Phase 2a: Auth write-side with real CSRF ---

r = client.get("/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Login form has CSRF token", m is not None,
      "csrf_token input not found -- check {{ csrf_token() }} syntax")

csrf_tok = m.group(1) if m else ""

r = client.post("/login", data={
    "username": "admin",
    "password": os.environ["ADMIN_PASSWORD"],
    "csrf_token": csrf_tok,
}, follow_redirects=False)
check("POST /login (redirect)", r.status_code == 302,
      f"got {r.status_code} -- CSRF token may be invalid")

with client.session_transaction() as sess:
    check("Login sets session['logged_in']",
          sess.get('logged_in') is True,
          f"session keys after login: {list(sess.keys())}")

# --- Phase 2b: Admin routes accessible after login ---

r = client.get("/admin/")
check("GET /admin/ (200, logged in)", r.status_code == 200, f"got {r.status_code}")

html = r.data.decode()
check("Dashboard has navbar links",
      "Submissions" in html and "Dashboard" in html,
      "navbar may be broken -- check session key in base.html")

r = client.get("/admin/submissions")
check("GET /admin/submissions (200)", r.status_code == 200, f"got {r.status_code}")

# --- Phase 3: Intake form submission with CSRF ---

r = client.get("/intake")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Intake form has CSRF token", m is not None)
csrf_tok = m.group(1) if m else ""

r = client.post("/intake", data={
    "contact_name": "Test User",
    "email": "test@example.com",
    "business_name": "Test Corp",
    "business_type": "SaaS",
    "team_size": "5-10",
    "current_workflows": "Manual data entry in spreadsheets",
    "pain_points": "Too slow, error-prone",
    "tools_used": "Excel, Google Docs",
    "goals": "Automate repetitive tasks",
    "urgency": "Next 30 days",
    "submitter_notes": "",
    "website": "",
    "csrf_token": csrf_tok,
}, follow_redirects=False)
check("POST /intake (302 to thank-you)", r.status_code == 302, f"got {r.status_code}")

# --- Phase 4: Verify submission appears in admin ---

r = client.get("/admin/submissions")
html = r.data.decode()
check("Submission visible in list", "Test Corp" in html,
      "submitted business_name not found in list")

# Find the submission link
m = re.search(r'href="(/admin/submissions/\d+)"', html)
check("Submission has detail link", m is not None)

if m:
    detail_url = m.group(1)
    r = client.get(detail_url)
    check("GET submission detail (200)", r.status_code == 200, f"got {r.status_code}")
    html = r.data.decode()
    check("Detail shows contact name", "Test User" in html)
    check("Detail shows email", "test@example.com" in html)
    check("Detail shows status badge", "new" in html.lower())

    # Extract submission_id from URL
    sub_id = detail_url.split("/")[-1]

    # --- Phase 5: Add a note ---
    r = client.get(detail_url)
    html = r.data.decode()
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/notes", data={
        "content": "Looks like a strong lead",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST add note (302)", r.status_code == 302, f"got {r.status_code}")

    r = client.get(detail_url)
    html = r.data.decode()
    check("Note visible on detail", "Looks like a strong lead" in html)

    # --- Phase 6: Change status ---
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/status", data={
        "new_status": "reviewed",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST change status (302)", r.status_code == 302, f"got {r.status_code}")

    r = client.get(detail_url)
    html = r.data.decode()
    check("Status updated to reviewed", "reviewed" in html.lower())

    # --- Phase 7: Create assessment ---
    r = client.get(f"/admin/submissions/{sub_id}/assessment")
    check("GET assessment form (200)", r.status_code == 200, f"got {r.status_code}")

    html = r.data.decode()
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/assessment", data={
        "summary": "Strong candidate for automation audit",
        "bottlenecks": "Manual data entry, no integration",
        "root_causes": "Legacy spreadsheet workflows",
        "next_steps": "Schedule 60-min audit call",
        "audit_fit_recommendation": "High fit -- clear ROI",
        "admin_notes": "Follow up by Friday",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST create assessment (302)", r.status_code == 302, f"got {r.status_code}")

    r = client.get(detail_url)
    html = r.data.decode()
    check("Assessment visible on detail", "Strong candidate" in html)

    # --- Phase 8: Toggle audit fit ---
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/audit-fit", data={
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST toggle audit-fit (302)", r.status_code == 302, f"got {r.status_code}")

    # --- Phase 9: Filter by status ---
    r = client.get("/admin/submissions?status=reviewed")
    html = r.data.decode()
    check("Filter by status=reviewed shows result", "Test Corp" in html)

    r = client.get("/admin/submissions?status=completed")
    html = r.data.decode()
    check("Filter by status=completed shows no result", "Test Corp" not in html)

    # --- Phase 10: Terminal status enforcement ---
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', client.get(detail_url).data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/status", data={
        "new_status": "completed",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST set terminal status (302)", r.status_code == 302, f"got {r.status_code}")

    # Try to change from terminal status
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', client.get(detail_url).data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/status", data={
        "new_status": "new",
        "csrf_token": csrf_tok,
    }, follow_redirects=True)
    html = r.data.decode()
    check("Terminal status blocks change", "cannot" in html.lower() or "Cannot" in html)

    # --- Phase 11: Honeypot rejection ---
    r = client.get("/intake")
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post("/intake", data={
        "contact_name": "Bot User",
        "email": "bot@spam.com",
        "business_name": "Spam Corp",
        "business_type": "Spam",
        "team_size": "1",
        "current_workflows": "Spam",
        "pain_points": "Spam",
        "tools_used": "Spam",
        "goals": "Spam",
        "urgency": "Now",
        "submitter_notes": "",
        "website": "http://spam.com",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("Honeypot submission redirects (302)", r.status_code == 302, f"got {r.status_code}")

    # Verify honeypot submission was NOT saved
    r = client.get("/admin/submissions")
    html = r.data.decode()
    check("Honeypot submission not in list", "Spam Corp" not in html)

    # --- Phase 12: Logout ---
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', client.get("/admin/").data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post("/logout", data={
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST /logout (302)", r.status_code == 302, f"got {r.status_code}")

    r = client.get("/admin/")
    check("Admin redirects after logout", r.status_code == 302, f"got {r.status_code}")


# --- Summary ---
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
