"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re
import tempfile
os.environ.setdefault("SECRET_KEY", "test-smoke-key-not-production")
os.environ.setdefault("ADMIN_PASSWORD", "test-strong-pw-123")
_tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp_db.close()
os.unlink(_tmp_db.name)
os.environ.setdefault("DATABASE", _tmp_db.name)

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

# Phase 1: Public routes
r = client.get("/auth/login")
check("GET /auth/login (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/auth/register")
check("GET /auth/register (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/")
check("GET / (redirect to login)", r.status_code == 302, f"got {r.status_code}")

# Phase 2a: Auth with real CSRF
r = client.get("/auth/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Login form has CSRF token", m is not None, "csrf_token input not found")

csrf_token = m.group(1) if m else ""
r = client.post("/auth/login", data={
    "username": "producer",
    "password": os.environ["ADMIN_PASSWORD"],
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /auth/login (redirect)", r.status_code == 302, f"got {r.status_code}")

with client.session_transaction() as sess:
    check("Login sets session['user_id']",
          sess.get('user_id') is not None,
          f"session keys: {list(sess.keys())}")

# Phase 2b: Authenticated routes
r = client.get("/")
check("GET / (logged in, redirect to dashboard)", r.status_code in (200, 302), f"got {r.status_code}")

# Phase 3: Project-scoped routes (project_id=1 from seed)
project_routes = [
    "/scenes/1", "/cast/1", "/crew/1", "/departments/1",
    "/locations/1", "/schedule/1", "/call-sheets/1",
    "/budget/1", "/expenses/1", "/reports/1"
]
for route in project_routes:
    r = client.get(route)
    check(f"GET {route}", r.status_code == 200, f"got {r.status_code}")

# Phase 4: CSP header check
r = client.get("/auth/login")
csp = r.headers.get('Content-Security-Policy', '')
check("CSP includes cdn.jsdelivr.net", 'cdn.jsdelivr.net' in csp, f"CSP: {csp[:100]}")

# Summary
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
