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
import json

from enrich_parsers import parse_bio, parse_profile_page

CONTACT_SCRAPER_ACTOR = "vdrmota/contact-info-scraper"

MAX_RESPONSE_BYTES = 1_000_000  # 1 MB cap per page

# Private IP ranges to block (SSRF protection)
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


@dataclass
class EnrichmentResult:
    leads_processed: int = 0
    emails_found: int = 0
    phones_found: int = 0
    social_found: int = 0


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
        # Check ALL resolved addresses, not just the first
        for _, _, _, _, sockaddr in addr_info:
            ip = ipaddress.ip_address(sockaddr[0])
            if any(ip in net for net in _PRIVATE_NETWORKS):
                return False
        return True
    except (socket.gaierror, ValueError, OSError):
        return False


def _fetch_page(session: requests.Session, url: str) -> str | None:
    """Fetch a URL with timeout, size cap, and SSRF protection."""
    if not _is_safe_url(url):
        return None
    try:
        resp = session.get(url, timeout=10, stream=True, allow_redirects=True)
        # Validate final URL after redirects (blocks redirect to private IPs)
        if str(resp.url) != url and not _is_safe_url(str(resp.url)):
            resp.close()
            return None
        if resp.status_code != 200:
            resp.close()
            return None
        content = resp.raw.read(MAX_RESPONSE_BYTES, decode_content=True)
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


def _get_leads_for_bio_parsing(db_path: Path = DB_PATH) -> list[dict]:
    """Get leads with bios that are missing email, phone, or social_handles."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, bio, profile_bio FROM leads "
            "WHERE (bio IS NOT NULL OR profile_bio IS NOT NULL) "
            "AND (email IS NULL OR phone IS NULL OR social_handles IS NULL)"
        ).fetchall()
    return [dict(row) for row in rows]


def _persist_bio_enrichment(
    lead_id: int, updates: dict, db_path: Path = DB_PATH
) -> None:
    """Write bio-parsed contact info. Only updates NULL columns."""
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE leads SET
                email = COALESCE(email, :email),
                phone = COALESCE(phone, :phone),
                social_handles = COALESCE(social_handles, :social_handles)
            WHERE id = :id""",
            {
                "email": updates.get("email"),
                "phone": updates.get("phone"),
                "social_handles": updates.get("social_handles"),
                "id": lead_id,
            },
        )


def enrich_from_bios(*, db_path: Path = DB_PATH) -> EnrichmentResult:
    """Parse bios for emails, phones, and social handles. No network calls."""
    leads = _get_leads_for_bio_parsing(db_path)
    if not leads:
        print("No leads to bio-parse.")
        return EnrichmentResult()

    result = EnrichmentResult()
    print(f"Bio-parsing {len(leads)} leads...")

    for i, lead in enumerate(leads, 1):
        bio_text = lead.get("bio") or ""
        profile_bio_text = lead.get("profile_bio") or ""
        combined = f"{bio_text}\n{profile_bio_text}".strip()

        if not combined:
            continue

        info = parse_bio(combined)
        updates: dict = {}

        if info.emails:
            updates["email"] = info.emails[0]
            result.emails_found += 1
        if info.phones:
            updates["phone"] = info.phones[0]
            result.phones_found += 1
        if info.social_handles:
            updates["social_handles"] = json.dumps(info.social_handles)
            result.social_found += 1

        if updates:
            _persist_bio_enrichment(lead["id"], updates, db_path)
            result.leads_processed += 1

    print(
        f"\nBio parsing complete. {result.leads_processed} enriched, "
        f"{result.emails_found} emails, {result.phones_found} phones, "
        f"{result.social_found} social handles."
    )
    return result


