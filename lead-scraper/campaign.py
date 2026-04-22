"""Campaign management: create, assign, generate, queue, approve, skip, sent, status.

This module owns all writes to campaigns, campaign_leads, and outreach_queue tables.
Single-writer rule: no other module writes to these tables.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path

from db import get_db, DB_PATH

# Template discovery uses repo-relative path, not CWD
TEMPLATES_DIR = Path(__file__).parent / "templates" / "outreach"


def _available_segments() -> list[str]:
    """Derive available segments from template files on disk."""
    return [p.stem for p in TEMPLATES_DIR.glob("*.md")]


def _read_template(segment: str) -> tuple[str, str]:
    """Read a template file. Returns (frontmatter_raw, body)."""
    path = TEMPLATES_DIR / f"{segment}.md"
    if not path.exists():
        raise FileNotFoundError(f"No template for segment: {segment}")
    text = path.read_text()
    # Split YAML frontmatter from body
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[1].strip(), parts[2].strip()
    return "", text.strip()


def _fill_template(template_body: str, variables: dict) -> str:
    """Replace {{var}} placeholders with values from the campaign config.

    Raises ValueError if any {{var}} in the template has no matching value.
    """
    # Find all {{var}} placeholders
    placeholders = set(re.findall(r"\{\{(\w+)\}\}", template_body))
    missing = placeholders - set(variables.keys())
    if missing:
        raise ValueError(
            f"Missing template variables: {', '.join(sorted(missing))}. "
            f"Provide via --var {list(missing)[0]}=value"
        )
    result = template_body
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------

def create_campaign(name: str, segment_filter: str | None,
                    template_vars: dict | None, target_date: str | None,
                    db_path: Path = DB_PATH) -> int:
    """Create a campaign. Returns the campaign ID."""
    vars_json = json.dumps(template_vars) if template_vars else None
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO campaigns (name, target_date, segment_filter, template_vars_json) "
            "VALUES (?, ?, ?, ?)",
            (name, target_date, segment_filter, vars_json),
        )
        campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return campaign_id


def assign_leads(campaign_id: int, min_hook_quality: int = 3,
                 db_path: Path = DB_PATH) -> int:
    """Assign eligible leads to a campaign. Returns count assigned.

    Eligible: segment in available templates, hook_quality between 1 and
    min_hook_quality, segment_confidence >= 0.7, matches campaign segment filter.
    """
    available = _available_segments()
    if not available:
        print("No template files found in templates/outreach/.")
        return 0

    # Read campaign's segment filter
    with get_db(db_path) as conn:
        campaign = conn.execute(
            "SELECT segment_filter FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if not campaign:
            print(f"Campaign {campaign_id} not found.")
            return 0

        # Build segment filter
        if campaign["segment_filter"]:
            requested = [s.strip() for s in campaign["segment_filter"].split(",")]
            # Intersect with available templates
            segments = [s for s in requested if s in available]
        else:
            segments = available

        if not segments:
            print("No matching segments with template files.")
            return 0

        placeholders = ",".join("?" for _ in segments)
        cursor = conn.execute(
            f"""INSERT INTO campaign_leads (campaign_id, lead_id)
                SELECT ?, id FROM leads
                WHERE segment IN ({placeholders})
                  AND hook_quality > 0
                  AND hook_quality <= ?
                  AND segment_confidence >= 0.7
                ON CONFLICT(campaign_id, lead_id) DO NOTHING""",
            [campaign_id] + segments + [min_hook_quality],
        )
        count = cursor.rowcount

    print(f"Assigned {count} leads to campaign {campaign_id}.")
    return count


# ---------------------------------------------------------------------------
# Message generation
# ---------------------------------------------------------------------------

def _generate_opener(client, name: str, hook_text: str) -> str:
    """Generate a 1-2 sentence opener from a hook using Claude Haiku."""
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            system="You write casual, specific Facebook DM openers for Alex, a musician and AI consultant in San Diego. Write 1-2 sentences that reference the person's specific activity. Sound like you actually follow their work. No vendor pitch tone. Use their first name.",
            messages=[{
                "role": "user",
                "content": f"Write a DM opener for {name} based on this hook: {hook_text}",
            }],
        )
        return response.content[0].text.strip()
    except Exception as e:
        # Fallback: simple opener from hook
        first_name = name.split()[0] if name else "Hey"
        return f"{first_name}, {hook_text}"


def generate_messages(campaign_id: int, db_path: Path = DB_PATH) -> int:
    """Generate draft messages for all assigned leads without queue entries.

    Returns count of messages generated.
    """
    import anthropic

    with get_db(db_path) as conn:
        # Get campaign config
        campaign = conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if not campaign:
            print(f"Campaign {campaign_id} not found.")
            return 0

        template_vars = json.loads(campaign["template_vars_json"]) if campaign["template_vars_json"] else {}

        # Get assigned leads that don't have queue entries yet
        leads = conn.execute(
            """SELECT l.id, l.name, l.hook_text, l.hook_source_url, l.segment
               FROM campaign_leads cl
               JOIN leads l ON cl.lead_id = l.id
               LEFT JOIN outreach_queue oq
                 ON oq.lead_id = cl.lead_id AND oq.campaign_id = cl.campaign_id
               WHERE cl.campaign_id = ? AND oq.id IS NULL""",
            (campaign_id,),
        ).fetchall()

    if not leads:
        print("No leads to generate messages for.")
        return 0

    # Validate templates can be filled before spending API credits
    segments_needed = {row["segment"] for row in leads}
    for seg in segments_needed:
        _, body = _read_template(seg)
        _fill_template(body, template_vars)  # raises ValueError if vars missing

    client = anthropic.Anthropic(max_retries=3)
    count = 0

    print(f"Generating messages for {len(leads)} leads...")
    for i, lead in enumerate(leads, 1):
        name = lead["name"][:40]
        print(f"  {i}/{len(leads)} {name}...", end=" ", flush=True)

        _, template_body = _read_template(lead["segment"])
        template_text = _fill_template(template_body, template_vars)

        if lead["hook_text"]:
            opener_text = _generate_opener(client, lead["name"], lead["hook_text"])
        else:
            opener_text = ""

        full_message = f"{opener_text}\n\n{template_text}".strip()

        with get_db(db_path) as conn:
            conn.execute(
                """INSERT INTO outreach_queue
                   (lead_id, campaign_id, opener_text, template_text, full_message)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(lead_id, campaign_id) DO NOTHING""",
                (lead["id"], campaign_id, opener_text, template_text, full_message),
            )

        count += 1
        print("done")
        time.sleep(0.1)

    print(f"\nGenerated {count} messages.")
    return count


# ---------------------------------------------------------------------------
# Queue review
# ---------------------------------------------------------------------------

def show_queue(campaign_id: int, db_path: Path = DB_PATH) -> None:
    """Print all draft messages with hook_source_url for verification."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT oq.id, l.name, l.hook_text, l.hook_source_url, oq.full_message
               FROM outreach_queue oq
               JOIN leads l ON oq.lead_id = l.id
               WHERE oq.campaign_id = ? AND oq.status = 'draft'
               ORDER BY oq.id""",
            (campaign_id,),
        ).fetchall()

    if not rows:
        print("No draft messages in queue.")
        return

    print(f"\n{'='*60}")
    print(f"QUEUE: {len(rows)} draft messages (campaign {campaign_id})")
    print(f"{'='*60}")

    for row in rows:
        print(f"\n--- {row['name']} ---")
        if row["hook_text"]:
            print(f"Hook: {row['hook_text']}")
        if row["hook_source_url"]:
            print(f"Verify: {row['hook_source_url']}")
        else:
            print("Verify: NO SOURCE URL -- verify hook manually")
        print(f"\nMessage:\n{row['full_message']}")
        print()


# ---------------------------------------------------------------------------
# Approval / Skip / Sent (atomic claim pattern)
# ---------------------------------------------------------------------------

def approve_message(campaign_id: int, lead_id: int, db_path: Path = DB_PATH) -> bool:
    """Approve a draft message. Atomic claim: only transitions draft -> approved."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE outreach_queue SET status = 'approved', approved_at = ? "
            "WHERE campaign_id = ? AND lead_id = ? AND status = 'draft'",
            (now, campaign_id, lead_id),
        )
        if cursor.rowcount == 0:
            print("Already approved or not found.")
            return False
    print(f"Approved message for lead {lead_id}.")
    return True


