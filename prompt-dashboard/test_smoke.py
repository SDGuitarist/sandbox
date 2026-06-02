# prompt-dashboard/test_smoke.py
"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re
os.environ.setdefault("SECRET_KEY", "test-smoke-key")
os.environ.setdefault("FLASK_DEBUG", "1")

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

# --- Phase 1: HTTP status checks ---

r = client.get("/")
check("GET / (dashboard, 200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/prompts/new")
check("GET /prompts/new (200)", r.status_code == 200, f"got {r.status_code}")

# --- Phase 2a: CRUD write-side with real CSRF ---

r = client.get("/prompts/new")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Create form has CSRF token", m is not None,
      "csrf_token input not found -- check {{ csrf_token() }} syntax")

csrf_token = m.group(1) if m else ""

r = client.post("/prompts/create", data={
    "name": "Smoke Test Prompt",
    "description": "A test prompt",
    "system_prompt": "You are {{role}}",
    "user_prompt": "Hello {{name}}",
    "tags": "test, smoke",
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /prompts/create (redirect)", r.status_code == 302,
      f"got {r.status_code}")

# Follow redirect to detail page
r = client.get(r.headers.get('Location', '/prompts/1'))
check("GET /prompts/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")
html = r.data.decode()
check("Detail shows prompt name", "Smoke Test Prompt" in html,
      "prompt name not in detail page")

# --- Phase 2b: Read-side verification ---

r = client.get("/")
html = r.data.decode()
check("Dashboard shows prompt", "Smoke Test Prompt" in html,
      "prompt not on dashboard")
check("Dashboard has navbar", "href=" in html,
      "navbar may be missing")

# --- Phase 3: Version + Edit ---

r = client.get("/prompts/1/edit")
check("GET /prompts/1/edit (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/prompts/1/versions")
check("GET /prompts/1/versions (200)", r.status_code == 200,
      f"got {r.status_code}")

# --- Phase 4: Search ---

r = client.get("/?q=Smoke")
check("Search returns results", r.status_code == 200,
      f"got {r.status_code}")

# --- Phase 5: Testing page (no API key, should show warning) ---

r = client.get("/testing/1")
check("GET /testing/1 (200)", r.status_code == 200,
      f"got {r.status_code}")

# --- Phase 6: Delete ---

r = client.get("/prompts/1")  # Get CSRF from the detail page where delete button lives
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
csrf_token = m.group(1) if m else ""

r = client.post("/prompts/1/delete", data={
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /prompts/1/delete (redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Summary ---
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
