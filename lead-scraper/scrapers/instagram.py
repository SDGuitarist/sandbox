from scrapers import NormalizedLead


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Convert one raw Apify Instagram profile to a NormalizedLead."""
    username = raw_item.get("username")
    if not username:
        return None

    full_name = raw_item.get("fullName") or username
    followers = raw_item.get("followersCount", 0)
    category = raw_item.get("categoryName", "")
    activity_parts = []
    if followers:
        activity_parts.append(f"{followers} followers")
    if category:
        activity_parts.append(category)
    activity = ". ".join(activity_parts) if activity_parts else None

    return NormalizedLead(
        name=full_name,
        bio=raw_item.get("biography"),
        location=None,
        email=None,
        website=raw_item.get("externalUrl"),
        profile_url=f"https://www.instagram.com/{username}",
        activity=activity,
        source="instagram",
    )


def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the Instagram Profile Apify actor and normalize results."""
    from scrapers._apify_helpers import run_actor

    hashtags = config.get("hashtags", [])
    max_profiles = config.get("max_profiles", 100)

    # Build search URLs from hashtags
    usernames_or_urls = [f"https://www.instagram.com/explore/tags/{tag}/" for tag in hashtags]

    run_input = {
        "usernames": usernames_or_urls,
        "resultsLimit": max_profiles,
    }

    raw_items = run_actor(config["actor"], run_input)
    return [lead for item in raw_items if (lead := normalize(item)) is not None]
