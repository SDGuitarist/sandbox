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


def get_perplexity_key() -> str | None:
    """Get Perplexity API key. Returns None if not set (non-fatal)."""
    return os.getenv("PERPLEXITY_API_KEY")


# Template discovery uses repo-relative path, not CWD
TEMPLATES_DIR = Path(__file__).parent / "templates" / "outreach"


def available_segments() -> list[str]:
    """Derive available segments from template files on disk."""
    return [p.stem for p in TEMPLATES_DIR.glob("*.md")]


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
        "keywords": [
            # Bucket 1: Musicians/Composers
            "composer showcase", "film composer", "music producer San Diego", "songwriter workshop",
            # Bucket 2: Authors/Writers
            "author talk San Diego", "screenwriting workshop", "writers conference",
            # Bucket 3: Indie Filmmakers/Producers
            "indie film San Diego", "documentary screening", "film festival San Diego", "video production",
            # Bucket 4: Creative entrepreneurs/educators
            "creative entrepreneurship", "creative business workshop", "art director",
            # Bucket 5: Filmmaker tools expansion (2026-05-08)
            "screenwriting San Diego", "cinematography San Diego", "filmmaking San Diego",
            "documentary San Diego", "short film San Diego", "video editing San Diego",
        ],
        "country": "united-states",
        "city": "San Diego",
        "max_pages": 2,
    },
    "facebook": {
        "enabled": True,
        "actor": "apify/facebook-groups-scraper",
        "groups": [
            # Existing
            "https://www.facebook.com/groups/1488967914699762/",
            "https://www.facebook.com/groups/mexicanfilmmakerssd/",
            # Filmmaker - core
            "https://www.facebook.com/groups/sandiegofilmnetwork/",
            "https://www.facebook.com/groups/filmconsortiumsd/",
            "https://www.facebook.com/groups/SanDiego48HFP/",
            "https://www.facebook.com/groups/244108549311595/",
            # Filmmaker - crew / cast
            "https://www.facebook.com/groups/audiovisualproductioncrewsd/",
            "https://www.facebook.com/groups/castncrew/",
            "https://www.facebook.com/groups/sandiegoactors/",
            # Filmmaker - institutional
            "https://www.facebook.com/groups/SDSUTheatreTVAndFilm/",
            # Writing / Music (workshop audience tiers)
            "https://www.facebook.com/groups/SanDiegoWriters/",
            "https://www.facebook.com/groups/BBSanDiegoCA/",
            # Media / adjacent creative
            "https://www.facebook.com/groups/sdmediapros/",
            "https://www.facebook.com/groups/257380068144396/",
            "https://www.facebook.com/groups/SanDiegoPhotographers/",
        ],
    },
    "instagram": {
        "enabled": True,
        "actor": "apify/instagram-hashtag-scraper",
        "hashtags": [
            # Bucket 1: Musicians/Composers
            "SanDiegoMusician", "SanDiegoComposer", "SDSongwriter", "SanDiegoMusicProducer",
            # Bucket 2: Authors/Writers
            "SanDiegoAuthor", "SanDiegoWriter", "SDScreenwriter",
            # Bucket 3: Indie Filmmakers
            "SanDiegoFilmmaker", "SDFilmmaker", "SanDiegoFilm", "IndieFilmSD", "SanDiegoVideoProduction",
            # Bucket 4: Creative entrepreneurs
            "SDCreatives", "SanDiegoCreative", "SanDiegoArtist",
            # Bucket 5: Filmmaker tools expansion (2026-05-08)
            "SanDiegoFilmCommunity", "SanDiegoCinematography", "SanDiegoDocumentary", "SDIndieFilm",
        ],
        "max_profiles": 400,
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