def skip_message(campaign_id: int, lead_id: int, db_path: Path = DB_PATH) -> bool:
    """Skip a draft message."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE outreach_queue SET status = 'skipped' "
            "WHERE campaign_id = ? AND lead_id = ? AND status = 'draft'",
            (campaign_id, lead_id),
        )
        if cursor.rowcount == 0:
            print("Already skipped or not found.")
            return False
    print(f"Skipped message for lead {lead_id}.")
    return True


def mark_sent(campaign_id: int, lead_id: int, db_path: Path = DB_PATH) -> bool:
    """Mark an approved message as sent. Only transitions approved -> sent."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE outreach_queue SET status = 'sent', sent_at = ? "
            "WHERE campaign_id = ? AND lead_id = ? AND status = 'approved'",
            (now, campaign_id, lead_id),
        )
        if cursor.rowcount == 0:
            print("Must approve before marking sent, or not found.")
            return False
    print(f"Marked sent for lead {lead_id}.")
    return True


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def show_status(campaign_id: int, db_path: Path = DB_PATH) -> None:
    """Print campaign delivery metrics."""
    with get_db(db_path) as conn:
        campaign = conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()
        if not campaign:
            print(f"Campaign {campaign_id} not found.")
            return

        assigned = conn.execute(
            "SELECT COUNT(*) FROM campaign_leads WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()[0]

        statuses = conn.execute(
            "SELECT status, COUNT(*) as count FROM outreach_queue "
            "WHERE campaign_id = ? GROUP BY status",
            (campaign_id,),
        ).fetchall()

    status_counts = {row["status"]: row["count"] for row in statuses}
    total_queued = sum(status_counts.values())

    print(f"\nCampaign: {campaign['name']}")
    if campaign["target_date"]:
        print(f"Target date: {campaign['target_date']}")
    if campaign["segment_filter"]:
        print(f"Segments: {campaign['segment_filter']}")
    print(f"Status: {campaign['status']}")
    print(f"\nLeads assigned: {assigned}")
    print(f"Messages generated: {total_queued}")
    print(f"  Draft:    {status_counts.get('draft', 0)}")
    print(f"  Approved: {status_counts.get('approved', 0)}")
    print(f"  Sent:     {status_counts.get('sent', 0)}")
    print(f"  Skipped:  {status_counts.get('skipped', 0)}")
