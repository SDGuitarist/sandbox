"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re
import sys
import tempfile

os.environ.setdefault("SECRET_KEY", "test-smoke-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-strong-pw-123")
os.environ.setdefault("FLASK_DEBUG", "1")

tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp_db.close()
os.environ["DATABASE_PATH"] = tmp_db.name

from app import create_app
from app.db import init_db

app = create_app()
client = app.test_client()

with app.app_context():
    init_db()

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


def get_csrf(html_text):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html_text)
    return m.group(1) if m else ""


def login():
    r = client.get("/login")
    token = get_csrf(r.data.decode())
    client.post("/login", data={
        "password": os.environ["ADMIN_PASSWORD"],
        "csrf_token": token,
    }, follow_redirects=False)


# ============================================================
# Phase 1: HTTP status checks (unauthenticated)
# ============================================================

r = client.get("/health")
check("GET /health (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/login")
check("GET /login (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/")
check("GET / redirects to login when not logged in",
      r.status_code == 302, f"got {r.status_code}")

r = client.get("/recipes/")
check("GET /recipes/ redirects when not logged in",
      r.status_code == 302, f"got {r.status_code}")

# ============================================================
# Phase 2a: Auth write-side with real CSRF
# ============================================================

r = client.get("/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Login form has CSRF token", m is not None,
      "csrf_token input not found -- check {{ csrf_token() }} syntax")

csrf_token = m.group(1) if m else ""

