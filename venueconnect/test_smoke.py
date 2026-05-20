"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import sys
os.environ.setdefault('SECRET_KEY', 'test-smoke-key')
os.environ.setdefault('FLASK_DEBUG', '1')
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.db import init_db

app = create_app()
client = app.test_client()

with app.app_context():
    init_db()

passed = 0
failed = 0

def check(name, response, expected_status):
    global passed, failed
    if response.status_code == expected_status:
        passed += 1
        print(f"PASS: {name} ({response.status_code})")
    else:
        failed += 1
        print(f"FAIL: {name} -- expected {expected_status}, got {response.status_code}")

# Health check
check("GET /health", client.get("/health"), 200)

# Auth pages (unauthenticated)
check("GET /auth/login", client.get("/auth/login"), 200)
check("GET /auth/register", client.get("/auth/register"), 200)

# Redirect when not logged in
check("GET / redirects", client.get("/", follow_redirects=False), 302)

# Register a venue_manager test user
r = client.post("/auth/register", data={
    "username": "testuser",
    "email": "test@test.com",
    "password": "TestPass123!",
    "confirm_password": "TestPass123!",
    "role": "venue_manager",
    "display_name": "Test User",
}, follow_redirects=False)
# May be 302 (redirect on success) or 200 (form re-render on error)
print(f"INFO: Register response: {r.status_code}")

# Login as venue_manager
r = client.post("/auth/login", data={
    "username": "testuser",
    "password": "TestPass123!",
}, follow_redirects=False)
print(f"INFO: Login response: {r.status_code}")

# Dashboard (should work after login)
check("GET /dashboard/venue/", client.get("/dashboard/venue/"), 200)

# Venue CRUD
check("GET /venues/", client.get("/venues/"), 200)
check("GET /venues/new", client.get("/venues/new"), 200)

# Search
check("GET /search/", client.get("/search/"), 200)
check("GET /search/?q=jazz", client.get("/search/?q=jazz"), 200)

# Notifications
check("GET /notifications/", client.get("/notifications/"), 200)
check("GET /notifications/unread-count", client.get("/notifications/unread-count"), 200)

# Analytics
# Analytics returns 404 if user has no venues (expected for test user with no data)
r = client.get("/analytics/venue/")
print(f"INFO: GET /analytics/venue/ = {r.status_code} (404 expected if no venues)")

# Settlements
check("GET /settlements/", client.get("/settlements/"), 200)

# Logout
check("GET /auth/logout redirects", client.get("/auth/logout", follow_redirects=False), 302)

# --- Role protection: musician trying venue routes ---

# Register a musician test user
client.post("/auth/register", data={
    "username": "testmusician",
    "email": "musician@test.com",
    "password": "TestPass123!",
    "confirm_password": "TestPass123!",
    "role": "musician",
    "display_name": "Test Musician",
}, follow_redirects=True)

# Login as musician
client.post("/auth/login", data={
    "username": "testmusician",
    "password": "TestPass123!",
}, follow_redirects=True)

# Musician should be blocked from venue-only routes
check("Musician blocked from /venues/new", client.get("/venues/new"), 403)

# Musician-specific routes should work
check("GET /bookings/browse", client.get("/bookings/browse"), 200)
check("GET /bookings/mine", client.get("/bookings/mine"), 200)
check("GET /dashboard/musician/", client.get("/dashboard/musician/"), 200)
check("GET /analytics/musician/", client.get("/analytics/musician/"), 200)

print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
if failed > 0:
    print("SOME SMOKE TESTS FAILED")
    sys.exit(1)
else:
    print("ALL SMOKE TESTS PASSED")
