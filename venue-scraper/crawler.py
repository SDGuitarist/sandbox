"""Crawl4AI wrapper for venue scraping.

Configures browser, extraction strategy, and dispatcher.
All functions return typed config objects for use with AsyncWebCrawler.
"""
from __future__ import annotations

import os
from typing import TypedDict

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


class ProxyConfig(TypedDict):
    server: str
    username: str
    password: str


def _normalize_proxy_server(server: str) -> str:
    """Ensure proxy server is in the scheme://host:port form Playwright expects."""
    return server if "://" in server else f"http://{server}"


def get_proxy_from_env() -> ProxyConfig | None:
    """Read IPRoyal proxy config from env vars. Returns None if not configured."""
    server = os.environ.get("IPROYAL_PROXY_SERVER")
    if not server:
        return None
    return ProxyConfig(
        server=_normalize_proxy_server(server),
        username=os.environ.get("IPROYAL_PROXY_USER", ""),
        password=os.environ.get("IPROYAL_PROXY_PASS", ""),
    )


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


def get_browser_config(proxy_config: ProxyConfig | None = None) -> BrowserConfig:
    if proxy_config:
        # Crawl4AI's managed-browser/CDP path falls back to a CLI --proxy-server flag,
        # which cannot handle authenticated residential proxies reliably. Force the
        # native persistent-context path so Playwright receives server/user/password
        # as structured proxy settings instead of inline credentials.
        return BrowserConfig(
            headless=True,
            enable_stealth=True,
            browser_type="chromium",
            use_persistent_context=True,
            proxy_config={
                "server": _normalize_proxy_server(proxy_config["server"]),
                "username": proxy_config["username"],
                "password": proxy_config["password"],
            },
        )
    return BrowserConfig(headless=True, enable_stealth=True)


def get_run_config(html_mode: bool = False) -> CrawlerRunConfig:
    """Build run config. Set html_mode=True for sites that fail markdown extraction."""
    strategy = get_strategy()
    if html_mode:
        strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="anthropic/claude-sonnet-4-20250514",
                api_token="env:ANTHROPIC_API_KEY",
            ),
            schema=VenueData.model_json_schema(),
            extraction_type="schema",
            instruction=EXTRACTION_PROMPT,
            input_format="fit_markdown",
            chunk_token_threshold=4000,
            overlap_rate=0.1,
        )
    return CrawlerRunConfig(
        extraction_strategy=strategy,
        cache_mode=CacheMode.BYPASS,
        page_timeout=15000,
        wait_until="domcontentloaded",
        delay_before_return_html=2.0,
        excluded_tags=["nav", "footer", "aside", "header"],
        remove_overlay_elements=True,
    )


def get_dispatcher() -> SemaphoreDispatcher:
    return SemaphoreDispatcher(max_session_permit=CONCURRENCY_LIMIT)
