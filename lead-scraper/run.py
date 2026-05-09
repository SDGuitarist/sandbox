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
    """Enrich existing leads: bio parsing, website fetching, crawl (Apify + venue scraper fallback), Hunter.io, segment classification, hook research."""
    from enrich import (
        enrich_from_bios, enrich_leads, enrich_crawl,
        enrich_with_hunter, enrich_segment, enrich_hook,
    )

    # --refresh: clear stale enrichment data before re-running
    if getattr(args, "refresh", False):
        days = getattr(args, "days", 30)
        _refresh_stale_leads(args.step, days)

    steps = {
        "bio": enrich_from_bios,
        "website": enrich_leads,
        "crawl": enrich_crawl,
        "hunter": enrich_with_hunter,
        "segment": enrich_segment,
        "hook": enrich_hook,
    }
    limit = getattr(args, "limit", 0) or 0
    selected = args.step
    if selected == "verify":
        from enrich import verify_hooks
        verify_hooks()
    elif selected == "screen":
        from enrich import screen_leads
        screen_leads()
    elif selected == "consistency":
        from enrich import verify_hook_consistency
        verify_hook_consistency(limit=limit)
    elif selected == "all":
        for name, func in steps.items():
            func()
            print()
        # Auto-verify, screen, and consistency check after enrichment
        from enrich import verify_hooks, screen_leads, verify_hook_consistency
        print()
        verify_hooks()
        print()
        screen_leads()
        print()
        verify_hook_consistency()
    elif selected in ("segment", "hook"):
        steps[selected](limit=limit)
    else:
        steps[selected]()


def _refresh_stale_leads(step: str, days: int):
    """Clear enrichment data older than N days so leads get re-processed."""
    from datetime import datetime, timedelta
    from db import get_db

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        if step in ("hook", "all"):
            cursor = conn.execute(
                "UPDATE leads SET hook_text = NULL, hook_source_url = NULL, hook_quality = NULL "
                "WHERE enriched_at < ? AND hook_text IS NOT NULL",
                (cutoff,),
            )
            print(f"Refreshed {cursor.rowcount} stale hooks (older than {days} days).")

        if step in ("segment", "all"):
            cursor = conn.execute(
                "UPDATE leads SET segment = NULL, segment_confidence = NULL "
                "WHERE enriched_at < ? AND segment IS NOT NULL",
                (cutoff,),
            )
            print(f"Refreshed {cursor.rowcount} stale segments (older than {days} days).")

        if step in ("website", "crawl", "hunter", "all"):
            cursor = conn.execute(
                "UPDATE leads SET enriched_at = NULL "
                "WHERE enriched_at < ?",
                (cutoff,),
            )
            print(f"Refreshed {cursor.rowcount} stale contact enrichments (older than {days} days).")


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


def cmd_leads(args) -> None:
    """Dispatch leads subcommands."""
    if args.action == "held":
        _cmd_leads_held()
    elif args.action == "unhold":
        _cmd_leads_unhold(args)


def _cmd_leads_held() -> None:
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


def _cmd_leads_unhold(args) -> None:
    """Force-approve a held lead for campaign assignment."""
    from models import unhold_lead, query_held_leads
    from db import get_db

    lead_id = args.lead_id

    # Look up the lead for confirmation output
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, segment FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
    if not row:
        print(f"Lead {lead_id} not found.", file=sys.stderr)
        sys.exit(1)

    # Check current hold reasons (for user feedback)
    held = query_held_leads()
    reasons = [h["hold_reason"] for h in held if h["id"] == lead_id]

    if not unhold_lead(lead_id):
        print(f"Lead {lead_id} not found.", file=sys.stderr)
        sys.exit(1)

    reason_str = ", ".join(reasons) if reasons else "none (already eligible)"
    print(f"Approved lead {lead_id} ({row['name']}). Was held for: {reason_str}")

    # Warn if lead still can't be assigned due to missing/unsupported segment
    from config import available_segments as _available_segments
    segments = _available_segments()
    if not row["segment"]:
        print("WARNING: Lead has no segment -- will not be assigned to campaigns until enriched.")
    elif segments and row["segment"] not in segments:
        print(f"WARNING: Segment '{row['segment']}' has no template -- lead will not be assigned.")


