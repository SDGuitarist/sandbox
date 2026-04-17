from scrapers import NormalizedLead


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Normalize the post author from a Facebook group post.

    The Apify facebook-groups-scraper returns posts, not member profiles.
    This extracts the post author as a single lead (maintains contract).
    """
    author_name = raw_item.get("name") or raw_item.get("userName")
    author_url = raw_item.get("profileUrl") or raw_item.get("url")
    if not author_name or not author_url:
        return None

    group_title = raw_item.get("groupTitle", "")
    activity = f"Posted in: {group_title}" if group_title else None

    return NormalizedLead(
        name=author_name,
        bio=(raw_item.get("text") or "")[:200] or None,
        location=None,
        email=None,
        website=None,
        profile_url=author_url,
        activity=activity,
        source="facebook",
    )


def _normalize_commenter(comment: dict, group_title: str) -> NormalizedLead | None:
    """Normalize a single commenter from a Facebook post comment."""
    name = comment.get("name") or comment.get("userName")
    url = comment.get("profileUrl") or comment.get("url")
    if not name or not url:
        return None

    activity = f"Commented in: {group_title}" if group_title else None

    return NormalizedLead(
        name=name,
        bio=(comment.get("text") or "")[:200] or None,
        location=None,
        email=None,
        website=None,
        profile_url=url,
        activity=activity,
        source="facebook",
    )


def extract_leads_from_post(raw_item: dict) -> list[NormalizedLead]:
    """Extract all leads (author + commenters) from a single Facebook post."""
    leads: list[NormalizedLead] = []
    author = normalize(raw_item)
    if author:
        leads.append(author)
    group_title = raw_item.get("groupTitle", "")
    for comment in raw_item.get("topComments", []):
        commenter = _normalize_commenter(comment, group_title)
        if commenter:
            leads.append(commenter)
    return leads


def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the Facebook Groups Apify actor and extract leads from posts."""
    from scrapers._apify_helpers import run_actor

    run_input = {
        "startUrls": [{"url": url} for url in config.get("groups", [])],
    }
    raw_items = run_actor(config["actor"], run_input)
    leads: list[NormalizedLead] = []
    for item in raw_items:
        leads.extend(extract_leads_from_post(item))
    return leads
