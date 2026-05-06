"""export.py -- JSON results -> sanitized CSV outreach list.

Applies formula injection prevention on all cells.
Skips venues with no email AND no phone (not actionable for outreach).
"""
from __future__ import annotations

import csv
from pathlib import Path

OUTREACH_COLUMNS = ["name", "email", "phone", "website", "venue_type"]


def sanitize_cell(value: str | None) -> str:
    """Prevent CSV formula injection.

    1. Strips control characters (tab, carriage return, newline)
    2. Prefixes cells starting with =, -, +, @, or | with a single quote

    (see: lead-scraper solution doc + liverequest CSV export lesson)
    """
    if not value:
        return ""
    # Strip control characters that can break cell boundaries
    value = value.strip()
    value = value.replace("\t", " ").replace("\r", "").replace("\n", " ")
    if value and value[0] in "=-+@|":
        return "'" + value
    return value


def export_outreach_csv(results: list[dict], output_path: Path) -> int:
    """Write venue results as a sanitized CSV outreach list.

    Args:
        results: List of VenueData dicts (from model_dump).
        output_path: Full path to output CSV file.

    Returns:
        Number of rows written (excluding header).
        Creates file with header even if zero rows qualify.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTREACH_COLUMNS)
        writer.writeheader()

        for venue in results:
            email = venue.get("email")
            phone = venue.get("phone")

            # Skip venues with no contact info (not actionable)
            if not email and not phone:
                continue

            row = {
                "name": sanitize_cell(venue.get("name")),
                "email": sanitize_cell(email),
                "phone": sanitize_cell(phone),
                "website": sanitize_cell(venue.get("source_url") or venue.get("website")),
                "venue_type": sanitize_cell(venue.get("venue_type")),
            }
            writer.writerow(row)
            rows_written += 1

    print(f"[export] Wrote {rows_written} venues to {output_path}")
    return rows_written
