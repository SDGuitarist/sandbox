import csv
import io
import sys
from pathlib import Path

from flask import Flask, render_template, request, make_response, redirect, url_for

# Ensure imports work when run from any directory
sys.path.insert(0, str(Path(__file__).parent))

from db import DB_PATH, init_db, get_db
from models import query_leads, query_leads_scored, delete_lead, VALID_SOURCES
from utils import sanitize_csv_cell


def create_app(db_path=DB_PATH):
    db_path = Path(db_path)
    app = Flask(__name__)
    init_db(db_path)

    @app.get("/")
    def index():
        source = request.args.get("source", "").strip()
        q = request.args.get("q", "").strip()
        try:
            page = max(1, min(int(request.args.get("page", 1)), 10000))
        except (ValueError, TypeError):
            page = 1
        per_page = 100
        offset = (page - 1) * per_page

        # Ignore invalid source values
        if source and source not in VALID_SOURCES:
            source = ""

        leads, total = query_leads_scored(
            source=source,
            q=q,
            db_path=db_path,
            limit=per_page,
            offset=offset,
        )
        has_next = offset + per_page < total

        return render_template(
            "index.html",
            leads=leads,
            source=source,
            q=q,
            page=page,
            has_next=has_next,
            valid_sources=sorted(VALID_SOURCES),
            total=total,
        )

    @app.get("/leads/export.csv")
    def export_csv():
        source = request.args.get("source", "").strip()
        q = request.args.get("q", "").strip()

        if source and source not in VALID_SOURCES:
            source = ""

        leads, _ = query_leads(source=source, q=q, db_path=db_path, limit=100000)

        fieldnames = ["id", "name", "bio", "location", "email", "phone", "website", "profile_url", "activity", "source", "scraped_at", "enriched_at"]
        si = io.StringIO()
        writer = csv.DictWriter(si, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            row = {k: sanitize_csv_cell(lead[k]) for k in fieldnames}
            writer.writerow(row)

        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=leads.csv"
        output.headers["Content-Type"] = "text/csv"
        return output

    @app.get("/campaigns")
    def campaigns():
        with get_db(db_path) as conn:
            rows = conn.execute(
                "SELECT c.*, "
                "(SELECT COUNT(*) FROM campaign_leads cl WHERE cl.campaign_id = c.id) as assigned, "
                "(SELECT COUNT(*) FROM outreach_queue oq WHERE oq.campaign_id = c.id) as total_messages "
                "FROM campaigns c ORDER BY c.created_at DESC"
            ).fetchall()

            campaign_list = []
            for row in rows:
                c = dict(row)
                statuses = conn.execute(
                    "SELECT status, COUNT(*) as count FROM outreach_queue "
                    "WHERE campaign_id = ? GROUP BY status",
                    (c["id"],),
                ).fetchall()
                c["statuses"] = {s["status"]: s["count"] for s in statuses}

                # Per-segment breakdown
                segments = conn.execute(
                    "SELECT l.segment, oq.status, COUNT(*) as count "
                    "FROM outreach_queue oq JOIN leads l ON oq.lead_id = l.id "
                    "WHERE oq.campaign_id = ? GROUP BY l.segment, oq.status",
                    (c["id"],),
                ).fetchall()
                seg_data = {}
                for s in segments:
                    seg = s["segment"] or "unknown"
                    if seg not in seg_data:
                        seg_data[seg] = {}
                    seg_data[seg][s["status"]] = s["count"]
                c["segments"] = seg_data

                # Conversion metrics
                sent = sum(c["statuses"].get(s, 0) for s in ("sent", "replied", "booked", "declined", "no_response"))
                replied = c["statuses"].get("replied", 0) + c["statuses"].get("booked", 0)
                booked = c["statuses"].get("booked", 0)
                c["sent_total"] = sent
                c["reply_rate"] = round(replied / sent * 100) if sent else 0
                c["book_rate"] = round(booked / sent * 100) if sent else 0

                campaign_list.append(c)

        return render_template("campaigns.html", campaigns=campaign_list)

    @app.post("/leads/<int:lead_id>/delete")
    def delete(lead_id):
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            return "CSRF check failed", 403
        delete_lead(lead_id, db_path)
        return "", 204

    return app
