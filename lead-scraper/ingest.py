import csv
from pathlib import Path

from db import get_db, DB_PATH
from scrapers import NormalizedLead
from utils import sanitize_csv_cell

REQUIRED_FIELDS = {"name", "profile_url", "source"}

# Column mapping for flexible CSV headers (case-insensitive)
_CSV_FIELD_MAP = {
    "name": "name", "Name": "name",
    "profile_url": "profile_url", "Profile URL": "profile_url",
    "url": "profile_url", "URL": "profile_url",
    "bio": "bio", "Bio": "bio",
    "location": "location", "Location": "location",
    "email": "email", "Email": "email",
    "website": "website", "Website": "website",
}


def ingest_leads(leads: list[NormalizedLead], db_path=DB_PATH) -> tuple[int, int, int]:
    """Validate and insert leads. Returns (inserted, skipped, invalid) counts.

    This is the ONLY module that executes INSERT on the leads table.
    """

    inserted = skipped = invalid = 0
    valid_leads = []

    for lead in leads:
        # Validate required fields are present and non-empty
        if not all(lead.get(f) for f in REQUIRED_FIELDS):
            invalid += 1
            continue
        # Validate profile_url is https
        if not lead["profile_url"].lower().startswith("https://"):
            invalid += 1
            continue
        valid_leads.append(lead)

    with get_db(db_path) as conn:
        for lead in valid_leads:
            conn.execute(
                """INSERT OR IGNORE INTO leads
                   (name, bio, location, email, website, profile_url, activity, source)
                   VALUES (:name, :bio, :location, :email, :website, :profile_url, :activity, :source)""",
                lead,
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
            else:
                skipped += 1

    return inserted, skipped, invalid


def _normalize_csv_headers(headers: list[str]) -> dict[str, str]:
    """Map CSV headers to NormalizedLead fields. Case-insensitive, strip whitespace."""
    mapping = {}
    for h in headers:
        stripped = h.strip()
        # Try exact match first, then case-insensitive
        if stripped in _CSV_FIELD_MAP:
            mapping[h] = _CSV_FIELD_MAP[stripped]
        else:
            for csv_key, field in _CSV_FIELD_MAP.items():
                if stripped.lower() == csv_key.lower():
                    mapping[h] = field
                    break
    return mapping


def import_from_csv(csv_path: str, source: str = "csv_import", db_path=DB_PATH) -> tuple[int, int, int]:
    """Import leads from a CSV file with flexible column mapping.

    Maps only fields that ingest_leads() supports: name, bio, location,
    email, website, profile_url, source. Other columns (phone, mutual_friends,
    follower_count) are silently ignored.

    Returns (inserted, skipped, rejected).
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header_map = _normalize_csv_headers(reader.fieldnames or [])

        leads: list[NormalizedLead] = []
        rejected = 0

        for row in reader:
            mapped: dict = {}
            for csv_col, field_name in header_map.items():
                val = (row.get(csv_col) or "").strip()
                if val:
                    mapped[field_name] = sanitize_csv_cell(val)

            # Require name and profile_url
            if not mapped.get("name") or not mapped.get("profile_url"):
                rejected += 1
                continue

            # Auto-fix Facebook profile URLs missing https://
            url = mapped["profile_url"]
            if not url.lower().startswith("https://"):
                if url.isdigit() or url.startswith("profile.php"):
                    mapped["profile_url"] = f"https://www.facebook.com/{url}"
                else:
                    rejected += 1
                    continue

            lead: NormalizedLead = {
                "name": mapped["name"],
                "bio": mapped.get("bio"),
                "location": mapped.get("location"),
                "email": mapped.get("email"),
                "website": mapped.get("website"),
                "profile_url": mapped["profile_url"],
                "activity": None,
                "source": source,
            }
            leads.append(lead)

    if not leads:
        return 0, 0, rejected

    inserted, skipped, invalid = ingest_leads(leads, db_path)
    return inserted, skipped, rejected + invalid
