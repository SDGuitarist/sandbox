from db import get_db, DB_PATH
from scrapers import NormalizedLead

REQUIRED_FIELDS = {"name", "profile_url", "source"}


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
