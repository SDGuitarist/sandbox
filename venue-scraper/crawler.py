"""Crawl4AI wrapper for venue scraping.

Configures browser, extraction strategy, and dispatcher.
All functions return typed config objects for use with AsyncWebCrawler.
"""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMConfig,
    SemaphoreDispatcher,
)
from crawl4ai.extraction_strategy import LLMExtractionStrategy

from models import EXTRACTION_PROMPT, VenueData

CONCURRENCY_LIMIT = 3  # conservative -- each tab uses ~100-200MB RAM

# Common subpaths where contact info lives.
# Trimmed to 2 high-value paths to reduce LLM API cost (~70% savings).
# /contact and /about cover ~90% of contact info pages.
CONTACT_SUBPATHS = [
    "/contact",
    "/about",
]


def get_strategy() -> LLMExtractionStrategy:
    return LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="anthropic/claude-sonnet-4-20250514",
            api_token="env:ANTHROPIC_API_KEY",
        ),
        schema=VenueData.model_json_schema(),
        extraction_type="schema",
        instruction=EXTRACTION_PROMPT,
        input_format="markdown",
        chunk_token_threshold=2000,
        overlap_rate=0.1,
    )


def get_browser_config() -> BrowserConfig:
    return BrowserConfig(headless=True, enable_stealth=True)


def get_run_config() -> CrawlerRunConfig:
    return CrawlerRunConfig(
        extraction_strategy=get_strategy(),
        cache_mode=CacheMode.BYPASS,  # prevent silent LLM skip on cache hits (#1455)
        page_timeout=15000,
        wait_until="networkidle",  # waits for JS nav menus to render links
        delay_before_return_html=2.0,
        scan_full_page=True,  # catches lazy-loaded nav links
        excluded_tags=["nav", "footer", "aside", "header"],
        remove_overlay_elements=True,
    )


def get_dispatcher() -> SemaphoreDispatcher:
    return SemaphoreDispatcher(max_session_permit=CONCURRENCY_LIMIT)


# Keywords for link-text matching (case-insensitive substring)
CONTACT_KEYWORDS = ["contact", "get in touch", "inquir"]
ABOUT_KEYWORDS = ["about", "team", "connect"]


def _is_same_origin(base_url: str, candidate_url: str) -> bool:
    """SSRF protection: ensure candidate URL is same-origin as base.

    Rejects: different hostnames, non-HTTP schemes, protocol-relative URLs.
    """
    base_parsed = urlparse(base_url)
    cand_parsed = urlparse(candidate_url)

    if cand_parsed.scheme not in ("http", "https"):
        return False
    if cand_parsed.netloc != base_parsed.netloc:
        return False
    return True


def discover_subpages_from_links(
    base_url: str,
    internal_links: list[dict],
) -> list[str]:
    """Find contact/about pages from homepage links.

    Searches internal_links for anchor text matching CONTACT_KEYWORDS
    and ABOUT_KEYWORDS. Returns up to 2 discovered URLs.

    FALLBACK BEHAVIOR (additive, cap-aware): After link-based discovery,
    appends hardcoded paths that were NOT already found via links, up to
    the 2-subpage cap. If links already found 2 pages, hardcoded paths
    are skipped. This prevents missing /contact pages not linked from
    the homepage while respecting cost controls.

    Args:
        base_url: The homepage URL (for urljoin on relative hrefs).
        internal_links: List of {"href": str, "text": str} from CrawlResult.links["internal"].

    Returns:
        List of subpage URLs to crawl (max 2, does NOT include base_url).
    """
    found: list[str] = []
    found_contact = False
    found_about = False

    for link in internal_links:
        text = (link.get("text") or "").lower().strip()
        href = link.get("href", "")
        if not text or not href:
            continue

        resolved = urljoin(base_url, href)

        # SSRF protection: same-origin only
        if not _is_same_origin(base_url, resolved):
            continue

        # Check contact keywords
        if not found_contact and any(kw in text for kw in CONTACT_KEYWORDS):
            found.append(resolved)
            found_contact = True

        # Check about keywords
        if not found_about and any(kw in text for kw in ABOUT_KEYWORDS):
            if resolved not in found:
                found.append(resolved)
            found_about = True

        if found_contact and found_about:
            break

    # ADDITIVE FALLBACK: append hardcoded paths not already discovered
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    for path in CONTACT_SUBPATHS:
        candidate = urljoin(origin, path)
        if candidate not in found and len(found) < 2:
            found.append(candidate)

    return found[:2]  # Hard cap at 2 subpages


def discover_subpages(base_url: str) -> list[str]:
    """Generate candidate subpage URLs for contact info discovery.

    Returns the base URL plus common contact/about paths appended to it.
    Deduplicates and preserves order (base URL first).
    """
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    urls = [base_url]
    for path in CONTACT_SUBPATHS:
        candidate = urljoin(origin, path)
        if candidate not in urls:
            urls.append(candidate)
    return urls
