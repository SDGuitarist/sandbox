from scrapers import NormalizedLead


def _extract_city(venue: dict | None) -> str | None:
    """Pull city from venue/location data.

    Handles two formats:
    - Live API: primary_venue.address is a dict with localized_area_display
    - Old fixtures: location.address is a plain string
    """
    if not venue:
        return None
    address = venue.get("address")
    if not address:
        return None
    if isinstance(address, str):
        parts = address.split(",")
        if len(parts) >= 2:
            return ",".join(parts[1:]).strip()
        return address
    area = address.get("localized_area_display")
    if area:
        return area
    city = address.get("city", "")
    region = address.get("region", "")
    if city and region:
        return f"{city}, {region}"
    return city or None


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Convert one raw Apify Eventbrite result to a NormalizedLead.

    Handles both live API format (primary_organizer) and old fixtures (organizer).
    Returns None if the item has no usable organizer data.
    """
    organizer = raw_item.get("primary_organizer") or raw_item.get("organizer")
    if not organizer or not organizer.get("name") or not organizer.get("url"):
        return None

    event_name = raw_item.get("name", "")
    activity = f"Organized: {event_name}" if event_name else None
    venue = raw_item.get("primary_venue") or raw_item.get("location")

    return NormalizedLead(
        name=organizer["name"],
        bio=organizer.get("summary") or organizer.get("description"),
        location=_extract_city(venue),
        email=None,
        website=organizer.get("website_url"),
        profile_url=organizer["url"],
        activity=activity,
        source="eventbrite",
    )


def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the Eventbrite Apify actor and normalize all results."""
    from scrapers._apify_helpers import run_actor

    run_input = {
        "searchQueries": config.get("keywords", []),
        "location": location,
        "maxItems": config.get("max_pages", 5) * 10,
    }

    raw_items = run_actor(config["actor"], run_input)
    return [lead for item in raw_items if (lead := normalize(item)) is not None]
