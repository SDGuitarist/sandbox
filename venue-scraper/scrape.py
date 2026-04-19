"""CLI entry point for venue scraping.

Usage:
    python scrape.py urls.txt --output results/
    python scrape.py --url "https://example-venue.com"
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from crawl4ai import AsyncWebCrawler

from crawler import discover_subpages, get_browser_config, get_dispatcher, get_run_config
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


async def main(urls: list[str], output_dir: Path, contacts_only: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    errors: list[dict] = []

    async with AsyncWebCrawler(config=get_browser_config()) as crawler:
        for start_url in urls:
            # Discover subpages for each start URL
            all_pages = discover_subpages(start_url)
            print(f"  Crawling {start_url} + {len(all_pages) - 1} subpages...")

            crawl_results = await crawler.arun_many(
                urls=all_pages,
                config=get_run_config(),
                dispatcher=get_dispatcher(),
            )

            # Collect valid extractions from all pages
            page_venues = []
            for result in crawl_results:
                if not result.success or not result.extracted_content:
                    if result.url == start_url:
                        errors.append({
                            "url": result.url,
                            "error": result.error_message or "No content extracted",
                        })
                        print(f"    FAIL: {result.url} -- {result.error_message}", file=sys.stderr)
                    # Subpage failures are expected (404s), don't log as errors
                    continue

                venue = validate_extraction(result.extracted_content, result.url)
                if venue is not None:
                    page_venues.append(venue)
                    print(f"    OK: {result.url}")

            # Merge all pages into one result
            if page_venues:
                merged = merge_venue_results(page_venues)
                if merged:
                    merged.source_url = start_url
                    results.append(merged.model_dump(mode="json"))
                    print(f"  -> {merged.name}: email={merged.email}, phone={merged.phone}")
            else:
                errors.append({"url": start_url, "error": "No valid extractions from any page"})
                print(f"  FAIL: {start_url} -- no data from any page", file=sys.stderr)

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
    parser.add_argument("--output", type=Path, default=Path("results"), help="Output directory")
    parser.add_argument("--contacts-only", action="store_true", help="Output only contact info as JSONL")
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

    asyncio.run(main(url_list, args.output, contacts_only=args.contacts_only))
