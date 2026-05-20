"""Demo data seeder for GigSheet.

Populates the database with realistic test data for development and demos.
Run with: .venv/bin/python seed.py
"""

import sys
import os

# Ensure the gigsheet package root is on the path so `from app import ...` works.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db, init_db
from app.models import (
    create_user,
    create_workspace,
    add_workspace_member,
    create_lead,
    create_tag,
    assign_tag,
    create_template,
    create_campaign,
    add_recipients,
    update_campaign_status,
    update_recipient_status,
    add_pipeline_note,
    update_lead_stage,
    log_activity,
)

# ---------------------------------------------------------------------------
# Demo venue/lead data -- realistic jazz clubs, bars, and festivals
# ---------------------------------------------------------------------------
LEADS = [
    {
        "email": "booking@bluenotechi.com",
        "contact_name": "Marcus Thompson",
        "venue_name": "Blue Note Chicago",
        "capacity": 250,
        "location": "Chicago, IL",
        "genre_tags": "jazz, blues",
        "phone": "312-555-0101",
        "website": "https://bluenotechi.com",
        "source": "manual",
        "pipeline_stage": "new",
    },
    {
        "email": "events@thejazzloft.com",
        "contact_name": "Sarah Chen",
        "venue_name": "The Jazz Loft",
        "capacity": 120,
        "location": "New York, NY",
        "genre_tags": "jazz",
        "phone": "212-555-0202",
        "website": "https://thejazzloft.com",
        "source": "csv",
        "pipeline_stage": "contacted",
    },
    {
        "email": "gigs@redbirdbar.com",
        "contact_name": "Jake Wilson",
        "venue_name": "Red Bird Bar & Grill",
        "capacity": 80,
        "location": "Austin, TX",
        "genre_tags": "rock, blues",
        "phone": "512-555-0303",
        "website": "https://redbirdbar.com",
        "source": "manual",
        "pipeline_stage": "responded",
    },
    {
        "email": "talent@summerfestpdx.org",
        "contact_name": "Alicia Reyes",
        "venue_name": "Portland Summer Jazz Festival",
        "capacity": 5000,
        "location": "Portland, OR",
        "genre_tags": "jazz, festival",
        "phone": "503-555-0404",
        "website": "https://summerfestpdx.org",
        "source": "manual",
        "pipeline_stage": "interested",
    },
    {
        "email": "info@velvetlounge.com",
        "contact_name": "Derek James",
        "venue_name": "Velvet Lounge",
        "capacity": 150,
        "location": "Washington, DC",
        "genre_tags": "jazz, soul",
        "phone": "202-555-0505",
        "website": "https://velvetlounge.com",
        "source": "csv",
        "pipeline_stage": "booking_requested",
    },
    {
        "email": "bookings@rockwoodmusichall.com",
        "contact_name": "Nina Patel",
        "venue_name": "Rockwood Music Hall",
        "capacity": 100,
        "location": "New York, NY",
        "genre_tags": "rock, indie",
        "phone": "212-555-0606",
        "website": "https://rockwoodmusichall.com",
        "source": "manual",
        "pipeline_stage": "booked",
    },
    {
        "email": "events@thebitterend.com",
        "contact_name": "Tom Rossi",
        "venue_name": "The Bitter End",
        "capacity": 200,
        "location": "New York, NY",
        "genre_tags": "rock, folk",
        "phone": "212-555-0707",
        "website": "https://thebitterend.com",
        "source": "csv",
        "pipeline_stage": "new",
    },
    {
        "email": "music@bayoufest.com",
        "contact_name": "Claudette Fontenot",
        "venue_name": "Bayou Music Festival",
        "capacity": 8000,
        "location": "New Orleans, LA",
        "genre_tags": "jazz, festival, blues",
        "phone": "504-555-0808",
        "website": "https://bayoufest.com",
        "source": "manual",
        "pipeline_stage": "contacted",
    },
    {
        "email": "book@midnightjazz.com",
        "contact_name": "Robert King",
        "venue_name": "Midnight Jazz Club",
        "capacity": 90,
        "location": "Nashville, TN",
        "genre_tags": "jazz",
        "phone": "615-555-0909",
        "website": "https://midnightjazz.com",
        "source": "manual",
        "pipeline_stage": "new",
    },
    {
        "email": "talent@hollywoodbowl.com",
        "contact_name": "Lisa Chang",
        "venue_name": "Hollywood Bowl Summer Series",
        "capacity": 17500,
        "location": "Los Angeles, CA",
        "genre_tags": "jazz, festival",
        "phone": "323-555-1010",
        "website": "https://hollywoodbowl.com",
        "source": "csv",
        "pipeline_stage": "declined",
    },
    {
        "email": "gigs@smokeyjoes.com",
        "contact_name": "Bill Harper",
        "venue_name": "Smokey Joe's",
        "capacity": 60,
        "location": "Philadelphia, PA",
        "genre_tags": "blues, rock",
        "phone": "215-555-1111",
        "website": "https://smokeyjoes.com",
        "source": "manual",
        "pipeline_stage": "new",
    },
    {
        "email": "events@greenmill.com",
        "contact_name": "Angela Rivera",
        "venue_name": "Green Mill Cocktail Lounge",
        "capacity": 180,
        "location": "Chicago, IL",
        "genre_tags": "jazz",
        "phone": "773-555-1212",
        "website": "https://greenmilljazz.com",
        "source": "manual",
        "pipeline_stage": "responded",
    },
    {
        "email": "booking@sunsetjazzfest.org",
        "contact_name": "Dwayne Mitchell",
        "venue_name": "Sunset Jazz Festival",
        "capacity": 3000,
        "location": "San Diego, CA",
        "genre_tags": "jazz, festival",
        "phone": "619-555-1313",
        "website": "https://sunsetjazzfest.org",
        "source": "csv",
        "pipeline_stage": "interested",
    },
    {
        "email": "shows@thepourhousenc.com",
        "contact_name": "Megan Brooks",
        "venue_name": "The Pour House Music Hall",
        "capacity": 350,
        "location": "Raleigh, NC",
        "genre_tags": "rock, indie",
        "phone": "919-555-1414",
        "website": "https://thepourhousenc.com",
        "source": "manual",
        "pipeline_stage": "new",
    },
    {
        "email": "info@harborjazzcafe.com",
        "contact_name": "Frank Colombo",
        "venue_name": "Harbor Jazz Cafe",
        "capacity": 70,
        "location": "Boston, MA",
        "genre_tags": "jazz",
        "phone": "617-555-1515",
        "website": "https://harborjazzcafe.com",
        "source": "manual",
        "pipeline_stage": "contacted",
    },
    {
        "email": "talent@redrocksfest.com",
        "contact_name": "Karen Ostrowski",
        "venue_name": "Red Rocks Jazz & Blues Festival",
        "capacity": 9000,
        "location": "Morrison, CO",
        "genre_tags": "jazz, blues, festival",
        "phone": "303-555-1616",
        "website": "https://redrocksfest.com",
        "source": "csv",
        "pipeline_stage": "booking_requested",
    },
    {
        "email": "music@thebluebird.com",
        "contact_name": "Wendy Nakamura",
        "venue_name": "Bluebird Cafe",
        "capacity": 90,
        "location": "Nashville, TN",
        "genre_tags": "folk, jazz",
        "phone": "615-555-1717",
        "website": "https://thebluebirdcafe.com",
        "source": "manual",
        "pipeline_stage": "new",
    },
    {
        "email": "booking@ironhorsesaloon.com",
        "contact_name": "Dave Kowalski",
        "venue_name": "Iron Horse Saloon",
        "capacity": 200,
        "location": "Denver, CO",
        "genre_tags": "rock, country",
        "phone": "720-555-1818",
        "website": "https://ironhorsesaloon.com",
        "source": "manual",
        "pipeline_stage": "contacted",
    },
]


