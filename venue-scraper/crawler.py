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
        wait_until="domcontentloaded",
        delay_before_return_html=2.0,
        excluded_tags=["nav", "footer", "aside", "header"],
        remove_overlay_elements=True,
    )


def get_dispatcher() -> SemaphoreDispatcher:
    return SemaphoreDispatcher(max_session_permit=CONCURRENCY_LIMIT)


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
