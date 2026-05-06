"""CLI entry point for venue scraping.

Usage:
    python scrape.py urls.txt --output results/
    python scrape.py --url "https://example-venue.com"
    python scrape.py --search "recording studios San Diego"
    python scrape.py --search-film --csv
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from crawl4ai import AsyncWebCrawler

from crawler import (
    discover_subpages_from_links,
    get_browser_config,
    get_dispatcher,
    get_run_config,
)
from models import merge_venue_results, validate_extraction


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


async def main(urls: list[str], output_dir: Path, contacts_only: bool = False, csv_export: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    errors: list[dict] = []

    # Apply 15-URL cap
    if len(urls) > 15:
        print(f"  Found {len(urls)} URLs, capping at 15.")
        urls = urls[:15]

    async with AsyncWebCrawler(config=get_browser_config()) as crawler:
        for start_url in urls:
            # SINGLE-PASS: crawl homepage with networkidle (for link discovery)
            homepage_results = await crawler.arun_many(
                urls=[start_url], config=get_run_config(wait_until="networkidle"), dispatcher=get_dispatcher()
            )
            homepage_result = homepage_results[0]

            page_venues = []

            # Extract from homepage
            if homepage_result.success and homepage_result.extracted_content:
                venue = validate_extraction(homepage_result.extracted_content, homepage_result.url)
                if venue:
                    page_venues.append(venue)
                    print(f"    OK: {homepage_result.url}")

            # Discover subpages from homepage links
            internal_links = homepage_result.links.get("internal", []) if homepage_result.success else []
            subpages = discover_subpages_from_links(start_url, internal_links)

            # Crawl subpages
            if subpages:
                subpage_results = await crawler.arun_many(
                    urls=subpages, config=get_run_config(), dispatcher=get_dispatcher()
                )
                for result in subpage_results:
                    if result.success and result.extracted_content:
                        venue = validate_extraction(result.extracted_content, result.url)
                        if venue:
                            page_venues.append(venue)
                            print(f"    OK: {result.url}")

            # Merge pages into one result
            if page_venues:
                merged = merge_venue_results(page_venues)
                if merged:
                    merged.source_url = start_url
                    results.append(merged.model_dump(mode="json"))
                    print(f"  -> {merged.name}: email={merged.email}, phone={merged.phone}")
            else:
                errors.append({"url": start_url, "error": "No data from any page"})
                print(f"  FAIL: {start_url}", file=sys.stderr)

    # Write results
    if contacts_only:
        output_file = output_dir / "contacts.jsonl"
        with open(output_file, "w") as f:
            for r in results:
                contact = {
                    "source_url": r["source_url"],
                    "name": r.get("name"),
                    "email": r.get("email"),
                    "phone": r.get("phone"),
                    "social_links": r.get("social_links", []),
                }
                f.write(json.dumps(contact) + "\n")
    else:
        output_file = output_dir / "results.json"
        output_file.write_text(json.dumps(results, indent=2, default=str))

    # CSV export (new)
    if csv_export and results:
        from export import export_outreach_csv
        export_outreach_csv(results, output_dir / "outreach.csv")

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
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("urls_file", nargs="?", type=Path, help="File with one URL per line")
    source.add_argument("--url", type=str, help="Scrape a single URL")
    source.add_argument("--search", type=str, metavar="QUERY",
        help="Search Google for venue URLs (uses SerpAPI)")
    source.add_argument("--search-film", action="store_true",
        help="Run predefined film-venue searches for San Diego")
    parser.add_argument("--output", type=Path, default=Path("results"), help="Output directory")
    parser.add_argument("--contacts-only", action="store_true", help="Output only contact info as JSONL")
    parser.add_argument("--csv", action="store_true",
        help="Also export results as outreach CSV")
    args = parser.parse_args()

    # SERPAPI_API_KEY only required if using search
    if (args.search or args.search_film) and not os.environ.get("SERPAPI_API_KEY"):
        print("Error: SERPAPI_API_KEY not set. Required for --search/--search-film.", file=sys.stderr)
        sys.exit(1)

    # Resolve URL list from source
    if args.url:
        if not is_valid_url(args.url):
            parser.error(f"Invalid URL (must start with http:// or https://): {args.url}")
        url_list = [args.url]
    elif args.search:
        from discover import search_venues
        url_list = search_venues(args.search)
    elif args.search_film:
        from discover import search_film_venues
        url_list = search_film_venues()
    elif args.urls_file:
        url_list = load_urls(args.urls_file)

    # Defense-in-depth: validate all URLs regardless of source
    url_list = [u for u in url_list if is_valid_url(u)]

    if not url_list:
        print("No URLs found.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(main(url_list, args.output, contacts_only=args.contacts_only, csv_export=args.csv))
