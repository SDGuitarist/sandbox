"""Verify-first: SSRF protection blocks private/loopback URLs at registration."""
import pytest

from dashboard.ssrf import SSRFError, validate_url


def test_loopback_rejected():
    with pytest.raises(SSRFError, match="loopback"):
        validate_url("http://127.0.0.1/health")


def test_localhost_rejected():
    with pytest.raises(SSRFError):
        validate_url("http://localhost/health")


def test_private_ip_rejected():
    with pytest.raises(SSRFError, match="private"):
        validate_url("http://192.168.1.1/health")


def test_private_10_rejected():
    with pytest.raises(SSRFError, match="private"):
        validate_url("http://10.0.0.1/health")


def test_link_local_rejected():
    with pytest.raises(SSRFError, match="link-local"):
        validate_url("http://169.254.169.254/health")  # AWS metadata


def test_cgnat_rejected():
    with pytest.raises(SSRFError, match="CGNAT"):
        validate_url("http://100.64.0.1/health")


def test_ipv6_loopback_rejected():
    with pytest.raises(SSRFError, match="loopback"):
        validate_url("http://[::1]/health")


def test_invalid_scheme_rejected():
    with pytest.raises(ValueError, match="scheme"):
        validate_url("ftp://example.com/health")


def test_no_hostname_rejected():
    with pytest.raises(ValueError):
        validate_url("http:///health")


def test_worker_uses_no_redirects(monkeypatch):
    """Verify that the worker passes allow_redirects=False when checking health."""
    import requests
    calls = []

    def mock_get(url, **kwargs):
        calls.append(kwargs)
        class R:
            status_code = 200
            elapsed = type("E", (), {"total_seconds": lambda self: 0.1})()
        return R()

    monkeypatch.setattr(requests, "get", mock_get)

    # Import the worker's check function and ensure it passes allow_redirects=False
    from dashboard.worker import check_service_url
    check_service_url("http://example.com/health")

    assert len(calls) == 1
    assert calls[0].get("allow_redirects") is False
