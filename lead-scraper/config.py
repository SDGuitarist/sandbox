import os
from pathlib import Path

# Load .env file if it exists (project-local, sibling to this file).
# No python-dotenv dependency needed.
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _require_env(key: str) -> str:
    """Validate env var exists with clear error message."""
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def get_apify_token() -> str:
    return _require_env("APIFY_TOKEN")


# Source configs -- edit to add/remove groups and keywords
SOURCES = {
    "meetup": {
        "enabled": False,  # Requires paid Apify actor rental ($8/mo)
        "actor": "datapilot/meetup-event-scraper",
        "groups": [
            "https://www.meetup.com/filmnet-sd/",
        ],
    },
    "eventbrite": {
        "enabled": True,
        "actor": "aitorsm/eventbrite",
        "keywords": ["AI workshop", "film", "creative", "music production"],
        "country": "united-states",
        "city": "San Diego",
        "max_pages": 2,
    },
    "facebook": {
        "enabled": True,
        "actor": "apify/facebook-groups-scraper",
        "groups": [
            "https://www.facebook.com/groups/1488967914699762/",
            "https://www.facebook.com/groups/mexicanfilmmakerssd/",
        ],
    },
    "instagram": {
        "enabled": True,
        "actor": "apify/instagram-profile-scraper",
        "hashtags": [
            "SanDiegoFilmmaker",
            "SDCreatives",
            "SanDiegoPhotographer",
            "SanDiegoDesigner",
            "SDContentCreator",
        ],
        "max_profiles": 100,
    },
    "linkedin": {
        "enabled": False,  # Requires paid Apify actor rental
        "actor": "curious_coder/linkedin-people-search-scraper",
        "queries": [
            "filmmaker San Diego",
            "musician San Diego",
            "creative director San Diego",
        ],
    },
}
