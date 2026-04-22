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
    """Enrich existing leads: bio parsing, website fetching, deep crawl, venue scraper, Hunter.io."""
    from enrich import (
        enrich_from_bios, enrich_leads, enrich_websites_deep,
        enrich_with_venue_scraper, enrich_with_hunter,
    )
    steps = {
        "bio": enrich_from_bios,
        "website": enrich_leads,
        "deep": enrich_websites_deep,
        "venue": enrich_with_venue_scraper,
        "hunter": enrich_with_hunter,
    }
    selected = args.step
    if selected == "all":
        for name, func in steps.items():
            func()
            print()
    else:
        steps[selected]()


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


def cmd_leads(args):
    """Show held leads with reasons."""
    from models import query_held_leads

    held = query_held_leads()
    if not held:
        print("No held leads.")
        return

    print(f"\n{'Name':<30} {'Segment':<15} {'Hook Q':<8} {'Reason'}")
    print("-" * 75)
    for lead in held:
        hook_q = lead["hook_quality"] if lead["hook_quality"] is not None else "-"
        segment = lead["segment"] or "-"
        print(f"{lead['name'][:29]:<30} {segment:<15} {str(hook_q):<8} {lead['hold_reason']}")
    print(f"\nTotal held: {len(held)}")


def cmd_import(args):
    """Import leads from a CSV file."""
    from ingest import import_from_csv

    inserted, skipped, rejected = import_from_csv(args.csv, args.source)
    print(f"Import complete. {inserted} new, {skipped} duplicates, {rejected} rejected.")


def cmd_campaign(args):
    """Dispatch campaign subcommands."""
    from campaign import (
        create_campaign, assign_leads, generate_messages,
        show_queue, approve_message, skip_message, mark_sent, show_status,
    )

    action = args.action
    if action == "create":
        template_vars = {}
        for v in (args.var or []):
            key, _, value = v.partition("=")
            template_vars[key.strip()] = value.strip()
        cid = create_campaign(
            args.name, args.segment, template_vars or None, args.target_date,
        )
        print(f"Campaign created: ID {cid}")
    elif action == "assign":
        assign_leads(args.campaign_id, args.min_hook_quality)
    elif action == "generate":
        generate_messages(args.campaign_id)
    elif action == "queue":
        show_queue(args.campaign_id)
    elif action == "approve":
        approve_message(args.campaign_id, args.lead)
    elif action == "skip":
        skip_message(args.campaign_id, args.lead)
    elif action == "sent":
        mark_sent(args.campaign_id, args.lead)
    elif action == "status":
        show_status(args.campaign_id)


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
    sp_enrich.add_argument(
        "--step",
        choices=["bio", "website", "deep", "venue", "hunter", "all"],
        default="all",
        help="Run a specific enrichment step (default: all)",
    )
    sp_enrich.set_defaults(func=cmd_enrich)

    # leads
    sp_leads = subparsers.add_parser("leads", help="Lead queries")
    leads_sub = sp_leads.add_subparsers(dest="action", required=True)
    leads_sub.add_parser("held", help="Show leads held from auto-generation")
    sp_leads.set_defaults(func=cmd_leads)

    # campaign
    sp_campaign = subparsers.add_parser("campaign", help="Campaign management")
    campaign_sub = sp_campaign.add_subparsers(dest="action", required=True)

    sp_create = campaign_sub.add_parser("create", help="Create a new campaign")
    sp_create.add_argument("name", help="Campaign name")
    sp_create.add_argument("--segment", help="Comma-separated segment filter")
    sp_create.add_argument("--var", action="append", help="Template var: key=value")
    sp_create.add_argument("--target-date", help="Campaign target date")

    sp_assign = campaign_sub.add_parser("assign", help="Assign eligible leads")
    sp_assign.add_argument("campaign_id", type=int)
    sp_assign.add_argument("--min-hook-quality", type=int, default=3)

    sp_gen = campaign_sub.add_parser("generate", help="Generate draft messages")
    sp_gen.add_argument("campaign_id", type=int)

    sp_queue = campaign_sub.add_parser("queue", help="Show draft messages for review")
    sp_queue.add_argument("campaign_id", type=int)

    sp_approve = campaign_sub.add_parser("approve", help="Approve a draft message")
    sp_approve.add_argument("campaign_id", type=int)
    sp_approve.add_argument("--lead", type=int, required=True)

    sp_skip = campaign_sub.add_parser("skip", help="Skip a draft message")
    sp_skip.add_argument("campaign_id", type=int)
    sp_skip.add_argument("--lead", type=int, required=True)

    sp_sent = campaign_sub.add_parser("sent", help="Mark an approved message as sent")
    sp_sent.add_argument("campaign_id", type=int)
    sp_sent.add_argument("--lead", type=int, required=True)

    sp_status = campaign_sub.add_parser("status", help="Show campaign status")
    sp_status.add_argument("campaign_id", type=int)

    sp_campaign.set_defaults(func=cmd_campaign)

    # import
    sp_import = subparsers.add_parser("import", help="Import leads from CSV")
    sp_import.add_argument("--csv", required=True, help="Path to CSV file")
    sp_import.add_argument("--source", default="csv_import", help="Source label (default: csv_import)")
    sp_import.set_defaults(func=cmd_import)

    # serve
    sp_serve = subparsers.add_parser("serve", help="Start Flask web UI")
    sp_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()

    # Always bootstrap the database
    init_db()

    args.func(args)


if __name__ == "__main__":
    main()
