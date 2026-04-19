#!/usr/bin/env python3
"""CLI dispatcher for the lead scraper. Subcommands: scrape, export, serve."""

import argparse
import csv
import re
import sys
from pathlib import Path

# Ensure lead-scraper/ is on the import path when run from any directory
sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, DB_PATH
from config import SOURCES, get_apify_token
from ingest import ingest_leads
from models import query_leads
from utils import sanitize_csv_cell


def cmd_scrape(args):
    """Run enabled scrapers and ingest results."""
    # Validate token early
    try:
        get_apify_token()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    results = []
    for source_name, source_config in SOURCES.items():
        if not source_config.get("enabled"):
            continue

        print(f"Scraping {source_name}...", end=" ", flush=True)
        try:
            from scrapers import eventbrite, meetup, facebook, linkedin, instagram
            scraper_map = {"eventbrite": eventbrite, "meetup": meetup, "facebook": facebook, "linkedin": linkedin, "instagram": instagram}
            scraper = scraper_map.get(source_name)
            if scraper is None:
                print(f"Unknown source: {source_name}")
                continue
            leads = scraper.scrape(args.location, source_config)
            print(f"found {len(leads)} leads.", end=" ", flush=True)

            inserted, skipped, invalid = ingest_leads(leads)
            print(f"{inserted} new, {skipped} duplicates, {invalid} rejected.")
            results.append({"source": source_name, "inserted": inserted, "skipped": skipped, "error": None})

        except Exception as e:
            # Mask tokens that might appear in the error message
            error_msg = re.sub(r'[A-Za-z0-9_-]{32,}', '[REDACTED]', str(e)[:500])
            print(f"FAILED: {error_msg}")
            results.append({"source": source_name, "inserted": 0, "skipped": 0, "error": error_msg})

    # Summary
    total_inserted = sum(r["inserted"] for r in results)
    succeeded = sum(1 for r in results if r["error"] is None)
    total = len(results)
    print(f"\nScrape complete. {total_inserted} new leads from {succeeded}/{total} sources.")

    if succeeded == 0 and total > 0:
        print("No leads scraped. Check your tokens and network.", file=sys.stderr)
        sys.exit(1)

    # Auto-enrich new leads
    if total_inserted > 0:
        from enrich import enrich_leads
        print()
        enrich_leads()


def cmd_enrich(args):
    """Enrich existing leads: bio parsing, website fetching, then deep crawl."""
    from enrich import enrich_from_bios, enrich_leads, enrich_websites_deep
    enrich_from_bios()
    print()
    enrich_leads()
    print()
    enrich_websites_deep()


def cmd_export(args):
    """Export all leads to a CSV file."""
    leads, _ = query_leads(limit=100000)
    if not leads:
        print("No leads to export.")
        return

    output_path = args.output
    fieldnames = ["id", "name", "bio", "location", "email", "phone", "website", "social_handles", "profile_bio", "profile_url", "activity", "source", "scraped_at", "enriched_at"]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            row = {k: sanitize_csv_cell(lead[k]) for k in fieldnames}
            writer.writerow(row)

    print(f"Exported {len(leads)} leads to {output_path}")


def cmd_serve(args):
    """Start the Flask web UI."""
    from app import create_app
    import os

    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=debug)


def main():
    parser = argparse.ArgumentParser(description="Lead Scraper CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scrape
    sp_scrape = subparsers.add_parser("scrape", help="Run scrapers and ingest leads")
    sp_scrape.add_argument("--location", required=True, help='Target location, e.g. "San Diego, CA"')
    sp_scrape.set_defaults(func=cmd_scrape)

    # export
    sp_export = subparsers.add_parser("export", help="Export leads to CSV")
    sp_export.add_argument("--output", required=True, help="Output CSV file path")
    sp_export.set_defaults(func=cmd_export)

    # enrich
    sp_enrich = subparsers.add_parser("enrich", help="Enrich leads with contact info")
    sp_enrich.set_defaults(func=cmd_enrich)

    # serve
    sp_serve = subparsers.add_parser("serve", help="Start Flask web UI")
    sp_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()

    # Always bootstrap the database
    init_db()

    args.func(args)


if __name__ == "__main__":
    main()
