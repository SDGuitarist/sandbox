from typing import TypedDict


class NormalizedLead(TypedDict):
    name: str
    bio: str | None
    location: str | None
    email: str | None
    website: str | None
    profile_url: str       # Required -- dedup key
    activity: str | None
    source: str            # Required -- dedup key
