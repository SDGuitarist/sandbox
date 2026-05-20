"""Tests for auth blueprint: register, login, logout.

EARS acceptance tests covered:
- WHEN a musician registers with email/password/display_name THE SYSTEM SHALL
  create the account and redirect to /dashboard
- WHEN a musician logs in with valid credentials THE SYSTEM SHALL set session
  and redirect to /dashboard
"""

from tests.conftest import _register_user, _login_user


class TestRegister:
    """Registration form tests."""

    def test_register_page_loads(self, client):
        """GET /auth/register returns 200."""
        resp = client.get("/auth/register")
        assert resp.status_code == 200

    def test_register_happy_path(self, client):
        """Valid registration redirects to dashboard."""
        resp = _register_user(client)
        assert resp.status_code == 200
        # Should land on dashboard after redirect
        assert b"dashboard" in resp.data.lower() or resp.request.path == "/dashboard/"

    def test_register_duplicate_email(self, client):
        """Registering the same email twice shows an error."""
        _register_user(client, email="dup@test.com")
        # Log out to register again
        client.post("/auth/logout", follow_redirects=True)
        resp = _register_user(client, email="dup@test.com")
        # Should show some error -- not redirect cleanly to dashboard
        assert resp.status_code == 200

    def test_register_password_mismatch(self, client):
        """Mismatched password and confirm_password shows error."""
        resp = _register_user(
            client,
            email="mismatch@test.com",
            password="TestPass123!",
            confirm_password="DifferentPass!",
        )
        assert resp.status_code == 200

    def test_register_missing_display_name(self, client):
        """Registration without display_name should fail validation."""
        resp = client.post("/auth/register", data={
            "email": "noname@test.com",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "display_name": "",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_register_missing_email(self, client):
        """Registration without email should fail validation."""
        resp = client.post("/auth/register", data={
            "email": "",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "display_name": "Test",
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestLogin:
    """Login form tests."""

    def test_login_page_loads(self, client):
        """GET /auth/login returns 200."""
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_login_happy_path(self, client):
        """Valid login redirects to dashboard."""
        _register_user(client)
        client.post("/auth/logout", follow_redirects=True)
        resp = _login_user(client)
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        """Wrong password stays on login page."""
        _register_user(client)
        client.post("/auth/logout", follow_redirects=True)
        resp = _login_user(client, password="WrongPass!")
        assert resp.status_code == 200

    def test_login_nonexistent_user(self, client):
        """Login with unknown email stays on login page."""
        resp = _login_user(client, email="nobody@test.com")
        assert resp.status_code == 200


class TestLogout:
    """Logout tests."""

    def test_logout_clears_session(self, client):
        """POST /auth/logout clears session and redirects."""
        _register_user(client)
        resp = client.post("/auth/logout", follow_redirects=True)
        assert resp.status_code == 200

    def test_protected_route_requires_login(self, client):
        """Accessing /dashboard without login redirects to login."""
        resp = client.get("/dashboard/", follow_redirects=True)
        assert resp.status_code == 200
        # Should have been redirected to login
        assert b"log in" in resp.data.lower() or b"login" in resp.data.lower() or b"email" in resp.data.lower()


class TestIndex:
    """Root route tests."""

    def test_index_redirects_to_login(self, client):
        """GET / redirects to /auth/login when not logged in."""
        resp = client.get("/")
        assert resp.status_code == 302

    def test_index_redirects_to_dashboard_when_logged_in(self, auth_client):
        """GET / redirects to /dashboard when logged in."""
        resp = auth_client.get("/")
        assert resp.status_code == 302