# ---------------------------------------------------------------------------
# Email template HTML with merge fields
# ---------------------------------------------------------------------------
TEMPLATE_BOOKING_INQUIRY = {
    "name": "Booking Inquiry",
    "subject_line": "Live Music Booking Inquiry for {{venue_name}}",
    "html_body": (
        "<h2>Hi {{contact_name}},</h2>"
        "<p>I'm a professional musician interested in performing at "
        "<strong>{{venue_name}}</strong> in {{location}}.</p>"
        "<p>I play jazz, blues, and soul and have a strong local following. "
        "I'd love to discuss availability and booking details.</p>"
        "<p>You can listen to samples on my website and check out my press kit.</p>"
        "<p>Looking forward to hearing from you!</p>"
        "<p>Best regards,<br>Alex Demo</p>"
    ),
}

TEMPLATE_FOLLOW_UP = {
    "name": "Follow-up",
    "subject_line": "Following up -- {{venue_name}} booking",
    "html_body": (
        "<h2>Hi {{contact_name}},</h2>"
        "<p>Just checking in on my earlier message about playing at "
        "<strong>{{venue_name}}</strong>.</p>"
        "<p>I noticed you host events for up to {{capacity}} guests -- "
        "my trio would be a great fit for that size room.</p>"
        "<p>Happy to send over a full press kit or schedule a quick call.</p>"
        "<p>Thanks,<br>Alex Demo</p>"
    ),
}


