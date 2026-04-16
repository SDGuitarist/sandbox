import csv
import io
import sys
from pathlib import Path

from flask import Flask, render_template, request, make_response, redirect, url_for

# Ensure imports work when run from any directory
sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, DB_PATH
from models import get_all_leads, get_leads_by_source, search_leads, count_leads, delete_lead, VALID_SOURCES


def _sanitize_cell(value):
    """Prevent CSV formula injection."""
    if value and isinstance(value, str) and value[0] in ("=", "-", "+", "@"):
        return "\t" + value
    return value


def create_app():
    app = Flask(__name__)
    init_db()

    @app.get("/")
    def index():
        source = request.args.get("source", "").strip()
        q = request.args.get("q", "").strip()
        page = max(1, int(request.args.get("page", 1)))
        per_page = 100
        offset = (page - 1) * per_page

        if q:
            leads = search_leads(q, limit=per_page, offset=offset)
        elif source and source in VALID_SOURCES:
            leads = get_leads_by_source(source, limit=per_page, offset=offset)
        else:
            source = ""  # ignore invalid source values
            leads = get_all_leads(limit=per_page, offset=offset)

        total = count_leads()
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

        if q:
            leads = search_leads(q, limit=100000)
        elif source and source in VALID_SOURCES:
            leads = get_leads_by_source(source, limit=100000)
        else:
            leads = get_all_leads(limit=100000)

        fieldnames = ["id", "name", "bio", "location", "email", "profile_url", "activity", "source", "scraped_at"]
        si = io.StringIO()
        writer = csv.DictWriter(si, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            row = {k: _sanitize_cell(lead[k]) for k in fieldnames}
            writer.writerow(row)

        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=leads.csv"
        output.headers["Content-Type"] = "text/csv"
        return output

    @app.post("/leads/<int:lead_id>/delete")
    def delete(lead_id):
        delete_lead(lead_id)
        return redirect(url_for("index"))

    return app
