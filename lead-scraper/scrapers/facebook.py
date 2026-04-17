from scrapers import NormalizedLead


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Convert one raw Apify Facebook group result to a NormalizedLead."""
    name = raw_item.get("name")
    profile_url = raw_item.get("profileUrl")
    if not name or not profile_url:
        return None

    group_name = raw_item.get("groupName", "")
    recent_posts = raw_item.get("recentPosts", 0)
    activity_parts = []
    if group_name:
        activity_parts.append(f"Active in: {group_name}")
    if recent_posts:
        activity_parts.append(f"Recent posts: {recent_posts}")
    activity = ". ".join(activity_parts) if activity_parts else None

    return NormalizedLead(
        name=name,
        bio=raw_item.get("about"),
        location=raw_item.get("location"),
        email=None,
        website=None,
        profile_url=profile_url,
        activity=activity,
        source="facebook",
    )


def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the Facebook Apify actor and normalize all results."""
    from scrapers._apify_helpers import run_actor

    run_input = {
        "startUrls": [{"url": url} for url in config.get("groups", [])],
    }
    raw_items = run_actor(config["actor"], run_input)
    return [lead for item in raw_items if (lead := normalize(item)) is not None]
