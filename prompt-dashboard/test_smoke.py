# prompt-dashboard/test_smoke.py
"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re
import tempfile
from cryptography.fernet import Fernet

os.environ.setdefault("SECRET_KEY", "test-smoke-key-not-production")
os.environ.setdefault("PROMPT_ENCRYPTION_KEY", Fernet.generate_key().decode())

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
os.unlink(_tmp.name)
os.environ.setdefault("DATABASE", _tmp.name)

from app import create_app

app = create_app()
client = app.test_client()

# Seed the database
with app.app_context():
    from app.database import get_db
    conn = get_db()
    # Quick seed: just check if component_definitions is empty
    if conn.execute('SELECT COUNT(*) FROM component_definitions').fetchone()[0] == 0:
        from click.testing import CliRunner
        runner = CliRunner()
        with app.app_context():
            result = runner.invoke(app.cli, ['seed'])

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
r = client.get("/health")
check("GET /health", r.status_code == 200, f"got {r.status_code}")

r = client.get("/")
check("GET / redirects to login", r.status_code == 302, f"got {r.status_code}")

r = client.get("/auth/login")
check("GET /auth/login", r.status_code == 200, f"got {r.status_code}")

r = client.get("/auth/register")
check("GET /auth/register", r.status_code == 200, f"got {r.status_code}")

r = client.get("/share/invalid-token-12345")
check("GET /share/invalid returns 404", r.status_code == 404, f"got {r.status_code}")

# Phase 2: Auth with CSRF
r = client.get("/auth/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Login form has CSRF token", m is not None, "csrf_token input not found")

csrf_token = m.group(1) if m else ""
r = client.post("/auth/login", data={
    "username": "alex",
    "password": "admin-password-123",
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /auth/login redirects", r.status_code == 302, f"got {r.status_code}")

with client.session_transaction() as sess:
    check("Login sets session['user_id']", sess.get('user_id') is not None,
          f"session keys: {list(sess.keys())}")
    check("Login sets session['role']", sess.get('role') == 'admin',
          f"role: {sess.get('role')}")

# Phase 3: Authenticated routes
r = client.get("/library")
check("GET /library (authenticated)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/wizard")
check("GET /wizard (industry selection)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/wizard/new?industry_id=1")
check("GET /wizard/new", r.status_code == 200, f"got {r.status_code}")

r = client.get("/search?q=email")
check("GET /search", r.status_code == 200, f"got {r.status_code}")

# Phase 4: Admin routes
r = client.get("/admin")
check("GET /admin (admin user)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/templates")
check("GET /admin/templates", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/prompts")
check("GET /admin/prompts", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/guidance")
check("GET /admin/guidance", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/tokens")
check("GET /admin/tokens", r.status_code == 200, f"got {r.status_code}")

r = client.get("/admin/export")
check("GET /admin/export", r.status_code == 200, f"got {r.status_code}")

# Phase 5: Wizard save flow
r = client.get("/wizard/new?industry_id=1")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
csrf_token = m.group(1) if m else ""

r = client.post("/wizard/save", data={
    "title": "Smoke Test Prompt",
    "industry_id": "1",
    "component_1": "I am a tester",
    "component_4": "Test the wizard save flow",
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /wizard/save redirects", r.status_code == 302, f"got {r.status_code}")

# Phase 6: Verify encryption
with app.app_context():
    conn = get_db()
    row = conn.execute(
        "SELECT content FROM prompt_components WHERE prompt_id = (SELECT MAX(id) FROM prompts) AND component_id = 1"
    ).fetchone()
    check("Component content is encrypted", row is not None and row['content'] != 'I am a tester',
          f"content appears plaintext: {row['content'][:50] if row else 'NULL'}")

# Phase 7: IDOR check (log in as non-admin, try to access admin)
r = client.post("/auth/logout", data={"csrf_token": csrf_token}, follow_redirects=False)

r = client.get("/auth/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
csrf_token = m.group(1) if m else ""

r = client.post("/auth/login", data={
    "username": "workshop_user",
    "password": "user-password-123",
    "csrf_token": csrf_token,
}, follow_redirects=False)

r = client.get("/admin")
check("Non-admin blocked from /admin", r.status_code == 403, f"got {r.status_code}")

# Summary
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
