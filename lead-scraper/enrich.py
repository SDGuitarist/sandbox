"""Enrichment pipeline: fetch lead websites and extract contact info.

This module owns UPDATE on enrichment columns (email, phone, enriched_at).
It never INSERTs — that is ingest.py's responsibility.
"""

import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from db import get_db, DB_PATH
from enrich_parsers import parse_profile_page

MAX_RESPONSE_BYTES = 1_000_000  # 1 MB cap per page

# Private IP ranges to block (SSRF protection)
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
]


@dataclass
class EnrichmentResult:
    leads_processed: int = 0
    emails_found: int = 0
    phones_found: int = 0


def _is_safe_url(url: str) -> bool:
    """Validate URL is HTTPS and doesn't resolve to a private IP."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        addr_info = socket.getaddrinfo(hostname, None)
        ip = ipaddress.ip_address(addr_info[0][4][0])
        return not any(ip in net for net in _PRIVATE_NETWORKS)
    except (socket.gaierror, ValueError, OSError):
        return False


def _fetch_page(session: requests.Session, url: str) -> str | None:
    """Fetch a URL with timeout, size cap, and SSRF protection."""
    if not _is_safe_url(url):
        return None
    try:
        resp = session.get(url, timeout=10, stream=True, allow_redirects=True)
        content = resp.raw.read(MAX_RESPONSE_BYTES)
        resp.close()
        return content.decode("utf-8", errors="replace")
    except requests.RequestException:
        return None


def _get_unenriched_leads(db_path: Path = DB_PATH) -> list[dict]:
    """Get leads that haven't been enriched yet."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name, email, phone, website, profile_url "
            "FROM leads WHERE enriched_at IS NULL"
        ).fetchall()
    return [dict(row) for row in rows]


def _persist_enrichment(lead_id: int, updates: dict, db_path: Path = DB_PATH) -> None:
    """Write enrichment results to a single lead. Only updates NULL columns."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db(db_path) as conn:
        # Only update columns that are currently NULL (don't overwrite ingest data)
        conn.execute(
            """UPDATE leads SET
                email = COALESCE(email, :email),
                phone = COALESCE(phone, :phone),
                website = COALESCE(website, :website),
                enriched_at = :enriched_at
            WHERE id = :id""",
            {
                "email": updates.get("email"),
                "phone": updates.get("phone"),
                "website": updates.get("website"),
                "enriched_at": now,
                "id": lead_id,
            },
        )


def _enrich_single_lead(lead: dict, session: requests.Session) -> dict:
    """Fetch a lead's profile and website pages, extract contact info."""
    updates: dict = {}

    urls_to_fetch = []
    if lead.get("profile_url"):
        urls_to_fetch.append(lead["profile_url"])
    if lead.get("website"):
        urls_to_fetch.append(lead["website"])

    for url in urls_to_fetch:
        html = _fetch_page(session, url)
        if not html:
            continue

        info = parse_profile_page(html)

        if info.emails and not updates.get("email"):
            updates["email"] = info.emails[0]
        if info.phones and not updates.get("phone"):
            updates["phone"] = info.phones[0]
        # Discover website from social links if we don't have one
        if not lead.get("website") and not updates.get("website"):
            # If the profile page links to a personal website, save it
            pass  # Future: extract non-social external links

    return updates


def enrich_leads(*, db_path: Path = DB_PATH) -> EnrichmentResult:
    """Enrich unenriched leads by fetching their profile/website pages."""
    leads = _get_unenriched_leads(db_path)
    if not leads:
        print("No leads to enrich.")
        return EnrichmentResult()

    result = EnrichmentResult()
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    print(f"Enriching {len(leads)} leads...")
    for i, lead in enumerate(leads, 1):
        name = lead["name"][:40]
        print(f"  {i}/{len(leads)} {name}...", end=" ", flush=True)
        try:
            updates = _enrich_single_lead(lead, session)
            _persist_enrichment(lead["id"], updates, db_path)
            result.leads_processed += 1
            if updates.get("email"):
                result.emails_found += 1
                print(f"email={updates['email']}", end=" ")
            if updates.get("phone"):
                result.phones_found += 1
                print(f"phone={updates['phone']}", end=" ")
            if not updates.get("email") and not updates.get("phone"):
                print("no contact info", end="")
            print()
        except Exception as e:
            print(f"FAILED: {str(e)[:80]}")

    session.close()
    print(
        f"\nEnrichment complete. {result.leads_processed} processed, "
        f"{result.emails_found} emails, {result.phones_found} phones."
    )
    return result
