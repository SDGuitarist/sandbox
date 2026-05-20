import csv
import os
import re
import uuid

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, abort
)

from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import create_lead, assign_tag, log_activity

lead_import_bp = Blueprint('lead_import', __name__)

MAX_CSV_ROWS = 5000
PREVIEW_LIMIT = 100
FORMULA_CHARS = set('=-+@|')

# Expected CSV header names mapped to create_lead keyword arguments.
# Column order when has_header is False:
#   0=email, 1=contact_name, 2=venue_name, 3=capacity, 4=location,
#   5=genre_tags, 6=phone, 7=website
HEADER_MAP = [
    'email', 'contact_name', 'venue_name', 'capacity',
    'location', 'genre_tags', 'phone', 'website',
]


def sanitize_csv_cell(value: str) -> str:
    """Prevent formula injection in CSV values."""
    if value and value[0] in FORMULA_CHARS:
        return "'" + value
    return value


def parse_csv_upload(file_storage, has_header: bool) -> tuple:
    """Parse uploaded CSV, return (preview_rows, error_rows, temp_filename).

    Saves raw CSV to temp file for the commit step.
    """
    temp_name = f'import_{uuid.uuid4().hex[:12]}.csv'
    temp_path = os.path.join('/tmp', temp_name)
    file_storage.save(temp_path)

    preview_rows = []
    error_rows = []
    with open(temp_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f) if has_header else csv.reader(f)
        for i, row in enumerate(reader):
            if i >= PREVIEW_LIMIT:
                break
            # Validate: email required
            email = (
                row.get('email', '') if has_header
                else (row[0] if len(row) > 0 else '')
            ).strip()
            if not email or '@' not in email:
                error_rows.append({
                    'row': i + 1,
                    'reason': 'Missing or invalid email',
                    'data': row,
                })
                continue
            preview_rows.append(row)
    return preview_rows, error_rows, temp_name


def _row_to_dict(row, has_header: bool) -> dict:
    """Convert a CSV row (dict or list) to a dict with sanitized values."""
    if has_header:
        return {
            key: sanitize_csv_cell(str(row.get(key, '')).strip())
            for key in HEADER_MAP
        }
    # No header -- positional mapping
    result = {}
    for idx, key in enumerate(HEADER_MAP):
        raw = row[idx] if idx < len(row) else ''
        result[key] = sanitize_csv_cell(str(raw).strip())
    return result


# ---- Routes ----

@lead_import_bp.route('/')
@login_required
@require_workspace
def index():
    """Show the CSV upload form."""
    return render_template('lead_import/index.html')


@lead_import_bp.route('/upload', methods=['POST'])
@login_required
@require_workspace
def upload():
    """Parse the uploaded CSV and show a preview."""
    csv_file = request.files.get('csv_file')
    if csv_file is None or csv_file.filename == '':
        flash('Please select a CSV file.', 'error')
        return redirect(url_for('lead_import.index'))

    # Basic extension check
    if not csv_file.filename.lower().endswith('.csv'):
        flash('Only .csv files are accepted.', 'error')
        return redirect(url_for('lead_import.index'))

    has_header = bool(request.form.get('has_header'))

    try:
        preview_rows, error_rows, temp_name = parse_csv_upload(csv_file, has_header)
    except Exception:
        flash('Could not read that CSV file. Please check the format.', 'error')
        return redirect(url_for('lead_import.index'))

    if not preview_rows:
        flash('No valid rows found in the CSV.', 'error')
        return redirect(url_for('lead_import.index'))

    return render_template(
        'lead_import/preview.html',
        preview_rows=preview_rows,
        error_rows=error_rows,
        temp_name=temp_name,
        has_header=has_header,
    )


@lead_import_bp.route('/commit', methods=['POST'])
@login_required
@require_workspace
def commit():
    """Read the temp CSV, create leads, delete temp file."""
    temp_name = request.form.get('filename', '').strip()
    if not temp_name:
        flash('Missing import file reference.', 'error')
        return redirect(url_for('lead_import.index'))

    # Prevent path traversal -- temp_name must be a simple filename
    if '/' in temp_name or '\\' in temp_name or '..' in temp_name:
        abort(400)

    temp_path = os.path.join('/tmp', temp_name)
    if not os.path.isfile(temp_path):
        flash('Import file expired. Please upload again.', 'error')
        return redirect(url_for('lead_import.index'))

    has_header = bool(request.form.get('has_header'))

    conn = get_db()
    created_count = 0
    skipped_count = 0

    try:
        conn.execute('BEGIN IMMEDIATE')

        with open(temp_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f) if has_header else csv.reader(f)
            for i, row in enumerate(reader):
                if i >= MAX_CSV_ROWS:
                    flash(
                        f'Import capped at {MAX_CSV_ROWS} rows. '
                        f'Remaining rows were skipped.',
                        'warning',
                    )
                    break

                data = _row_to_dict(row, has_header)
                email = data.get('email', '').strip()

                # Skip rows without a valid email
                if not email or '@' not in email:
                    skipped_count += 1
                    continue

                capacity_raw = data.get('capacity', '0')
                try:
                    capacity = int(capacity_raw)
                except (ValueError, TypeError):
                    capacity = 0

                create_lead(
                    conn,
                    workspace_id=g.workspace['id'],
                    email=email,
                    contact_name=data.get('contact_name', ''),
                    venue_name=data.get('venue_name', ''),
                    capacity=capacity,
                    location=data.get('location', ''),
                    genre_tags=data.get('genre_tags', ''),
                    phone=data.get('phone', ''),
                    website=data.get('website', ''),
                    source='csv',
                    created_by_user_id=g.user['id'],
                )
                created_count += 1

        log_activity(
            conn,
            g.workspace['id'],
            g.user['id'],
            'imported_leads',
            'lead',
            None,
            f'Imported {created_count} leads from CSV',
        )
        conn.commit()
    except Exception:
        conn.rollback()
        flash('Import failed. Please try again.', 'error')
        return redirect(url_for('lead_import.index'))
    finally:
        # Clean up temp file
        try:
            os.remove(temp_path)
        except OSError:
            pass

    if skipped_count:
        flash(f'{skipped_count} rows skipped due to missing email.', 'warning')

    flash(f'Successfully imported {created_count} leads.', 'success')
    return redirect(url_for('lead_list.index'))