def _get_leads_for_website_crawl(db_path: Path = DB_PATH) -> list[dict]:
    """Get leads with websites that are still missing email."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name, website FROM leads "
            "WHERE website IS NOT NULL AND email IS NULL"
        ).fetchall()
    return [dict(row) for row in rows]


def _merge_social_handles(existing_json: str | None, new_handles: list[str]) -> str | None:
    """Merge new social handles into existing JSON array, deduplicating."""
    existing = json.loads(existing_json) if existing_json else []
    merged = list(existing)
    for h in new_handles:
        if h not in merged:
            merged.append(h)
    return json.dumps(merged) if merged else None


def enrich_websites_deep(*, db_path: Path = DB_PATH) -> EnrichmentResult:
    """Crawl lead websites with vdrmota/contact-info-scraper for contact info."""
    leads = _get_leads_for_website_crawl(db_path)
    if not leads:
        print("No websites to deep-crawl.")
        return EnrichmentResult()

    from scrapers._apify_helpers import run_actor

    # Build URL list for the actor
    urls = [lead["website"] for lead in leads]
    url_to_lead = {lead["website"]: lead for lead in leads}

    print(f"Deep-crawling {len(urls)} websites via {CONTACT_SCRAPER_ACTOR}...")

    try:
        raw_results = run_actor(
            CONTACT_SCRAPER_ACTOR,
            {
                "startUrls": [{"url": u} for u in urls],
                "maxDepth": 2,
                "maxRequestsPerStartUrl": 5,
            },
            timeout_secs=600,
        )
    except Exception as e:
        print(f"FAILED: {str(e)[:200]}")
        return EnrichmentResult()

    # Group results by domain to match back to leads
    result = EnrichmentResult()

    for item in raw_results:
        domain = item.get("domain", "")
        emails = item.get("emails", [])
        phones = item.get("phones", [])
        instagrams = item.get("instagrams", [])
        twitters = item.get("twitters", [])
        linkedins = item.get("linkedIns", [])
        facebooks = item.get("facebooks", [])

        if not emails and not phones and not instagrams and not twitters and not linkedins:
            continue

        # Match this result back to a lead by checking if any lead's website
        # contains this domain
        matched_lead = None
        for url, lead in url_to_lead.items():
            if domain and domain in url:
                matched_lead = lead
                break

        if not matched_lead:
            continue

        updates: dict = {}

        if emails:
            updates["email"] = emails[0]
            result.emails_found += 1
        if phones:
            digits = "".join(c for c in phones[0] if c.isdigit())
            if 7 <= len(digits) <= 16:
                updates["phone"] = digits
                result.phones_found += 1

        # Build social handles
        new_handles = []
        for ig in instagrams:
            handle = ig.rstrip("/").split("/")[-1]
            if handle:
                new_handles.append(f"instagram:{handle}")
        for tw in twitters:
            handle = tw.rstrip("/").split("/")[-1]
            if handle:
                new_handles.append(f"twitter:{handle}")
        for li in linkedins:
            parts = li.rstrip("/").split("/")
            if len(parts) >= 2:
                new_handles.append(f"linkedin:in/{parts[-1]}")
        for fb in facebooks:
            handle = fb.rstrip("/").split("/")[-1]
            if handle:
                new_handles.append(f"facebook:{handle}")

        if new_handles:
            # Read existing handles to merge
            with get_db(db_path) as conn:
                row = conn.execute(
                    "SELECT social_handles FROM leads WHERE id = ?",
                    (matched_lead["id"],)
                ).fetchone()
            existing = row["social_handles"] if row else None
            updates["social_handles"] = _merge_social_handles(existing, new_handles)
            result.social_found += 1

        if updates:
            with get_db(db_path) as conn:
                conn.execute(
                    """UPDATE leads SET
                        email = COALESCE(email, :email),
                        phone = COALESCE(phone, :phone),
                        social_handles = COALESCE(social_handles, :social_handles)
                    WHERE id = :id""",
                    {
                        "email": updates.get("email"),
                        "phone": updates.get("phone"),
                        "social_handles": updates.get("social_handles"),
                        "id": matched_lead["id"],
                    },
                )
            result.leads_processed += 1
            name = matched_lead["name"][:30]
            found = []
            if updates.get("email"):
                found.append(f"email={updates['email']}")
            if updates.get("phone"):
                found.append(f"phone={updates['phone']}")
            if new_handles:
                found.append(f"social={len(new_handles)}")
            print(f"  {name}: {', '.join(found)}")

    print(
        f"\nDeep crawl complete. {result.leads_processed} enriched, "
        f"{result.emails_found} emails, {result.phones_found} phones, "
        f"{result.social_found} social handles."
    )
    return result
