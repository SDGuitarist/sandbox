"""SSRF protection for service health check URLs.

Two-layer defense:
1. Registration time: resolve hostname, reject private/loopback/link-local IPs.
2. Worker time: allow_redirects=False so redirects to private IPs are blocked.

Known gap: DNS rebinding attacks can bypass layer 1 (register with public DNS that
later resolves to 127.0.0.1). Layer 2 does NOT protect against this for the initial
request — only for redirect-based rebinding.
"""
import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(Exception):
    """Raised when a URL fails SSRF validation."""


def validate_url(url: str):
    """Validate that a URL does not point to a private/loopback/link-local IP.

    Raises SSRFError if the URL is unsafe.
    Raises ValueError if the URL is malformed.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must use http or https scheme, got '{parsed.scheme}'")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    # Reject raw IP literals before DNS resolution
    try:
        ip = ipaddress.ip_address(hostname)
        _check_ip(ip, hostname)
        return  # valid public IP literal
    except ValueError:
        pass  # not an IP literal — continue to DNS resolution

    # Resolve hostname and check each returned IP
    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFError(f"Cannot resolve hostname '{hostname}': {e}") from e

    for result in results:
        addr = result[4][0]
        try:
            ip = ipaddress.ip_address(addr)
            _check_ip(ip, hostname)
        except SSRFError:
            raise
        except ValueError:
            continue


def _check_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str):
    """Raise SSRFError if the IP is private, loopback, link-local, or CGNAT."""
    if ip.is_loopback:
        raise SSRFError(f"'{hostname}' resolves to loopback address {ip}")
    if ip.is_link_local:
        raise SSRFError(f"'{hostname}' resolves to link-local address {ip}")
    if ip.is_private:
        raise SSRFError(f"'{hostname}' resolves to private address {ip}")
    if ip.is_multicast:
        raise SSRFError(f"'{hostname}' resolves to multicast address {ip}")
    # CGNAT range 100.64.0.0/10
    if isinstance(ip, ipaddress.IPv4Address):
        cgnat = ipaddress.IPv4Network("100.64.0.0/10")
        if ip in cgnat:
            raise SSRFError(f"'{hostname}' resolves to CGNAT address {ip}")
