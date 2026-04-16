from scrapers import NormalizedLead


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Convert one raw Apify Meetup result to a NormalizedLead."""
    name = raw_item.get("name")
    profile_url = raw_item.get("profileUrl")
    if not name or not profile_url:
        return None

    groups = raw_item.get("groups", [])
    events = raw_item.get("eventsAttended", 0)
    activity_parts = []
    if groups:
        activity_parts.append(f"Groups: {', '.join(groups)}")
    if events:
        activity_parts.append(f"Events attended: {events}")
    activity = ". ".join(activity_parts) if activity_parts else None

    return NormalizedLead(
        name=name,
        bio=raw_item.get("bio"),
        location=raw_item.get("city"),
        email=raw_item.get("email"),
        profile_url=profile_url,
        activity=activity,
        source="meetup",
    )


def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the Meetup Apify actor and normalize all results."""
    from scrapers._apify_helpers import run_actor

    run_input = {
        "startUrls": [{"url": url} for url in config.get("groups", [])],
        "location": location,
    }
    raw_items = run_actor(config["actor"], run_input)
    return [lead for item in raw_items if (lead := normalize(item)) is not None]
