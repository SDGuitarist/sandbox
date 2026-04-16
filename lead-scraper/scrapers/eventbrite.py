from scrapers import NormalizedLead


def _extract_city(location: dict | None) -> str | None:
    """Pull city from location address string, e.g. '742 5th Ave, San Diego, CA 92101'."""
    if not location or not location.get("address"):
        return None
    parts = location["address"].split(",")
    if len(parts) >= 2:
        # "San Diego, CA 92101" -> "San Diego, CA 92101"
        return ",".join(parts[1:]).strip()
    return location["address"]


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Convert one raw Apify Eventbrite result to a NormalizedLead.

    Returns None if the item has no usable organizer data.
    Tested independently via fixtures -- no Apify dependency.
    """
    organizer = raw_item.get("organizer")
    if not organizer or not organizer.get("name") or not organizer.get("url"):
        return None

    event_name = raw_item.get("name", "")
    activity = f"Organized: {event_name}" if event_name else None

    return NormalizedLead(
        name=organizer["name"],
        bio=organizer.get("description"),
        location=_extract_city(raw_item.get("location")),
        email=None,
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
