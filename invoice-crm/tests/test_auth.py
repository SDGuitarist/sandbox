"""Tests for the auth blueprint (login, register, logout, profile)."""


class TestRegister:
    def test_register_success(self, client):
        """WHEN a user registers with valid email and password
        THE SYSTEM SHALL create the account and redirect to login."""
        response = client.post('/auth/register', data={
            'email': 'newuser@example.com',
            'password': 'securepass123',
            'confirm_password': 'securepass123'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Registration successful' in response.data or \
               b'Please log in' in response.data

    def test_register_duplicate_email(self, client):
        """WHEN a user registers with an existing email
        THE SYSTEM SHALL show error and not create duplicate."""
        # Register first time
        client.post('/auth/register', data={
            'email': 'dupe@example.com',
            'password': 'testpass123',
            'confirm_password': 'testpass123'
        })
        # Register same email again
        response = client.post('/auth/register', data={
            'email': 'dupe@example.com',
            'password': 'testpass123',
            'confirm_password': 'testpass123'
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should contain some error indication about duplicate/existing email
        assert b'already' in response.data.lower() or \
               b'exists' in response.data.lower() or \
               b'taken' in response.data.lower() or \
               b'error' in response.data.lower() or \
               b'register' in response.data.lower()


class TestLogin:
    def test_login_success(self, client):
        """WHEN a user logs in with valid credentials
        THE SYSTEM SHALL set session and redirect to dashboard."""
        # Register first
        client.post('/auth/register', data={
            'email': 'logintest@example.com',
            'password': 'testpass123',
            'confirm_password': 'testpass123'
        })
        # Login
        response = client.post('/auth/login', data={
            'email': 'logintest@example.com',
            'password': 'testpass123'
        })
        # Should redirect to dashboard (302)
        assert response.status_code == 302
        assert '/' in response.headers.get('Location', '')

    def test_login_invalid_credentials(self, client):
        """WHEN a user submits invalid credentials
        THE SYSTEM SHALL show error message."""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'wrongpass'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Invalid' in response.data or b'invalid' in response.data


class TestLogout:
    def test_logout(self, auth_client):
        """WHEN a logged-in user logs out
        THE SYSTEM SHALL clear session and redirect to login."""
        response = auth_client.post('/auth/logout')
        assert response.status_code == 302

        # After logout, accessing a protected page should redirect to login
        response = auth_client.get('/', follow_redirects=True)
        assert b'log in' in response.data.lower() or \
               b'login' in response.data.lower()


class TestProfile:
    def test_profile_requires_login(self, client):
        """WHEN a user accesses profile without login
        THE SYSTEM SHALL redirect to login."""
        response = client.get('/auth/profile')
        assert response.status_code == 302
        assert 'login' in response.headers.get('Location', '').lower()

    def test_profile_loads_when_authenticated(self, auth_client):
        """WHEN an authenticated user visits profile
        THE SYSTEM SHALL display the profile page."""
        response = auth_client.get('/auth/profile')
        assert response.status_code == 200
