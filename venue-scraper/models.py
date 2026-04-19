"""Pydantic schema and validation for venue data extraction.

Pydantic over TypedDict: LLM output requires runtime validation.
This module also co-locates the extraction prompt with the schema it describes,
since they change together.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class VenueData(BaseModel):
    name: str
    description: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    booking_url: str | None = None
    website: str | None = None
    social_links: list[str] = Field(default_factory=list)
    capacity: int | None = None
    capacity_range: str | None = None
    pricing: str | None = None
    pricing_range: str | None = None
    amenities: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    venue_type: str | None = None
    photos: list[str] = Field(default_factory=list, max_length=20)
    star_rating: float | None = None
    review_count: int | None = None
    source_url: str
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


EXTRACTION_PROMPT = """Extract venue information from this page.
Rules:
- Return null for any field not explicitly stated on the page. Never guess.
- For capacity, extract the maximum number of guests if a range is given.
- For pricing, include the unit (per hour, per event, per person).
- Combine all amenities into a flat list of short strings.
- For social links, include full URLs only.
- Prefer the most specific mention when data conflicts on the page.
"""


def merge_venue_results(venues: list[VenueData]) -> VenueData | None:
    """Merge multiple VenueData results into one, preferring first non-null values.

    Scalar fields: take the first non-null.
    List fields: merge all, deduplicate, preserve order.
    """
    if not venues:
        return None
    if len(venues) == 1:
        return venues[0]

    base = venues[0].model_copy()

    for venue in venues[1:]:
        # Scalar fields: fill nulls from later pages
        for field in ("name", "description", "email", "phone", "address",
                      "booking_url", "website", "capacity", "capacity_range",
                      "pricing", "pricing_range", "venue_type", "star_rating",
                      "review_count"):
            if getattr(base, field) is None and getattr(venue, field) is not None:
                setattr(base, field, getattr(venue, field))

        # List fields: merge with dedup
        for field in ("social_links", "amenities", "event_types", "photos"):
            existing = getattr(base, field)
            new_items = getattr(venue, field)
            for item in new_items:
                if item not in existing:
                    existing.append(item)

    return base


def validate_extraction(raw_json: str | dict | list, source_url: str) -> VenueData | None:
    """Validate raw LLM extraction output into a VenueData instance.

    This is the venue-scraper equivalent of lead-scraper's normalize().
    Independently testable with JSON fixtures -- no API calls needed.
    """
    try:
        if isinstance(raw_json, str):
            data = json.loads(raw_json)
        else:
            data = raw_json

        # Handle list output (Crawl4AI may return array of results)
        if isinstance(data, list):
            if not data:
                return None
            data = data[0]

        data["source_url"] = source_url
        return VenueData(**data)
    except (json.JSONDecodeError, ValueError, IndexError, TypeError):
        return None
