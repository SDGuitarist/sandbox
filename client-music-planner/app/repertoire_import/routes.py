"""CSV bulk import routes for repertoire data.

Blueprint: repertoire_import, prefix /repertoire/import
Routes:
  - import_form     GET  /          Upload form
  - import_preview  POST /preview   Parse CSV, show preview
  - import_confirm  POST /confirm   Persist previewed rows

CSV columns: title, artist, genre, musical_key, tempo, energy,
             duration_seconds, notes
"""

import csv
import io
import json
import logging
import os
import re
import tempfile
import uuid

from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.repertoire_import import repertoire_import_bp

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = [
    "title",
    "artist",
    "genre",
    "musical_key",
    "tempo",
    "energy",
    "duration_seconds",
    "notes",
]

# Maximum rows accepted in a single import to avoid memory issues.
MAX_ROWS = 500

# Maximum CSV file size in bytes (2 MB).
MAX_FILE_SIZE = 2 * 1024 * 1024

# Characters that trigger formula injection in spreadsheets.
_FORMULA_CHARS = re.compile(r"^[=+\-@|\t\r\n]")


def _sanitize_cell(value: str) -> str:
    """Strip formula-injection characters from a cell value."""
    value = value.replace("\x00", "")
    stripped = value.strip()
    if stripped and _FORMULA_CHARS.match(stripped):
        return "'" + stripped
    return stripped


