from scrapers import NormalizedLead


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Convert one raw Instagram hashtag post to a NormalizedLead.

    The apify/instagram-hashtag-scraper returns posts, not profiles.
    We extract the post owner as the lead.
    """
    username = raw_item.get("ownerUsername")
    if not username:
        return None

    full_name = raw_item.get("ownerFullName") or username
    caption = (raw_item.get("caption") or "")[:200] or None
    likes = raw_item.get("likesCount", 0)
    activity = f"{likes} likes" if likes else None

    return NormalizedLead(
        name=full_name,
        bio=caption,
        location=raw_item.get("locationName"),
        email=None,
        website=None,
        profile_url=f"https://www.instagram.com/{username}",
        activity=activity,
        source="instagram",
    )


def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the Instagram Hashtag Apify actor and normalize results."""
    from scrapers._apify_helpers import run_actor

    hashtags = config.get("hashtags", [])
    max_profiles = config.get("max_profiles", 100)

    run_input = {
        "hashtags": hashtags,
        "resultsLimit": max_profiles,
    }

    raw_items = run_actor(config["actor"], run_input)
    return [lead for item in raw_items if (lead := normalize(item)) is not None]
