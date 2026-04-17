from scrapers import NormalizedLead


def _extract_city(venue: dict | None) -> str | None:
    """Pull city from venue/location data.

    Handles two formats:
    - Live API: primary_venue.address is a dict with localized_area_display
    - Old fixtures: location.address is a plain string like '742 5th Ave, San Diego, CA 92101'
    """
    if not venue:
        return None
    address = venue.get("address")
    if not address:
        return None
    # Old format: address is a string
    if isinstance(address, str):
        parts = address.split(",")
        if len(parts) >= 2:
            return ",".join(parts[1:]).strip()
        return address
    # Live API format: address is a dict
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

    Returns None if the item has no usable organizer data.
    Tested independently via fixtures -- no Apify dependency.
    """
    # Support both old fixture format ("organizer") and live API ("primary_organizer")
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
        profile_url=organizer["url"],
        activity=activity,
        source="eventbrite",
    )


def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the Eventbrite Apify actor and normalize all results.

    The actor accepts: country, city, category, keyword, maxPages.
    When multiple keywords are provided, we run the actor once per keyword
    with category='custom' and merge the results.
    """
    from scrapers._apify_helpers import run_actor

    city = config.get("city", location)
    country = config.get("country", "united-states")
    max_pages = config.get("max_pages", 5)
    keywords = config.get("keywords", [])

    all_items: list[dict] = []

    if keywords:
        # One actor run per keyword (actor only accepts a single keyword)
        for kw in keywords:
            run_input = {
                "country": country,
                "city": city,
                "category": "custom",
                "keyword": kw,
                "maxPages": max_pages,
            }
            items = run_actor(config["actor"], run_input)
            print(f"[{kw}: {len(items)}]", end=" ", flush=True)
            all_items.extend(items)
    else:
        # No keywords — broad search for the city
        run_input = {
            "country": country,
            "city": city,
            "maxPages": max_pages,
        }
        all_items = run_actor(config["actor"], run_input)

    return [lead for item in all_items if (lead := normalize(item)) is not None]
