import os
import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

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
SOURCES_OVERRIDES_PATH = Path(__file__).parent / "sources.overrides.json"


def available_segments() -> list[str]:
    """Derive available segments from template files on disk."""
    return [p.stem for p in TEMPLATES_DIR.glob("*.md")]


# Source configs -- edit to add/remove groups and keywords
BASE_SOURCES = {
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

_ALLOWED_SOURCE_LIST_FIELDS = {
    "eventbrite": {"keywords"},
    "facebook": {"groups"},
    "instagram": {"hashtags"},
    "linkedin": {"queries"},
    "meetup": {"groups"},
}
_SOURCE_LIST_LIMITS = {
    ("eventbrite", "keywords"): 25,
}


def _load_source_overrides() -> dict:
    if not SOURCES_OVERRIDES_PATH.exists():
        return {}
    return json.loads(SOURCES_OVERRIDES_PATH.read_text())


def _merge_sources(base_sources: dict, overrides: dict) -> dict:
    merged = deepcopy(base_sources)
    for source_name, source_overrides in overrides.items():
        if source_name not in merged or not isinstance(source_overrides, dict):
            continue
        for key, value in source_overrides.items():
            if key.endswith("_add"):
                field_name = key[:-4]
                if field_name not in merged[source_name] or not isinstance(value, list):
                    continue
                existing = list(merged[source_name][field_name])
                for item in value:
                    if item not in existing:
                        existing.append(item)
                merged[source_name][field_name] = existing
            else:
                merged[source_name][key] = value
    return merged


def get_sources() -> dict:
    return _merge_sources(BASE_SOURCES, _load_source_overrides())


SOURCES = get_sources()


def get_sources_overrides_path() -> Path:
    return SOURCES_OVERRIDES_PATH


def save_source_overrides(overrides: dict) -> None:
    SOURCES_OVERRIDES_PATH.write_text(json.dumps(overrides, indent=2, sort_keys=True) + "\n")


def _normalize_source_list_item(source_name: str, field_name: str, item: str) -> str:
    normalized = item.strip()
    if field_name == "hashtags":
        normalized = normalized.lstrip("#")
    if field_name == "groups":
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Invalid group URL: {item}")
        if source_name == "facebook" and "facebook.com" not in parsed.netloc:
            raise ValueError(f"Facebook groups must use facebook.com URLs: {item}")
        if source_name == "meetup" and "meetup.com" not in parsed.netloc:
            raise ValueError(f"Meetup groups must use meetup.com URLs: {item}")
    return normalized


def add_source_list_items(source_name: str, field_name: str, items: list[str]) -> list[str]:
    if source_name not in _ALLOWED_SOURCE_LIST_FIELDS:
        raise ValueError(f"Unsupported source: {source_name}")
    if field_name not in _ALLOWED_SOURCE_LIST_FIELDS[source_name]:
        raise ValueError(f"Unsupported field for {source_name}: {field_name}")

    cleaned = []
    for item in items:
        normalized = _normalize_source_list_item(source_name, field_name, item)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    if not cleaned:
        return []

    overrides = _load_source_overrides()
    source_overrides = overrides.setdefault(source_name, {})
    key = f"{field_name}_add"
    existing = list(source_overrides.get(key, []))
    current_values = list(get_sources()[source_name][field_name])
    limit = _SOURCE_LIST_LIMITS.get((source_name, field_name))
    if limit is not None:
        projected_total = len(current_values)
        for item in cleaned:
            if item not in current_values:
                projected_total += 1
                current_values.append(item)
        if projected_total > limit:
            raise ValueError(
                f"{source_name}.{field_name} cannot exceed {limit} items "
                f"(would become {projected_total})."
            )
    added = []
    for item in cleaned:
        if item not in existing:
            existing.append(item)
            added.append(item)
    source_overrides[key] = existing
    save_source_overrides(overrides)
    return added
