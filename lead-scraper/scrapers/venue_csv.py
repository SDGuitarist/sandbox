"""Venue CSV scraper -- reads venue-scraper's outreach CSV as a lead source.

Maps venue CSV columns to LeadModel fields for ingest into lead-scraper.
This is the Phase 3 bridge between the two repos.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path


VENUE_SCRAPER_DIR = Path(os.environ.get(
    "VENUE_SCRAPER_DIR",
    str(Path(__file__).parent.parent.parent / "venue-scraper"),
))

# Column mapping: venue CSV -> lead-scraper fields
# See plan Phase 3 "Column mapping contract" table
_COLUMN_MAP = {
    "source_url": "profile_url",
    "name": "name",
    "email": "email",
    "phone": "phone",
    "website": "website",
    "description": "bio",
}


def normalize(row: dict) -> dict | None:
    """Map a venue CSV row to a lead-scraper dict.

    Returns None if the row is missing source_url (required for dedup).
    """
    source_url = (row.get("source_url") or "").strip()
    if not source_url:
        return None

    name = (row.get("name") or "").strip()
    if not name:
        return None

    lead = {
        "profile_url": source_url,
        "name": name,
        "source": "venue_scraper",
    }

    # Map optional fields
    for csv_col, lead_field in _COLUMN_MAP.items():
        if csv_col in ("source_url", "name"):
            continue  # Already handled
        value = (row.get(csv_col) or "").strip() or None
        lead[lead_field] = value

    # venue_type -> activity field with prefix
    venue_type = (row.get("venue_type") or "").strip()
    if venue_type:
        lead["activity"] = f"Venue: {venue_type}"

    return lead


def scrape(config: dict) -> list[dict]:
    """Read venue CSV and return normalized lead dicts.

    Args:
        config: Source config dict (may contain csv_path override).

    Returns:
        List of normalized lead dicts ready for ingest_leads().
    """
    csv_path = config.get("csv_path")
    if csv_path:
        path = Path(csv_path)
    else:
        path = VENUE_SCRAPER_DIR / "results" / "outreach.csv"

    if not path.exists():
        print(f"[venue_csv] No venue CSV found at {path}")
        return []

    leads = []
    skipped = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lead = normalize(row)
            if lead:
                leads.append(lead)
            else:
                skipped += 1

    print(f"[venue_csv] Read {len(leads)} venues from {path.name} ({skipped} skipped)")
    return leads
