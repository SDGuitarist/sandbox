import os
import uuid
import unicodedata

from flask import (
    Blueprint, current_app, flash, g, abort,
    redirect, render_template, request, send_from_directory, url_for,
)
from PIL import Image

from app.db import get_db
from app.decorators import login_required, require_workspace
from app.models import (
    create_file_record, get_file, get_files_by_workspace,
    delete_file_record, log_activity,
)
from app import ALLOWED_EXTENSIONS, limiter

# Set at module import level -- prevents decompression bomb attacks (FC pitfall)
Image.MAX_IMAGE_PIXELS = 50_000_000

file_uploads_bp = Blueprint('file_uploads', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(filename: str) -> str:
    """NFKC normalize, strip null bytes, basename only, cap 200 chars."""
    name = unicodedata.normalize('NFKC', filename)
    name = name.replace('\x00', '')
    name = os.path.basename(name)  # Strip path components
    return name[:200]


def allowed_file(filename: str) -> bool:
    """Check extension against the ALLOWLIST (not denylist)."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@file_uploads_bp.route('/')
@login_required
@require_workspace
def index():
    """List all files for the current workspace."""
    conn = get_db()
    files = get_files_by_workspace(conn, g.workspace['id'])
    return render_template('file_uploads/index.html', files=files)


@file_uploads_bp.route('/upload', methods=['POST'])
@login_required
@require_workspace
@limiter.limit('10/minute')
def upload():
    """Upload a file to the current workspace."""
    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('file_uploads.index'))

    file = request.files['file']

    if file.filename == '' or file.filename is None:
        flash('No file selected.', 'error')
        return redirect(url_for('file_uploads.index'))

    # Sanitize and validate
    original_name = sanitize_filename(file.filename)

    if not allowed_file(original_name):
        flash('File type not allowed.', 'error')
        return redirect(url_for('file_uploads.index'))

    # UUID filename to prevent collisions and path traversal
    ext = os.path.splitext(original_name)[1].lower()
    stored_name = uuid.uuid4().hex + ext

    # Ensure workspace upload directory exists
    upload_dir = os.path.join(
        current_app.config['UPLOAD_FOLDER'], str(g.workspace['id'])
    )
    os.makedirs(upload_dir, exist_ok=True)

    # Save to disk
    file_path = os.path.join(upload_dir, stored_name)
    file.save(file_path)

    # Get file size after saving
    file_size = os.path.getsize(file_path)

    # Determine content type (fall back to octet-stream)
    content_type = file.content_type or 'application/octet-stream'

    # Record in database and log activity
    conn = get_db()
    file_id = create_file_record(
        conn,
        workspace_id=g.workspace['id'],
        filename_original=original_name,
        filename_stored=stored_name,
        file_ext=ext,
        file_size_bytes=file_size,
        content_type=content_type,
        uploaded_by_user_id=g.user['id'],
    )
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'uploaded_file', 'file', file_id, f'File: {original_name}',
    )
    conn.commit()

    flash('File uploaded.', 'success')
    return redirect(url_for('file_uploads.index'))


@file_uploads_bp.route('/<int:file_id>')
@login_required
@require_workspace
def serve(file_id):
    """Serve a file with Content-Disposition: attachment."""
    conn = get_db()
    f = get_file(conn, file_id)
    if f is None:
        abort(404)
    # FC35: verify file belongs to current workspace
    if f['workspace_id'] != g.workspace['id']:
        abort(403)
    upload_dir = os.path.join(
        current_app.config['UPLOAD_FOLDER'], str(g.workspace['id'])
    )
    return send_from_directory(
        upload_dir, f['filename_stored'],
        as_attachment=True, download_name=f['filename_original'],
    )


@file_uploads_bp.route('/<int:file_id>/delete', methods=['POST'])
@login_required
@require_workspace
def delete(file_id):
    """Delete a file record and remove the stored file from disk."""
    conn = get_db()
    f = get_file(conn, file_id)
    if f is None:
        abort(404)
    # FC35: verify file belongs to current workspace
    if f['workspace_id'] != g.workspace['id']:
        abort(403)

    # Remove file from disk
    upload_dir = os.path.join(
        current_app.config['UPLOAD_FOLDER'], str(g.workspace['id'])
    )
    stored_path = os.path.join(upload_dir, f['filename_stored'])
    if os.path.exists(stored_path):
        os.remove(stored_path)

    # Delete record and log
    delete_file_record(conn, file_id)
    log_activity(
        conn, g.workspace['id'], g.user['id'],
        'deleted_file', 'file', file_id, f'File: {f["filename_original"]}',
    )
    conn.commit()

    flash('File deleted.', 'success')
    return redirect(url_for('file_uploads.index'))
