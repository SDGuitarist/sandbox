from scrapers import NormalizedLead


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Convert one raw Apify LinkedIn result to a NormalizedLead."""
    first = raw_item.get("firstName", "")
    last = raw_item.get("lastName", "")
    name = f"{first} {last}".strip()
    profile_url = raw_item.get("profileUrl")
    if not name or not profile_url:
        return None

    connections = raw_item.get("connectionCount", 0)
    summary = raw_item.get("summary")
    activity_parts = []
    if connections:
        activity_parts.append(f"{connections}+ connections")
    if summary:
        activity_parts.append(summary)
    activity = ". ".join(activity_parts) if activity_parts else None

    return NormalizedLead(
        name=name,
        bio=raw_item.get("headline"),
        location=raw_item.get("locationName"),
        email=None,
        profile_url=profile_url,
        activity=activity,
        source="linkedin",
    )


def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the LinkedIn Apify actor and normalize all results."""
    from scrapers._apify_helpers import run_actor

    run_input = {
        "searchQueries": config.get("queries", []),
        "location": location,
    }
    raw_items = run_actor(config["actor"], run_input)
    return [lead for item in raw_items if (lead := normalize(item)) is not None]