def seed():
    """Populate the database with demo data."""

    app = create_app()

    with app.app_context():
        # Initialize schema (creates tables if not present)
        init_db()
        conn = get_db()

        # ------------------------------------------------------------------
        # 1. Users
        # ------------------------------------------------------------------
        pw1 = generate_password_hash("password123", method="scrypt")
        pw2 = generate_password_hash("password123", method="scrypt")

        user1_id = create_user(conn, "musician1@test.com", pw1, "Alex Demo")
        user2_id = create_user(conn, "musician2@test.com", pw2, "Jordan Sideman")
        conn.commit()
        print(f"[seed] Created users: {user1_id}, {user2_id}")

        # ------------------------------------------------------------------
        # 2. Workspace
        # ------------------------------------------------------------------
        ws_id = create_workspace(conn, "Demo Band", "demo-band", user1_id)
        add_workspace_member(conn, ws_id, user1_id, "owner")
        add_workspace_member(conn, ws_id, user2_id, "member")
        conn.commit()
        print(f"[seed] Created workspace: {ws_id} ('Demo Band')")

        # ------------------------------------------------------------------
        # 3. Tags
        # ------------------------------------------------------------------
        tag_jazz_id = create_tag(conn, ws_id, "jazz", "#6366f1")
        tag_rock_id = create_tag(conn, ws_id, "rock", "#ef4444")
        tag_fest_id = create_tag(conn, ws_id, "festival", "#f59e0b")
        conn.commit()
        print(f"[seed] Created tags: jazz={tag_jazz_id}, rock={tag_rock_id}, festival={tag_fest_id}")

        # Tag name -> id lookup for auto-assignment
        tag_map = {
            "jazz": tag_jazz_id,
            "rock": tag_rock_id,
            "festival": tag_fest_id,
        }

        # ------------------------------------------------------------------
        # 4. Leads (18 venues)
        # ------------------------------------------------------------------
        lead_ids = []
        for lead_data in LEADS:
            lead_id = create_lead(
                conn,
                workspace_id=ws_id,
                email=lead_data["email"],
                contact_name=lead_data["contact_name"],
                venue_name=lead_data["venue_name"],
                capacity=lead_data["capacity"],
                location=lead_data["location"],
                genre_tags=lead_data["genre_tags"],
                phone=lead_data["phone"],
                website=lead_data["website"],
                source=lead_data["source"],
                created_by_user_id=user1_id,
            )
            lead_ids.append(lead_id)

            # Set the pipeline stage (create_lead defaults to 'new')
            if lead_data["pipeline_stage"] != "new":
                update_lead_stage(conn, lead_id, lead_data["pipeline_stage"])

            # Auto-assign tags based on genre_tags field
            genres = [g.strip().lower() for g in lead_data["genre_tags"].split(",")]
            for genre in genres:
                if genre in tag_map:
                    assign_tag(conn, lead_id, tag_map[genre])

        conn.commit()
        print(f"[seed] Created {len(lead_ids)} leads with tag assignments")

        # ------------------------------------------------------------------
        # 5. Email templates
        # ------------------------------------------------------------------
        tmpl1_id = create_template(
            conn, ws_id,
            TEMPLATE_BOOKING_INQUIRY["name"],
            TEMPLATE_BOOKING_INQUIRY["subject_line"],
            TEMPLATE_BOOKING_INQUIRY["html_body"],
            user1_id,
        )
        tmpl2_id = create_template(
            conn, ws_id,
            TEMPLATE_FOLLOW_UP["name"],
            TEMPLATE_FOLLOW_UP["subject_line"],
            TEMPLATE_FOLLOW_UP["html_body"],
            user1_id,
        )
        conn.commit()
        print(f"[seed] Created templates: {tmpl1_id} (Booking Inquiry), {tmpl2_id} (Follow-up)")

        # ------------------------------------------------------------------
        # 6. Campaigns
        # ------------------------------------------------------------------

        # Campaign 1 -- Draft (not sent yet), uses "Booking Inquiry" template
        camp1_id = create_campaign(conn, ws_id, "Q3 Jazz Club Outreach", tmpl1_id, user1_id)
        # Add first 8 leads as recipients
        add_recipients(conn, camp1_id, lead_ids[:8])
        conn.commit()
        print(f"[seed] Created draft campaign: {camp1_id} ('Q3 Jazz Club Outreach') with 8 recipients")

        # Campaign 2 -- Sent with mock delivery data, uses "Follow-up" template
        camp2_id = create_campaign(conn, ws_id, "Festival Season Follow-ups", tmpl2_id, user1_id)
        # Add leads 8-14 as recipients
        camp2_lead_ids = lead_ids[8:15]
        add_recipients(conn, camp2_id, camp2_lead_ids)
        conn.commit()

        # Transition campaign 2 to 'sent' with mock delivery counters
        update_campaign_status(conn, camp2_id, "sending")
        # update_campaign_status already commits

        # Simulate delivery: mark some recipients as sent/delivered/opened
        camp2_recipients = conn.execute(
            "SELECT id FROM campaign_recipients WHERE campaign_id = ?",
            (camp2_id,),
        ).fetchall()

        delivery_statuses = ["delivered", "delivered", "delivered", "opened", "opened", "sent", "bounced"]
        for i, recip in enumerate(camp2_recipients):
            status = delivery_statuses[i] if i < len(delivery_statuses) else "delivered"
            mock_msg_id = f"mock-msg-{camp2_id}-{recip['id']}"
            update_recipient_status(conn, recip["id"], status, mock_msg_id)

        # Update campaign aggregate counters to match
        # 3 delivered + 2 opened (also delivered) + 1 sent + 1 bounced = 7 total
        conn.execute(
            """UPDATE campaigns SET
                sent_count = 7, delivered_count = 5, opened_count = 2,
                bounced_count = 1, total_recipients = 7
            WHERE id = ?""",
            (camp2_id,),
        )
        conn.commit()

        # Mark campaign as fully sent
        update_campaign_status(conn, camp2_id, "sent")

        # Insert campaign_progress row for the sent campaign
        conn.execute(
            """INSERT INTO campaign_progress (campaign_id, total, sent, delivered, failed, status)
            VALUES (?, 7, 7, 5, 1, 'completed')""",
            (camp2_id,),
        )
        conn.commit()
        print(f"[seed] Created sent campaign: {camp2_id} ('Festival Season Follow-ups') with mock delivery")

        # ------------------------------------------------------------------
        # 7. Pipeline notes on a few leads
        # ------------------------------------------------------------------
        # Note on lead 1 (Blue Note Chicago) -- 'new' stage
        add_pipeline_note(conn, lead_ids[0], user1_id, "Great venue, need to follow up after weekend.")
        # Note on lead 3 (Red Bird Bar) -- 'responded' stage
        add_pipeline_note(conn, lead_ids[2], user1_id, "Jake said they're looking for a Friday night act. Send press kit.")
        add_pipeline_note(conn, lead_ids[2], user2_id, "I know Jake -- he prefers blues-rock sets. 90 min max.")
        # Note on lead 5 (Velvet Lounge) -- 'booking_requested' stage
        add_pipeline_note(conn, lead_ids[4], user1_id, "Sent contract. Waiting for Derek to confirm date (Aug 15).")
        # Note on lead 6 (Rockwood Music Hall) -- 'booked' stage
        add_pipeline_note(conn, lead_ids[5], user1_id, "Confirmed! Sept 20, 8pm slot. $500 guarantee + door split.")
        conn.commit()
        print("[seed] Created 5 pipeline notes across 4 leads")

        # ------------------------------------------------------------------
        # 8. Activity log entries
        # ------------------------------------------------------------------
        log_activity(conn, ws_id, user1_id, "created_workspace", "workspace", ws_id, "Created 'Demo Band' workspace")
        log_activity(conn, ws_id, user1_id, "imported_leads", "lead", None, "Imported 18 leads via CSV and manual entry")
        log_activity(conn, ws_id, user1_id, "created_campaign", "campaign", camp1_id, "Created 'Q3 Jazz Club Outreach' campaign")
        log_activity(conn, ws_id, user1_id, "created_campaign", "campaign", camp2_id, "Created 'Festival Season Follow-ups' campaign")
        log_activity(conn, ws_id, user1_id, "sent_campaign", "campaign", camp2_id, "Sent 'Festival Season Follow-ups' to 7 recipients")
        log_activity(conn, ws_id, user1_id, "moved_lead", "lead", lead_ids[5], "Moved 'Rockwood Music Hall' to booked")
        log_activity(conn, ws_id, user2_id, "added_note", "lead", lead_ids[2], "Added note on 'Red Bird Bar & Grill'")
        log_activity(conn, ws_id, user1_id, "created_template", "template", tmpl1_id, "Created 'Booking Inquiry' template")
        log_activity(conn, ws_id, user1_id, "created_template", "template", tmpl2_id, "Created 'Follow-up' template")
        log_activity(conn, ws_id, user1_id, "created_tag", "tag", tag_jazz_id, "Created 'jazz' tag")
        conn.commit()
        print("[seed] Created 10 activity log entries")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n=== Seed complete ===")
        print(f"  Users:      2 (musician1@test.com, musician2@test.com)")
        print(f"  Workspace:  'Demo Band' (id={ws_id})")
        print(f"  Leads:      {len(lead_ids)}")
        print(f"  Tags:       3 (jazz, rock, festival)")
        print(f"  Templates:  2")
        print(f"  Campaigns:  2 (1 draft, 1 sent)")
        print(f"  Notes:      5")
        print(f"  Activity:   10 entries")
        print(f"\nLogin: musician1@test.com / password123")
        print(f"       musician2@test.com / password123")


if __name__ == "__main__":
    seed()
