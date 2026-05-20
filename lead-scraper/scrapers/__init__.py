from typing import TypedDict


# DEPRECATED: use LeadModel (in ingest.py) for runtime validation.
# This TypedDict remains for backward-compatible type annotations in scrapers.
class NormalizedLead(TypedDict):
    name: str
    bio: str | None
    location: str | None
    email: str | None
    website: str | None
    profile_url: str       # Required -- dedup key
    activity: str | None
    source: str            # Required -- dedup key