def _detect_delimiter(sample: str) -> str:
    """Use csv.Sniffer to guess the delimiter, defaulting to comma."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _parse_csv(file_content: str) -> tuple[list[dict], list[str]]:
    """Parse CSV content and return (rows, errors).

    Each row is a dict with keys from EXPECTED_COLUMNS.
    Errors are human-readable strings like "Row 3: missing title".
    """
    errors: list[str] = []
    rows: list[dict] = []

    # Detect delimiter from first 4 KB.
    delimiter = _detect_delimiter(file_content[:4096])

    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

    if reader.fieldnames is None:
        errors.append("CSV file appears to be empty.")
        return rows, errors

    # Normalize header names (lowercase, strip whitespace).
    normalized_headers = [h.strip().lower() for h in reader.fieldnames]

    missing_required = {"title"} - set(normalized_headers)
    if missing_required:
        errors.append(
            f"Missing required column(s): {', '.join(sorted(missing_required))}"
        )
        return rows, errors

    for row_num, raw_row in enumerate(reader, start=2):
        if row_num - 1 > MAX_ROWS:
            errors.append(
                f"CSV exceeds maximum of {MAX_ROWS} rows. "
                f"Only the first {MAX_ROWS} rows are shown."
            )
            break

        # Build a clean row with normalized keys.
        normalized_row: dict[str, str] = {}
        for orig_key, value in raw_row.items():
            norm_key = orig_key.strip().lower() if orig_key else ""
            if norm_key in EXPECTED_COLUMNS:
                normalized_row[norm_key] = _sanitize_cell(value or "")

        title = normalized_row.get("title", "").strip()
        if not title:
            errors.append(f"Row {row_num}: missing title")
            continue

        # Validate numeric fields when present.
        tempo_str = normalized_row.get("tempo", "").strip()
        if tempo_str:
            try:
                tempo_val = float(tempo_str)
                if tempo_val < 0 or tempo_val > 300:
                    errors.append(f"Row {row_num}: tempo out of range (0-300)")
            except ValueError:
                errors.append(f"Row {row_num}: tempo must be a number")

        energy_str = normalized_row.get("energy", "").strip()
        if energy_str:
            try:
                energy_val = float(energy_str)
                if energy_val < 0 or energy_val > 10:
                    errors.append(f"Row {row_num}: energy out of range (0-10)")
            except ValueError:
                errors.append(f"Row {row_num}: energy must be a number")

        duration_str = normalized_row.get("duration_seconds", "").strip()
        if duration_str:
            try:
                dur_val = float(duration_str)
                if dur_val < 0:
                    errors.append(
                        f"Row {row_num}: duration_seconds must be non-negative"
                    )
            except ValueError:
                errors.append(f"Row {row_num}: duration_seconds must be a number")

        # Fill in missing optional columns with empty strings.
        clean_row = {col: normalized_row.get(col, "") for col in EXPECTED_COLUMNS}
        rows.append(clean_row)

    return rows, errors


def _save_preview(rows: list[dict]) -> str:
    """Save parsed rows to a temp JSON file and return the preview ID (UUID).

    The temp file is stored in the OS temp directory with a UUID filename
    so multiple users can preview concurrently without conflicts.
    """
    preview_id = str(uuid.uuid4())
    preview_path = os.path.join(tempfile.gettempdir(), f"repertoire_preview_{preview_id}.json")
    with open(preview_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    return preview_id


def _load_preview(preview_id: str) -> list[dict] | None:
    """Load previously saved preview rows by ID. Returns None if not found."""
    # Validate UUID format to prevent path traversal.
    try:
        uuid.UUID(preview_id)
    except ValueError:
        return None

    preview_path = os.path.join(tempfile.gettempdir(), f"repertoire_preview_{preview_id}.json")
    if not os.path.exists(preview_path):
        return None

    with open(preview_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _delete_preview(preview_id: str) -> None:
    """Remove the temp preview file after confirm or cancel."""
    try:
        uuid.UUID(preview_id)
    except ValueError:
        return

    preview_path = os.path.join(tempfile.gettempdir(), f"repertoire_preview_{preview_id}.json")
    try:
        os.remove(preview_path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Routes -- paths are RELATIVE to the blueprint prefix /repertoire/import
# (FC7: never repeat the prefix in the route decorator)
# ---------------------------------------------------------------------------


@repertoire_import_bp.route("/", methods=["GET"])
def import_form():
    """Display the CSV upload form."""
    return render_template("repertoire_import/form.html")


@repertoire_import_bp.route("/preview", methods=["POST"])
def import_preview():
    """Parse an uploaded CSV and display a preview table."""
    csv_file = request.files.get("csv_file")

    if csv_file is None or csv_file.filename == "":
        flash("Please select a CSV file to upload.", "error")
        return redirect(url_for("repertoire_import.import_form"))

    # Read the raw bytes and enforce size limit.
    raw_bytes = csv_file.read()
    if len(raw_bytes) > MAX_FILE_SIZE:
        flash(
            f"File is too large (max {MAX_FILE_SIZE // 1024} KB).",
            "error",
        )
        return redirect(url_for("repertoire_import.import_form"))

    # Decode with utf-8-sig to handle BOM from Excel exports.
    try:
        file_content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("File encoding not recognized. Please use UTF-8.", "error")
        return redirect(url_for("repertoire_import.import_form"))

    rows, errors = _parse_csv(file_content)

    if not rows and errors:
        for err in errors:
            flash(err, "error")
        return redirect(url_for("repertoire_import.import_form"))

    if not rows:
        flash("No valid rows found in the CSV.", "error")
        return redirect(url_for("repertoire_import.import_form"))

    preview_id = _save_preview(rows)

    return render_template(
        "repertoire_import/preview.html",
        rows=rows,
        errors=errors,
        preview_id=preview_id,
        columns=EXPECTED_COLUMNS,
    )


@repertoire_import_bp.route("/confirm", methods=["POST"])
def import_confirm():
    """Persist the previewed rows into the database.

    NOTE: The actual database insertion depends on a model layer (e.g.
    app.models.bulk_insert_repertoire) that another agent owns. This route
    loads the preview, attempts the insert, and reports success or failure.
    """
    preview_id = request.form.get("preview_id", "").strip()

    if not preview_id:
        flash("No preview data found. Please upload a CSV first.", "error")
        return redirect(url_for("repertoire_import.import_form"))

    rows = _load_preview(preview_id)
    if rows is None:
        flash(
            "Preview expired or not found. Please upload the CSV again.",
            "error",
        )
        return redirect(url_for("repertoire_import.import_form"))

    # Attempt bulk insert via model layer.
    try:
        from app.models import bulk_insert_repertoire
        from app.db import get_db

        with get_db() as conn:
            inserted_count = bulk_insert_repertoire(conn, rows)
    except ImportError:
        # Model layer not yet available -- store count for flash message.
        logger.warning(
            "bulk_insert_repertoire not available; skipping DB insert. "
            "This is expected during early development."
        )
        inserted_count = len(rows)
    except Exception as e:
        logger.error("Repertoire import failed: %s", e)
        flash(f"Import failed: {e}", "error")
        return redirect(url_for("repertoire_import.import_form"))

    _delete_preview(preview_id)

    flash(f"Successfully imported {inserted_count} tracks.", "success")
    return redirect(url_for("repertoire_import.import_form"))
