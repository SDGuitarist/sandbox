import csv
import io
import sys
from pathlib import Path

from flask import Flask, render_template, request, make_response, redirect, url_for

# Ensure imports work when run from any directory
sys.path.insert(0, str(Path(__file__).parent))

from db import init_db
from models import query_leads, delete_lead, VALID_SOURCES
from utils import sanitize_csv_cell


def create_app():
    app = Flask(__name__)
    init_db()

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

        leads, total = query_leads(source=source, q=q, limit=per_page, offset=offset)
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

        leads, _ = query_leads(source=source, q=q, limit=100000)

        fieldnames = ["id", "name", "bio", "location", "email", "profile_url", "activity", "source", "scraped_at"]
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

    @app.post("/leads/<int:lead_id>/delete")
    def delete(lead_id):
        delete_lead(lead_id)
        return redirect(url_for("index"))

    return app