r = client.post("/login", data={
    "password": os.environ["ADMIN_PASSWORD"],
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /login (redirect)", r.status_code == 302,
      f"got {r.status_code} -- CSRF token may be invalid")

with client.session_transaction() as sess:
    check("Login sets session['logged_in']",
          sess.get('logged_in') is True,
          f"session keys after login: {list(sess.keys())}")

# ============================================================
# Phase 2b: Navigate read-side (logged in)
# ============================================================

r = client.get("/")
check("GET / (dashboard, logged in)", r.status_code == 200,
      f"got {r.status_code}")

html = r.data.decode()
check("Dashboard has navbar links",
      "Recipes" in html and "Batches" in html,
      "navbar may be empty or broken")

# ============================================================
# Phase 3: Route-specific checks -- ALL 8 blueprints
# ============================================================

# --- Recipes blueprint ---

r = client.get("/recipes/")
check("GET /recipes/ (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/recipes/new")
check("GET /recipes/new (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/recipes/new")
token = get_csrf(r.data.decode())
r = client.post("/recipes/", data={
    "name": "Test IPA",
    "style": "IPA",
    "target_abv": "6.5",
    "notes": "Smoke test recipe",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /recipes/ (create, redirect)", r.status_code == 302,
      f"got {r.status_code}")

r = client.get("/recipes/1")
check("GET /recipes/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")
check("Recipe detail shows name", b"Test IPA" in r.data,
      "recipe name not found on detail page")

r = client.get("/recipes/1/edit")
check("GET /recipes/1/edit (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/recipes/1/edit")
token = get_csrf(r.data.decode())
r = client.post("/recipes/1/edit", data={
    "name": "Test IPA Updated",
    "style": "IPA",
    "target_abv": "7.0",
    "notes": "Updated notes",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /recipes/1/edit (update, redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Ingredients blueprint ---

r = client.get("/ingredients/")
check("GET /ingredients/ (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/ingredients/new")
check("GET /ingredients/new (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/ingredients/new")
token = get_csrf(r.data.decode())
r = client.post("/ingredients/", data={
    "name": "Pale Malt",
    "category": "grain",
    "stock_qty": "100.0",
    "unit": "lb",
    "low_stock_threshold": "10.0",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /ingredients/ (create, redirect)", r.status_code == 302,
      f"got {r.status_code}")

r = client.get("/ingredients/1")
check("GET /ingredients/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/ingredients/1/edit")
check("GET /ingredients/1/edit (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/ingredients/1/edit")
token = get_csrf(r.data.decode())
r = client.post("/ingredients/1/edit", data={
    "name": "Pale Malt",
    "category": "grain",
    "stock_qty": "95.0",
    "unit": "lb",
    "low_stock_threshold": "10.0",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /ingredients/1/edit (update, redirect)", r.status_code == 302,
      f"got {r.status_code}")

# Create a second ingredient for recipe ingredients test
r = client.get("/ingredients/new")
token = get_csrf(r.data.decode())
r = client.post("/ingredients/", data={
    "name": "Cascade Hops",
    "category": "hops",
    "stock_qty": "50.0",
    "unit": "lb",
    "low_stock_threshold": "5.0",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /ingredients/ (create hops, redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Add recipe ingredient ---

r = client.get("/recipes/1")
token = get_csrf(r.data.decode())
r = client.post("/recipes/1/ingredients", data={
    "ingredient_id": "1",
    "quantity": "10.0",
    "unit": "lb",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /recipes/1/ingredients (add ingredient, redirect)",
      r.status_code == 302, f"got {r.status_code}")

# --- Tanks blueprint ---

r = client.get("/tanks/")
check("GET /tanks/ (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/tanks/new")
check("GET /tanks/new (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/tanks/new")
token = get_csrf(r.data.decode())
r = client.post("/tanks/", data={
    "name": "Fermenter 1",
    "capacity_gallons": "15.0",
    "tank_type": "fermenter",
    "notes": "Primary fermenter",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /tanks/ (create, redirect)", r.status_code == 302,
      f"got {r.status_code}")

r = client.get("/tanks/1")
check("GET /tanks/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/tanks/1/edit")
check("GET /tanks/1/edit (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/tanks/1/edit")
token = get_csrf(r.data.decode())
r = client.post("/tanks/1/edit", data={
    "name": "Fermenter 1",
    "capacity_gallons": "15.0",
    "tank_type": "fermenter",
    "notes": "Updated notes",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /tanks/1/edit (update, redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Taps blueprint ---

r = client.get("/taps/")
check("GET /taps/ (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/taps/new")
check("GET /taps/new (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/taps/new")
token = get_csrf(r.data.decode())
r = client.post("/taps/", data={
    "name": "Tap 1",
    "position": "1",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /taps/ (create, redirect)", r.status_code == 302,
      f"got {r.status_code}")

r = client.get("/taps/1")
check("GET /taps/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/taps/1/edit")
check("GET /taps/1/edit (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/taps/1/edit")
token = get_csrf(r.data.decode())
r = client.post("/taps/1/edit", data={
    "name": "Tap 1",
    "position": "1",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /taps/1/edit (update, redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Batches blueprint ---

r = client.get("/batches/")
check("GET /batches/ (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/batches/new")
check("GET /batches/new (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/batches/new")
token = get_csrf(r.data.decode())
r = client.post("/batches/", data={
    "recipe_id": "1",
    "name": "Batch 001",
    "volume_gallons": "10.0",
    "notes": "Smoke test batch",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /batches/ (create, redirect)", r.status_code == 302,
      f"got {r.status_code}")

r = client.get("/batches/1")
check("GET /batches/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/batches/1/edit")
check("GET /batches/1/edit (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/batches/1/edit")
token = get_csrf(r.data.decode())
r = client.post("/batches/1/edit", data={
    "name": "Batch 001 Updated",
    "notes": "Updated notes",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /batches/1/edit (update, redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Start Brewing flow (derived state chain) ---

r = client.get("/batches/1")
token = get_csrf(r.data.decode())
r = client.post("/batches/1/start-brewing", data={
    "tank_id": "1",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /batches/1/start-brewing (redirect)", r.status_code == 302,
      f"got {r.status_code}")

# Advance: brewing -> fermenting
r = client.get("/batches/1")
token = get_csrf(r.data.decode())
r = client.post("/batches/1/advance", data={
    "new_status": "fermenting",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /batches/1/advance to fermenting (redirect)",
      r.status_code == 302, f"got {r.status_code}")

# Advance: fermenting -> conditioning
r = client.get("/batches/1")
token = get_csrf(r.data.decode())
r = client.post("/batches/1/advance", data={
    "new_status": "conditioning",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /batches/1/advance to conditioning (redirect)",
      r.status_code == 302, f"got {r.status_code}")

# Advance: conditioning -> ready (releases tank)
r = client.get("/batches/1")
token = get_csrf(r.data.decode())
r = client.post("/batches/1/advance", data={
    "new_status": "ready",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /batches/1/advance to ready (redirect)",
      r.status_code == 302, f"got {r.status_code}")

# Assign to tap: ready -> tapped
r = client.get("/batches/1")
token = get_csrf(r.data.decode())
r = client.post("/batches/1/assign-tap", data={
    "tap_id": "1",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /batches/1/assign-tap (redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Sales blueprint ---

r = client.get("/sales/")
check("GET /sales/ (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/sales/new")
check("GET /sales/new (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/sales/new")
token = get_csrf(r.data.decode())
r = client.post("/sales/", data={
    "tap_id": "1",
    "quantity_oz": "16",
    "sale_type": "pint",
    "price": "7.50",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /sales/ (create, redirect)", r.status_code == 302,
      f"got {r.status_code}")

r = client.get("/sales/1")
check("GET /sales/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")

# --- Staff blueprint ---

r = client.get("/staff/")
check("GET /staff/ (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/staff/new")
check("GET /staff/new (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/staff/new")
token = get_csrf(r.data.decode())
r = client.post("/staff/", data={
    "name": "Jane Brewer",
    "role": "brewer",
    "email": "jane@brewops.test",
    "phone": "555-0100",
    "hire_date": "2026-01-15",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /staff/ (create, redirect)", r.status_code == 302,
      f"got {r.status_code}")

r = client.get("/staff/1")
check("GET /staff/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/staff/1/edit")
check("GET /staff/1/edit (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/staff/1/edit")
token = get_csrf(r.data.decode())
r = client.post("/staff/1/edit", data={
    "name": "Jane Brewer",
    "role": "manager",
    "email": "jane@brewops.test",
    "phone": "555-0100",
    "hire_date": "2026-01-15",
    "status": "active",
    "csrf_token": token,
}, follow_redirects=False)
check("POST /staff/1/edit (update, redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Dashboard blueprint (re-check after data exists) ---

r = client.get("/")
check("GET / (dashboard with data, 200)", r.status_code == 200,
      f"got {r.status_code}")
html = r.data.decode()
check("Dashboard shows taps section",
      "Tap" in html or "tap" in html,
      "taps section missing from dashboard")

# --- Logout ---

r = client.get("/")
token = get_csrf(r.data.decode())
r = client.post("/logout", data={
    "csrf_token": token,
}, follow_redirects=False)
check("POST /logout (redirect)", r.status_code == 302,
      f"got {r.status_code}")

r = client.get("/")
check("GET / after logout (redirect to login)",
      r.status_code == 302, f"got {r.status_code}")

# ============================================================
# Cleanup temp DB
# ============================================================
try:
    os.unlink(tmp_db.name)
except OSError:
    pass

# ============================================================
# Summary
# ============================================================
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    sys.exit(1)
