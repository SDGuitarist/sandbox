#!/usr/bin/env python3
"""CLI dispatcher for the lead scraper. Subcommands: scrape, export, serve."""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure lead-scraper/ is on the import path when run from any directory
sys.path.insert(0, str(Path(__file__).parent))

from db import (
    DB_JOB_LOCKFILE,
    DB_PATH,
    MigrationRequired,
    MigrationSafetyError,
    create_backup,
    db_job_lock,
    get_db,
    init_db,
)
from config import (
    add_source_list_items,
    get_apify_token,
    get_sources,
    get_sources_overrides_path,
)
from ingest import ingest_leads
from models import query_leads
from utils import sanitize_csv_cell


DEFAULT_EVENTBRITE_SOURCE = "eventbrite"
NL_AUDIT_LOG_PATH = Path(__file__).parent / "nl_audit.jsonl"


def cmd_scrape(args):
    """Run enabled scrapers and ingest results."""
    # Validate token early
    try:
        get_apify_token()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    results = []
    for source_name, source_config in get_sources().items():
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


def _print_db_status(db_path=DB_PATH) -> None:
    """Print a compact production DB summary."""
    with get_db(db_path) as conn:
        lead_count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        campaign_count = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
        queue_count = conn.execute("SELECT COUNT(*) FROM outreach_queue").fetchone()[0]
        approved_count = conn.execute(
            "SELECT COUNT(*) FROM outreach_queue WHERE status = 'approved'"
        ).fetchone()[0]
        draft_count = conn.execute(
            "SELECT COUNT(*) FROM outreach_queue WHERE status = 'draft'"
        ).fetchone()[0]
        review_count = conn.execute(
            "SELECT COUNT(*) FROM outreach_queue WHERE status = 'needs_review'"
        ).fetchone()[0]

    print("Database status:")
    print(f"  Leads:         {lead_count}")
    print(f"  Campaigns:     {campaign_count}")
    print(f"  Queue rows:    {queue_count}")
    print(f"  Drafts:        {draft_count}")
    print(f"  Approved:      {approved_count}")
    print(f"  Needs review:  {review_count}")


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


def cmd_migrate(args):
    """Run explicit schema migrations."""
    init_db(DB_PATH, allow_destructive=args.allow_destructive_production)
    print("Database schema is current.")


def cmd_workflow(args):
    """Run a safe high-level workflow for natural-language usage."""
    from campaign import assign_leads, generate_messages
    from quality_gate import run_gate

    action = args.action

    if action == "status":
        _print_db_status()
        return

    if action == "daily":
        cmd_scrape(args)
        assign_leads(args.campaign_id, args.min_hook_quality)
        generate_messages(args.campaign_id, limit=args.generate_limit)
        if not args.skip_gate:
            run_gate(args.campaign_id, limit=args.gate_limit, force=args.force_gate)
        _print_db_status()
        return

    if action == "scrape-only":
        cmd_scrape(args)
        _print_db_status()
        return

    if action == "outreach-prep":
        if getattr(args, "run_enrich", False):
            cmd_enrich(args)
        assign_leads(args.campaign_id, args.min_hook_quality)
        generate_messages(args.campaign_id, limit=args.generate_limit)
        if not args.skip_gate:
            run_gate(args.campaign_id, limit=args.gate_limit, force=args.force_gate)
        _print_db_status()
        return


def _join_nl_text(text_parts) -> str:
    if isinstance(text_parts, str):
        return text_parts.strip()
    return " ".join(text_parts).strip()


