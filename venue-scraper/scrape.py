"""CLI entry point for venue scraping.

Usage:
    python scrape.py urls.txt --output results/
    python scrape.py --url "https://example-venue.com" --source gigsalad --proxy
    python scrape.py urls.txt --db
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from crawl4ai import AsyncWebCrawler

from crawler import get_browser_config, get_dispatcher, get_proxy_from_env, get_run_config
from models import VenueSource, validate_extraction


def is_valid_url(url: str) -> bool:
    """Check that a URL starts with http:// or https://."""
    return url.startswith(("http://", "https://"))


def load_urls(filepath: Path) -> list[str]:
    """Load URLs from file. One per line. Blank lines and # comments ignored."""
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    urls: list[str] = []
    for line in filepath.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if not is_valid_url(line):
                print(f"  Skipping invalid URL: {line}", file=sys.stderr)
                continue
            urls.append(line)

    # Deduplicate, preserve order
    return list(dict.fromkeys(urls))


async def main(
    urls: list[str],
    output_dir: Path,
    *,
    source: VenueSource = VenueSource.WEBSITE,
    use_proxy: bool = False,
    use_db: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    errors: list[dict] = []

    proxy_config = get_proxy_from_env() if use_proxy else None
    if use_proxy and proxy_config is None:
        print("Warning: --proxy set but IPROYAL_PROXY_SERVER not configured", file=sys.stderr)

    async with AsyncWebCrawler(config=get_browser_config(proxy_config)) as crawler:
        crawl_results = await crawler.arun_many(
            urls=urls,
            config=get_run_config(),
            dispatcher=get_dispatcher(),
        )

        for result in crawl_results:
            # Hard failure: crawl itself failed (DNS, timeout, etc.)
            if not result.success:
                errors.append({
                    "url": result.url,
                    "error": result.error_message or "Crawl failed",
                })
                print(f"  FAIL: {result.url} -- {result.error_message}", file=sys.stderr)
                continue

            # Try markdown extraction (may be falsy/empty -- that's OK, fallback handles it)
            venue = validate_extraction(result.extracted_content, result.url)

            # HTML fallback: retry if markdown extraction returned nothing usable
            if venue is None:
                print(f"  RETRY (HTML): {result.url}", file=sys.stderr)
                fallback = await crawler.arun(
                    url=result.url,
                    config=get_run_config(html_mode=True),
                )
                if fallback.success and fallback.extracted_content:
                    venue = validate_extraction(fallback.extracted_content, result.url)

            if venue is None:
                errors.append({"url": result.url, "error": "Extraction failed (markdown + HTML)"})
                print(f"  FAIL: {result.url} -- extraction failed", file=sys.stderr)
                continue

            # Tag the source
            venue.source = source
            results.append(venue.model_dump(mode="json"))
            print(f"  OK: {venue.name} ({result.url})")

    # Persist to SQLite if requested
    if use_db:
        from db import get_db, init_db
        from ingest import insert_venue

        init_db()
        inserted = 0
        with get_db() as conn:
            for row in results:
                from models import VenueData

                v = VenueData(**row)
                status = insert_venue(conn, v)
                if status == "inserted":
                    inserted += 1
        print(f"\nStored {inserted} new venues in venue_scraper.db ({len(results) - inserted} duplicates skipped).")

    # Write JSON results
    output_file = output_dir / "results.json"
    output_file.write_text(json.dumps(results, indent=2, default=str))

    # Summary
    total = len(urls)
    succeeded = len(results)
    failed = len(errors)
    print(f"\nScraped {succeeded}/{total} venues. {failed} failed.")

    if errors:
        for err in errors:
            print(f"  - {err['url']}: {err['error']}", file=sys.stderr)


if __name__ == "__main__":
    import argparse

    # Validate API key at startup
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set. Export it or add to .env", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Scrape venue websites for business intelligence")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("urls_file", nargs="?", type=Path, help="File with one URL per line")
    source_group.add_argument("--url", type=str, help="Scrape a single URL")
    parser.add_argument("--output", type=Path, default=Path("results"), help="Output directory")
    parser.add_argument(
        "--source", type=VenueSource, default=VenueSource.WEBSITE,
        choices=list(VenueSource), help="Source tag",
    )
    parser.add_argument("--proxy", action="store_true", help="Use IPRoyal residential proxy")
    parser.add_argument("--db", action="store_true", help="Persist results to SQLite")
    args = parser.parse_args()

    if args.url:
        if not is_valid_url(args.url):
            parser.error(f"Invalid URL (must start with http:// or https://): {args.url}")
        url_list = [args.url]
    elif args.urls_file:
        url_list = load_urls(args.urls_file)
    else:
        parser.error("Provide urls_file or --url")

    if not url_list:
        print("No URLs found.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(main(url_list, args.output, source=args.source, use_proxy=args.proxy, use_db=args.db))
