from scrapers import NormalizedLead


def normalize(raw_item: dict) -> NormalizedLead | None:
    """Normalize the post author from a Facebook group post.

    The Apify facebook-groups-scraper returns posts with author in a nested
    ``user`` dict (keys: ``name``, ``id``). Falls back to flat fields for
    forward-compatibility.
    """
    user = raw_item.get("user") or {}
    author_name = user.get("name") or raw_item.get("name") or raw_item.get("userName")
    # Build profile URL from numeric user ID, fall back to post permalink
    user_id = str(user.get("id", ""))
    if user_id.isdigit():
        author_url = f"https://www.facebook.com/profile.php?id={user_id}"
    else:
        author_url = raw_item.get("profileUrl") or raw_item.get("url")
    if not author_name or not author_url:
        return None

    group_label = raw_item.get("facebookUrl") or raw_item.get("groupTitle", "")
    activity = f"Posted in: {group_label}" if group_label else None

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


def _normalize_commenter(comment: dict, group_url: str) -> NormalizedLead | None:
    """Normalize a single commenter from a Facebook post comment."""
    name = comment.get("profileName") or comment.get("name") or comment.get("userName")
    url = comment.get("profileUrl") or comment.get("url")
    if not name or not url:
        return None

    activity = f"Commented in: {group_url}" if group_url else None

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
    group_label = raw_item.get("facebookUrl") or raw_item.get("groupTitle", "")
    for comment in raw_item.get("topComments", []):
        commenter = _normalize_commenter(comment, group_label)
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