def _extract_campaign_id(text: str) -> int | None:
    match = re.search(r"\bcampaign\s+(\d+)\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"\bfor\s+(\d+)\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _default_location() -> str:
    eventbrite = get_sources().get(DEFAULT_EVENTBRITE_SOURCE, {})
    city = eventbrite.get("city")
    if city:
        return f"{city}, CA" if "," not in city else city
    return "San Diego, CA"


def _extract_location(text: str) -> str | None:
    match = re.search(
        r"\b(?:in|for|around)\s+([A-Za-z .'-]+,\s*[A-Za-z]{2})\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return None


def _extract_list_after_keyword(text: str, anchor: str) -> list[str]:
    pattern = rf"{anchor}\s+(.+?)(?:[.?!]|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return []
    raw = match.group(1).strip()
    raw = re.sub(r"^(like|such as)\s+", "", raw, flags=re.IGNORECASE)
    raw = raw.replace(" and ", ", ")
    items = []
    for piece in raw.split(","):
        cleaned = piece.strip().strip("\"'")
        if cleaned:
            items.append(cleaned)
    deduped = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _extract_list_after_anchor_to_end(text: str, anchor: str) -> list[str]:
    pattern = rf"{anchor}\s+(.+)$"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return []
    raw = match.group(1).strip()
    raw = raw.replace(" and ", ", ")
    items = []
    for piece in raw.split(","):
        cleaned = piece.strip().strip("\"'")
        if cleaned:
            items.append(cleaned)
    return items


def _infer_mutation_source(normalized_text: str, field_name: str) -> str:
    if field_name == "hashtags":
        return "instagram"
    if field_name == "queries":
        return "linkedin"
    if field_name == "keywords":
        return "eventbrite"
    if "facebook" in normalized_text:
        return "facebook"
    if "meetup" in normalized_text:
        return "meetup"
    return "facebook"


def _append_mutation(plan: dict, normalized_text: str, field_name: str, items: list[str]) -> None:
    if not items:
        return
    cleaned_items = []
    for item in items:
        cleaned = item.strip()
        if field_name == "hashtags":
            cleaned = cleaned.lstrip("#")
        if cleaned and cleaned not in cleaned_items:
            cleaned_items.append(cleaned)
    if not cleaned_items:
        return
    source_name = _infer_mutation_source(normalized_text, field_name)
    plan["mutations"].append(
        {
            "source_name": source_name,
            "field_name": field_name,
            "items": cleaned_items,
        }
    )


def _parse_nl_mutations(prompt: str, normalized: str, plan: dict) -> None:
    if "keyword" in normalized and any(word in normalized for word in ("add", "include", "use", "with")):
        for anchor in ("keywords", "keyword"):
            keywords = _extract_list_after_keyword(prompt, anchor)
            if keywords:
                _append_mutation(plan, normalized, "keywords", keywords)
                break

    if "hashtag" in normalized and any(word in normalized for word in ("add", "include", "use", "with")):
        for anchor in ("hashtags", "hashtag"):
            hashtags = _extract_list_after_keyword(prompt, anchor)
            if hashtags:
                _append_mutation(plan, normalized, "hashtags", hashtags)
                break

    if "group" in normalized and any(word in normalized for word in ("add", "include", "use", "with")):
        for anchor in ("groups", "group"):
            groups = _extract_list_after_anchor_to_end(prompt, anchor)
            if groups:
                _append_mutation(plan, normalized, "groups", groups)
                break

    if "query" in normalized and any(word in normalized for word in ("add", "include", "use", "with")):
        for anchor in ("queries", "query"):
            queries = _extract_list_after_keyword(prompt, anchor)
            if queries:
                _append_mutation(plan, normalized, "queries", queries)
                break


def _parse_nl_request(text: str) -> dict:
    prompt = text.strip()
    if not prompt:
        raise ValueError("Natural-language request is empty.")

    normalized = re.sub(r"\s+", " ", prompt.lower())
    plan = {
        "raw_text": prompt,
        "action": None,
        "location": None,
        "campaign_id": None,
        "mutations": [],
        "needs_lock": False,
        "needs_backup": False,
    }

    if any(phrase in normalized for phrase in ("status", "how many leads", "database summary", "db summary")):
        plan["action"] = "status"
        return plan

    _parse_nl_mutations(prompt, normalized, plan)
    if any(word in normalized for word in ("keyword", "hashtag", "group", "query")) and not plan["mutations"]:
        raise ValueError("I could not safely extract the items to add.")

    campaign_id = _extract_campaign_id(prompt)
    location = _extract_location(prompt) or _default_location()
    plan["campaign_id"] = campaign_id
    plan["location"] = location

    if any(phrase in normalized for phrase in ("daily workflow", "full workflow", "run the pipeline")):
        if campaign_id is None:
            raise ValueError("Campaign ID is required for the daily workflow.")
        plan["action"] = "daily"
    elif any(phrase in normalized for phrase in ("outreach prep", "prepare outreach", "prep outreach")):
        if campaign_id is None:
            raise ValueError("Campaign ID is required for outreach prep.")
        plan["action"] = "outreach-prep"
    elif "scrape" in normalized or "search for leads" in normalized:
        plan["action"] = "scrape-only"

    if plan["action"] is None and plan["mutations"]:
        plan["action"] = "config-only"

    if plan["action"] is None:
        raise ValueError(
            "Unsupported request. I can safely translate status checks, scrape requests, "
            "campaign outreach prep, daily workflow runs, and source-list additions "
            "(Eventbrite keywords, Instagram hashtags, Facebook/Meetup groups, LinkedIn queries)."
        )

    plan["needs_lock"] = plan["action"] != "status"
    plan["needs_backup"] = plan["action"] != "status"
    return plan


def _nl_plan_from_args(args) -> dict | None:
    if getattr(args, "command", None) != "nl":
        return None
    cached = getattr(args, "_nl_plan", None)
    if cached is not None:
        return cached
    try:
        plan = _parse_nl_request(_join_nl_text(args.text))
    except ValueError:
        return None
    args._nl_plan = plan
    return plan


def _confirm_nl_mutations(plan: dict, *, assume_yes: bool = False) -> bool:
    if assume_yes or not plan["mutations"]:
        return True

    print("Planned config changes:")
    for mutation in plan["mutations"]:
        print(
            f"  Add to {mutation['source_name']}.{mutation['field_name']}: "
            f"{', '.join(mutation['items'])}"
        )
    response = input("Apply these config changes? [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def _print_nl_plan(plan: dict) -> None:
    print(f"Translated request: {plan['action']}")
    if plan["location"]:
        print(f"  Location: {plan['location']}")
    if plan["campaign_id"] is not None:
        print(f"  Campaign: {plan['campaign_id']}")
    for mutation in plan["mutations"]:
        print(
            f"  Add to {mutation['source_name']}.{mutation['field_name']}: "
            f"{', '.join(mutation['items'])}"
        )


def _append_nl_audit_log(plan: dict, *, status: str) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "action": plan["action"],
        "location": plan["location"],
        "campaign_id": plan["campaign_id"],
        "mutations": plan["mutations"],
        "raw_text": plan["raw_text"],
    }
    with NL_AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def _apply_nl_mutations(plan: dict) -> None:
    for mutation in plan["mutations"]:
        added = add_source_list_items(
            mutation["source_name"],
            mutation["field_name"],
            mutation["items"],
        )
        if added:
            print(
                f"Added {len(added)} item(s) to "
                f"{mutation['source_name']}.{mutation['field_name']}: {', '.join(added)}"
            )
        else:
            print(
                f"No new items were added to "
                f"{mutation['source_name']}.{mutation['field_name']}."
            )
    if plan["mutations"]:
        print(f"Overrides saved to {get_sources_overrides_path()}")


def cmd_nl(args):
    """Translate restricted natural language into safe workflow actions."""
    try:
        plan = _parse_nl_request(_join_nl_text(args.text))
    except ValueError as e:
        print(f"Could not safely translate request: {e}", file=sys.stderr)
        sys.exit(2)

    args._nl_plan = plan

    _print_nl_plan(plan)

    if getattr(args, "preview", False):
        _append_nl_audit_log(plan, status="preview")
        return

    if plan["mutations"]:
        if not _confirm_nl_mutations(plan, assume_yes=getattr(args, "yes", False)):
            _append_nl_audit_log(plan, status="cancelled")
            print("Cancelled.")
            return
        _apply_nl_mutations(plan)

    if plan["action"] == "status":
        _append_nl_audit_log(plan, status="executed")
        _print_db_status()
        return

    if plan["action"] == "config-only":
        _append_nl_audit_log(plan, status="executed")
        return

    workflow_args = argparse.Namespace(
        action=plan["action"],
        location=plan["location"],
        campaign_id=plan["campaign_id"],
        min_hook_quality=3,
        generate_limit=50,
        gate_limit=0,
        skip_gate=False,
        force_gate=False,
        run_enrich=False,
        step="all",
        limit=50,
        refresh=False,
        days=30,
    )
    _append_nl_audit_log(plan, status="executed")
    cmd_workflow(workflow_args)


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
        show_queue(args.campaign_id, status_filter=getattr(args, "status", None))
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
    elif action == "send":
        from browser_sender import run_send
        run_send(args.campaign_id, args.limit)
    elif action == "gate":
        from quality_gate import run_gate
        run_gate(args.campaign_id, limit=getattr(args, "limit", 0) or 0,
                 force=getattr(args, "force", False))
    elif action == "requeue":
        from campaign import requeue_lead
        requeue_lead(args.campaign_id, args.lead)
    elif action == "force-approve":
        from campaign import force_approve
        force_approve(args.campaign_id, args.lead)
    elif action == "force-skip":
        from campaign import force_skip
        force_skip(args.campaign_id, args.lead,
                   reason=getattr(args, "reason", "") or "")


def cmd_serve(args):
    """Start the Flask web UI."""
    from app import create_app
    import os

    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=debug)


def _command_needs_db_lock(args) -> bool:
    if args.command == "nl":
        plan = _nl_plan_from_args(args)
        return bool(plan and plan["needs_lock"])
    if args.command in {"scrape", "enrich", "import", "dedup", "migrate"}:
        return True
    if args.command == "workflow" and args.action != "status":
        return True
    if args.command == "campaign" and args.action not in {"queue", "status"}:
        return True
    if args.command == "account":
        return True
    if args.command == "leads" and args.action == "unhold":
        return True
    return False


def _command_needs_backup(args) -> bool:
    if args.command == "nl":
        plan = _nl_plan_from_args(args)
        return bool(plan and plan["needs_backup"])
    if args.command in {"scrape", "enrich", "import", "dedup", "migrate"}:
        return True
    if args.command == "workflow" and args.action != "status":
        return True
    return False


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

    sp_queue = campaign_sub.add_parser("queue", help="Show queue messages for review")
    sp_queue.add_argument("campaign_id", type=int)
    sp_queue.add_argument("--status",
                          choices=["draft", "approved", "needs_review", "skipped", "sent"],
                          help="Filter by status (default: all non-sent)")

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

    sp_send = campaign_sub.add_parser("send", help="Send approved messages via browser")
    sp_send.add_argument("campaign_id", type=int)
    sp_send.add_argument("--limit", type=int, required=True,
                         help="Max messages to send (required for safety)")

    sp_gate = campaign_sub.add_parser("gate", help="Run quality gate on draft messages")
    sp_gate.add_argument("campaign_id", type=int)
    sp_gate.add_argument("--limit", type=int, default=0,
                         help="Max drafts to check (default: all)")
    sp_gate.add_argument("--force", action="store_true",
                         help="Re-gate leads that already have gate_checked_at")

    sp_requeue = campaign_sub.add_parser("requeue",
                                         help="Move skipped/needs_review back to draft")
    sp_requeue.add_argument("campaign_id", type=int)
    sp_requeue.add_argument("--lead", type=int, required=True)

    sp_fapprove = campaign_sub.add_parser("force-approve",
                                          help="Approve a needs_review lead after review")
    sp_fapprove.add_argument("campaign_id", type=int)
    sp_fapprove.add_argument("--lead", type=int, required=True)

    sp_fskip = campaign_sub.add_parser("force-skip",
                                       help="Reject a needs_review lead after review")
    sp_fskip.add_argument("campaign_id", type=int)
    sp_fskip.add_argument("--lead", type=int, required=True)
    sp_fskip.add_argument("--reason", default="", help="Skip reason")

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

    # migrate
    sp_migrate = subparsers.add_parser(
        "migrate",
        help="Run explicit schema migrations",
    )
    sp_migrate.add_argument(
        "--allow-destructive-production",
        action="store_true",
        help="Allow the production outreach_queue table recreation migration",
    )
    sp_migrate.set_defaults(func=cmd_migrate)

    # workflow
    sp_workflow = subparsers.add_parser(
        "workflow",
        help="Run a safe high-level production workflow",
    )
    workflow_sub = sp_workflow.add_subparsers(dest="action", required=True)

    sp_daily = workflow_sub.add_parser(
        "daily",
        help="Scrape, assign, generate, and optionally gate in one safe run",
    )
    sp_daily.add_argument("--location", required=True, help='Target location, e.g. "San Diego, CA"')
    sp_daily.add_argument("--campaign-id", type=int, required=True)
    sp_daily.add_argument("--min-hook-quality", type=int, default=3)
    sp_daily.add_argument("--generate-limit", type=int, default=50)
    sp_daily.add_argument("--gate-limit", type=int, default=0)
    sp_daily.add_argument("--skip-gate", action="store_true")
    sp_daily.add_argument("--force-gate", action="store_true")

    sp_scrape_only = workflow_sub.add_parser(
        "scrape-only",
        help="Run only the scrape step under the global DB lock",
    )
    sp_scrape_only.add_argument("--location", required=True, help='Target location, e.g. "San Diego, CA"')

    sp_outreach = workflow_sub.add_parser(
        "outreach-prep",
        help="Assign, generate, and optionally gate for a campaign",
    )
    sp_outreach.add_argument("--campaign-id", type=int, required=True)
    sp_outreach.add_argument("--min-hook-quality", type=int, default=3)
    sp_outreach.add_argument("--generate-limit", type=int, default=50)
    sp_outreach.add_argument("--gate-limit", type=int, default=0)
    sp_outreach.add_argument("--skip-gate", action="store_true")
    sp_outreach.add_argument("--force-gate", action="store_true")
    sp_outreach.add_argument("--run-enrich", action="store_true")
    sp_outreach.add_argument(
        "--step",
        choices=["bio", "website", "crawl", "hunter", "segment", "hook", "verify", "screen", "consistency", "all"],
        default="all",
    )
    sp_outreach.add_argument("--limit", type=int, default=50)
    sp_outreach.add_argument("--refresh", action="store_true")
    sp_outreach.add_argument("--days", type=int, default=30)

    workflow_sub.add_parser("status", help="Show a compact DB status summary")
    sp_workflow.set_defaults(func=cmd_workflow)

    # nl
    sp_nl = subparsers.add_parser(
        "nl",
        help="Translate a restricted natural-language request into a safe workflow action",
    )
    sp_nl.add_argument("text", nargs="+", help="Natural-language request")
    sp_nl.add_argument(
        "--yes",
        action="store_true",
        help="Apply allowed config changes without confirmation",
    )
    sp_nl.add_argument(
        "--preview",
        action="store_true",
        help="Show the translated action without applying changes or running workflows",
    )
    sp_nl.set_defaults(func=cmd_nl)

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

    try:
        if args.command == "migrate":
            with db_job_lock():
                create_backup()
                args.func(args)
            return

        # Always bootstrap non-destructive schema changes before normal commands.
        init_db()
    except (MigrationRequired, MigrationSafetyError) as e:
        print(f"Database safety check failed: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        if _command_needs_db_lock(args):
            with db_job_lock():
                if _command_needs_backup(args):
                    create_backup()
                args.func(args)
        else:
            args.func(args)
    except MigrationSafetyError as e:
        print(f"Database safety check failed: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
