import csv
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from db import get_db, DB_PATH
from scrapers import NormalizedLead
from utils import sanitize_csv_cell

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"name", "profile_url", "source"}


class LeadModel(BaseModel):
    """Validates lead data at the ingest boundary before SQLite INSERT.

    Same shape as NormalizedLead TypedDict but with runtime enforcement.
    TypedDict = static type checking. BaseModel = runtime validation.
    """

    model_config = ConfigDict(strict=True)

    name: str = Field(min_length=1)
    bio: str | None = None
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    profile_url: str = Field(min_length=1)
    activity: str | None = None
    source: str = Field(min_length=1)

    @field_validator("profile_url")
    @classmethod
    def must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("profile_url must start with https://")
        return v

# Column mapping for flexible CSV headers (case-insensitive)
_CSV_FIELD_MAP = {
    "name": "name", "Name": "name",
    "profile_url": "profile_url", "Profile URL": "profile_url",
    "url": "profile_url", "URL": "profile_url",
    "bio": "bio", "Bio": "bio",
    "location": "location", "Location": "location",
    "email": "email", "Email": "email",
    "website": "website", "Website": "website",
    "phone": "phone", "Phone": "phone",
    "venue_type": "activity", "Venue Type": "activity",
}


def ingest_leads(leads: list[NormalizedLead], db_path=DB_PATH) -> tuple[int, int, int]:
    """Validate and insert leads. Returns (inserted, skipped, invalid) counts.

    This is the ONLY module that executes INSERT on the leads table.
    Validates each lead through LeadModel (Pydantic) before INSERT.
    """

    inserted = skipped = invalid = 0
    valid_leads = []

    for lead in leads:
        try:
            validated = LeadModel.model_validate(lead)
            valid_leads.append(validated.model_dump())
        except ValidationError as e:
            invalid += 1
            lead_name = lead.get("name", "<missing>")
            lead_source = lead.get("source", "<missing>")
            logger.warning(
                "Lead validation failed: name=%s source=%s errors=%s",
                lead_name,
                lead_source,
                e.errors(),
            )
            continue

    with get_db(db_path) as conn:
        for lead in valid_leads:
            conn.execute(
                """INSERT OR IGNORE INTO leads
                   (name, bio, location, email, phone, website, profile_url, activity, source)
                   VALUES (:name, :bio, :location, :email, :phone, :website, :profile_url, :activity, :source)""",
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

        # Warn about phone column (enrichment-only, not imported from CSV)
        if "phone" in {h.lower().strip() for h in (reader.fieldnames or [])}:
            print(
                "Note: 'phone' column found but not imported. "
                "Phone numbers come from the enrichment pipeline (enrich --step bio/hunter/venue)."
            )

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