def cmd_import(args):
    """Import leads from a CSV file."""
    from ingest import import_from_csv

    inserted, skipped, rejected = import_from_csv(args.csv, args.source)
    print(f"Import complete. {inserted} new, {skipped} duplicates, {rejected} rejected.")


def cmd_dedup(args):
    """Find and merge duplicate leads."""
    from models import find_duplicates, merge_leads

    groups = find_duplicates()
    if not groups:
        print("No duplicates found.")
        return

    total_dupes = sum(len(g) - 1 for g in groups)
    print(f"Found {len(groups)} duplicate groups ({total_dupes} extra leads):\n")
    for i, group in enumerate(groups, 1):
        names = [f"{l['name']} (id={l['id']}, source={l['source']})" for l in group]
        print(f"  Group {i}: {', '.join(names)}")

    if not args.apply:
        print(f"\nDry run. Use --apply to merge these groups.")
        return

    merged = 0
    for group in groups:
        keeper_id = merge_leads(group)
        names = [l["name"] for l in group]
        print(f"  Merged {len(group)} leads -> kept id {keeper_id} ({names[0]})")
        merged += 1
    print(f"\nMerged {merged} groups, removed {total_dupes} duplicate leads.")


def cmd_cleanup(args):
    """Remove old database backups, keeping the most recent N."""
    keep = args.keep
    db_dir = Path(__file__).parent
    backups = sorted(db_dir.glob("leads.backup-*.db"), key=lambda p: p.name)

    if len(backups) <= keep:
        print(f"Only {len(backups)} backups found, keeping all (threshold: {keep}).")
        return

    to_delete = backups[:-keep]
    print(f"Found {len(backups)} backups. Removing {len(to_delete)}, keeping {keep}.\n")

    freed = 0
    for backup in to_delete:
        size = backup.stat().st_size
        # Also remove -shm and -wal companions
        for suffix in ("", "-shm", "-wal"):
            companion = Path(str(backup) + suffix)
            if companion.exists():
                if not args.dry_run:
                    companion.unlink()
                freed += companion.stat().st_size if companion.exists() or suffix == "" else 0
        print(f"  {'[dry run] ' if args.dry_run else ''}Removed {backup.name} ({size // 1024}KB)")

    if args.dry_run:
        print(f"\nDry run. Use without --dry-run to delete.")
    else:
        print(f"\nDeleted {len(to_delete)} backups, freed ~{freed // 1024 // 1024}MB.")


def cmd_schedule(args):
    """Print crontab setup for automatic scraping."""
    script = Path(__file__).resolve()
    project_dir = script.parent
    # Prefer the project venv python over system python
    venv_python = project_dir / "venv" / "bin" / "python"
    python = str(venv_python) if venv_python.exists() else str(Path(sys.executable).resolve())
    location = args.location

    cron_line = (
        f'0 8 * * * cd {project_dir} && '
        f'{python} {script} scrape --location "{location}" '
        f'>> /tmp/lead-scraper.log 2>&1'
    )

    print("To scrape automatically every day at 8am, add this to your crontab:\n")
    print(f"  {cron_line}")
    print()
    print("Commands:")
    print("  crontab -e    # open crontab editor")
    print("  crontab -l    # view current crontab")


def cmd_account(args):
    """Dispatch account subcommands."""
    from account import (
        add_account, list_accounts, confirm_risk, set_cooldown,
        disable_account, enable_account,
    )

    action = args.action
    if action == "add":
        add_account(args.name, platform=args.platform, daily_cap=args.daily_cap)
    elif action == "list":
        list_accounts()
    elif action == "login":
        _account_login(args.name)
    elif action == "confirm-risk":
        # Look up account ID by name
        _with_account_by_name(args.name, confirm_risk)
    elif action == "cooldown":
        _with_account_by_name(args.name, lambda aid: set_cooldown(aid, args.hours))
    elif action == "disable":
        _with_account_by_name(args.name, disable_account)
    elif action == "enable":
        _with_account_by_name(args.name, enable_account)


def _with_account_by_name(name, func):
    """Look up account ID by name, then call func(account_id)."""
    from db import get_db
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM sender_accounts WHERE name = ?", (name,)
        ).fetchone()
    if not row:
        print(f"Account '{name}' not found.", file=sys.stderr)
        sys.exit(1)
    func(row['id'])


def _account_login(name):
    """Open a headed browser for manual login. Session saved to profile_dir."""
    from db import get_db
    with get_db() as conn:
        row = conn.execute(
            "SELECT profile_dir FROM sender_accounts WHERE name = ?", (name,)
        ).fetchone()
    if not row:
        print(f"Account '{name}' not found.", file=sys.stderr)
        sys.exit(1)

    profile_dir = row['profile_dir']
    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright
    print(f"Opening browser for '{name}'...")
    print(f"Profile: {profile_dir}")
    print("Log in to Facebook/Instagram manually.")
    print("Press Enter here when done to save session and close.\n")

    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=False,
        viewport={"width": 1280, "height": 800},
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://www.facebook.com")

    input("Press Enter to save session and close browser...")
    context.close()
    pw.stop()
    print(f"Session saved for '{name}'.")


def cmd_campaign(args):
    """Dispatch campaign subcommands."""
    from campaign import (
        create_campaign, assign_leads, generate_messages,
        show_queue, approve_message, skip_message, mark_sent, show_status,
        mark_replied, mark_booked, mark_declined, mark_no_response,
        approve_all_messages, skip_all_messages,
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
        limit = getattr(args, "limit", 0) or 0
        generate_messages(args.campaign_id, limit=limit)
    elif action == "queue":
        show_queue(args.campaign_id)
    elif action == "approve":
        approve_message(args.campaign_id, args.lead)
    elif action == "skip":
        skip_message(args.campaign_id, args.lead)
    elif action == "sent":
        mark_sent(args.campaign_id, args.lead)
    elif action == "replied":
        mark_replied(args.campaign_id, args.lead)
    elif action == "booked":
        mark_booked(args.campaign_id, args.lead)
    elif action == "declined":
        mark_declined(args.campaign_id, args.lead)
    elif action == "no-response":
        mark_no_response(args.campaign_id, args.lead)
    elif action == "approve-all":
        approve_all_messages(args.campaign_id)
    elif action == "skip-all":
        skip_all_messages(args.campaign_id, getattr(args, "except_leads", None))
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
        choices=["bio", "website", "crawl", "hunter", "segment", "hook", "verify", "screen", "consistency", "all"],
        default="all",
        help="Run a specific enrichment step (default: all)",
    )
    sp_enrich.add_argument(
        "--limit", type=int, default=50,
        help="Max leads to process for segment/hook steps (default: 50)",
    )
    sp_enrich.add_argument(
        "--refresh", action="store_true",
        help="Re-enrich leads older than --days (clears stale data first)",
    )
    sp_enrich.add_argument(
        "--days", type=int, default=30,
        help="Age threshold for --refresh in days (default: 30)",
    )
    sp_enrich.set_defaults(func=cmd_enrich)

    # leads
    sp_leads = subparsers.add_parser("leads", help="Lead queries")
    leads_sub = sp_leads.add_subparsers(dest="action", required=True)
    leads_sub.add_parser("held", help="Show leads held from auto-generation")
    sp_unhold = leads_sub.add_parser("unhold", help="Force-approve a held lead for campaigns")
    sp_unhold.add_argument("lead_id", type=int, help="Lead ID to approve")
    sp_leads.set_defaults(func=cmd_leads)

    # account
    sp_account = subparsers.add_parser("account", help="Sender account management")
    account_sub = sp_account.add_subparsers(dest="action", required=True)

    sp_acc_add = account_sub.add_parser("add", help="Add a sender account")
    sp_acc_add.add_argument("name", help="Account name (used as profile dir name)")
    sp_acc_add.add_argument("--platform", choices=["facebook", "instagram", "both"],
                            default="both", help="Platform (default: both)")
    sp_acc_add.add_argument("--daily-cap", type=int, default=30,
                            help="Max sends per day (default: 30)")

    account_sub.add_parser("list", help="List all sender accounts")

    sp_acc_login = account_sub.add_parser("login", help="Open browser for manual login")
    sp_acc_login.add_argument("name", help="Account name")

    sp_acc_risk = account_sub.add_parser("confirm-risk",
                                         help="Acknowledge Meta ban risk (required before sends)")
    sp_acc_risk.add_argument("name", help="Account name")

    sp_acc_cool = account_sub.add_parser("cooldown", help="Set cooldown period (restricted accounts)")
    sp_acc_cool.add_argument("name", help="Account name")
    sp_acc_cool.add_argument("--hours", type=int, required=True, help="Cooldown hours")

    sp_acc_dis = account_sub.add_parser("disable", help="Disable an account")
    sp_acc_dis.add_argument("name", help="Account name")

    sp_acc_en = account_sub.add_parser("enable", help="Re-enable a disabled account")
    sp_acc_en.add_argument("name", help="Account name")

    sp_account.set_defaults(func=cmd_account)

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
    sp_gen.add_argument(
        "--limit", type=int, default=50,
        help="Max leads to generate messages for (default: 50)",
    )

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

    sp_replied = campaign_sub.add_parser("replied", help="Mark a sent message as replied")
    sp_replied.add_argument("campaign_id", type=int)
    sp_replied.add_argument("--lead", type=int, required=True)

    sp_booked = campaign_sub.add_parser("booked", help="Mark as booked (converted)")
    sp_booked.add_argument("campaign_id", type=int)
    sp_booked.add_argument("--lead", type=int, required=True)

    sp_declined = campaign_sub.add_parser("declined", help="Mark as declined")
    sp_declined.add_argument("campaign_id", type=int)
    sp_declined.add_argument("--lead", type=int, required=True)

    sp_noresp = campaign_sub.add_parser("no-response", help="Mark as no response")
    sp_noresp.add_argument("campaign_id", type=int)
    sp_noresp.add_argument("--lead", type=int, required=True)

    sp_approve_all = campaign_sub.add_parser("approve-all", help="Approve all draft messages")
    sp_approve_all.add_argument("campaign_id", type=int)

    sp_skip_all = campaign_sub.add_parser("skip-all", help="Skip all draft messages")
    sp_skip_all.add_argument("campaign_id", type=int)
    sp_skip_all.add_argument("--except", type=int, nargs="+", dest="except_leads",
                             help="Lead IDs to keep as draft")

    sp_status = campaign_sub.add_parser("status", help="Show campaign status")
    sp_status.add_argument("campaign_id", type=int)

    sp_campaign.set_defaults(func=cmd_campaign)

    # import
    sp_import = subparsers.add_parser("import", help="Import leads from CSV")
    sp_import.add_argument("--csv", required=True, help="Path to CSV file")
    sp_import.add_argument("--source", default="csv_import", help="Source label (default: csv_import)")
    sp_import.set_defaults(func=cmd_import)

    # cleanup
    sp_cleanup = subparsers.add_parser("cleanup", help="Remove old database backups")
    sp_cleanup.add_argument("--keep", type=int, default=5,
                            help="Number of recent backups to keep (default: 5)")
    sp_cleanup.add_argument("--dry-run", action="store_true",
                            help="Show what would be deleted without deleting")
    sp_cleanup.set_defaults(func=cmd_cleanup)

    # dedup
    sp_dedup = subparsers.add_parser("dedup", help="Find and merge duplicate leads")
    sp_dedup.add_argument("--apply", action="store_true",
                          help="Actually merge (default: dry run)")
    sp_dedup.set_defaults(func=cmd_dedup)

    # schedule
    sp_schedule = subparsers.add_parser("schedule", help="Print crontab setup for auto-scraping")
    sp_schedule.add_argument("--location", required=True,
                             help='Target location, e.g. "San Diego, CA"')
    sp_schedule.set_defaults(func=cmd_schedule)

    # serve
    sp_serve = subparsers.add_parser("serve", help="Start Flask web UI")
    sp_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()

    # Always bootstrap the database
    init_db()

    args.func(args)


if __name__ == "__main__":
    main()
