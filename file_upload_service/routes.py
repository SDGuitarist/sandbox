"""
Flask route handlers for the file upload service.

Endpoints:
  POST  /files                      — upload a file (multipart)
  GET   /files                      — list all files
  GET   /files/<file_id>            — file metadata + job statuses
  GET   /files/<file_id>/download   — serve original file
  GET   /files/<file_id>/thumbnail  — serve thumbnail (if available)
  GET   /files/<file_id>/metadata   — return extracted metadata JSON
"""
import json
import mimetypes
import os

from flask import Blueprint, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

from db import get_connection, generate_file_id, get_file_upload_dir, is_valid_file_id, UPLOAD_DIR

bp = Blueprint("file_upload", __name__)

ALLOWED_EXTENSIONS = None  # Accept any file type
MAX_FILENAME_LEN = 255


def _validate_file_id(file_id: str):
    """Return 400 response if file_id is not a valid UUID."""
    if not is_valid_file_id(file_id):
        abort(400, description="Invalid file ID format")


# ---------------------------------------------------------------------------
# POST /files
# ---------------------------------------------------------------------------
@bp.route("/files", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "no file field in request"}), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "no file selected"}), 400

    # Sanitize filename — used for display only, NOT for path construction
    original_filename = secure_filename(f.filename)
    if not original_filename:
        original_filename = "upload"

    # Determine content type and extension
    content_type = f.content_type or "application/octet-stream"
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower() if ext else ""

    # Generate UUID file_id and create its directory
    file_id = generate_file_id()
    file_dir = get_file_upload_dir(file_id)  # UUID-validated, safe
    os.makedirs(file_dir, exist_ok=True)

    # Save file using sanitized extension (never user-supplied path)
    save_ext = ext if ext else ".bin"
    save_path = os.path.join(file_dir, f"original{save_ext}")
    f.save(save_path)
    size_bytes = os.path.getsize(save_path)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO files (id, original_filename, content_type, size_bytes, upload_dir_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_id, original_filename, content_type, size_bytes, file_dir),
        )
        # Enqueue one processing job per type
        conn.execute(
            "INSERT INTO processing_jobs (file_id, job_type) VALUES (?, 'thumbnail')",
            (file_id,),
        )
        conn.execute(
            "INSERT INTO processing_jobs (file_id, job_type) VALUES (?, 'metadata')",
            (file_id,),
        )
        conn.commit()

    return jsonify({
        "file_id": file_id,
        "original_filename": original_filename,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "status": "uploaded",
    }), 202


# ---------------------------------------------------------------------------
# GET /files
# ---------------------------------------------------------------------------
@bp.route("/files", methods=["GET"])
def list_files():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, original_filename, content_type, size_bytes, status, created_at
            FROM files ORDER BY created_at DESC
            """
        ).fetchall()
    return jsonify({"files": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# GET /files/<file_id>
# ---------------------------------------------------------------------------
@bp.route("/files/<file_id>", methods=["GET"])
def get_file(file_id):
    _validate_file_id(file_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, original_filename, content_type, size_bytes, status, created_at FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404

        jobs = conn.execute(
            """
            SELECT id, job_type, status, attempt_count, max_attempts,
                   created_at, completed_at, error_message
            FROM processing_jobs WHERE file_id = ?
            """,
            (file_id,),
        ).fetchall()

    return jsonify({
        "file": dict(row),
        "processing_jobs": [dict(j) for j in jobs],
    })


# ---------------------------------------------------------------------------
# GET /files/<file_id>/download
# ---------------------------------------------------------------------------
@bp.route("/files/<file_id>/download", methods=["GET"])
def download_file(file_id):
    _validate_file_id(file_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT original_filename, content_type, upload_dir_path FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    # Path constructed from DB value (uuid-named dir) + known extension
    file_dir = row["upload_dir_path"]
    # Find the original file — it's named original.<ext>
    for fname in os.listdir(file_dir):
        if fname.startswith("original"):
            return send_file(
                os.path.join(file_dir, fname),
                download_name=row["original_filename"],
                as_attachment=True,
            )
    return jsonify({"error": "file not found on disk"}), 404


# ---------------------------------------------------------------------------
# GET /files/<file_id>/thumbnail
# ---------------------------------------------------------------------------
@bp.route("/files/<file_id>/thumbnail", methods=["GET"])
def get_thumbnail(file_id):
    _validate_file_id(file_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404

        result = conn.execute(
            "SELECT result_path FROM file_results WHERE file_id = ? AND result_type = 'thumbnail'",
            (file_id,),
        ).fetchone()

        if result is None:
            job = conn.execute(
                "SELECT status FROM processing_jobs WHERE file_id = ? AND job_type = 'thumbnail'",
                (file_id,),
            ).fetchone()
            if job and job["status"] == "failed":
                return jsonify({"error": "thumbnail processing failed (non-image file?)"}), 422
            return jsonify({"error": "thumbnail not yet available", "status": "processing"}), 202

    thumb_path = result["result_path"]
    if not os.path.exists(thumb_path):
        return jsonify({"error": "thumbnail file missing"}), 404
    return send_file(thumb_path, mimetype="image/jpeg")


# ---------------------------------------------------------------------------
# GET /files/<file_id>/metadata
# ---------------------------------------------------------------------------
@bp.route("/files/<file_id>/metadata", methods=["GET"])
def get_metadata(file_id):
    _validate_file_id(file_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404

        result = conn.execute(
            "SELECT result_json FROM file_results WHERE file_id = ? AND result_type = 'metadata'",
            (file_id,),
        ).fetchone()

        if result is None:
            return jsonify({"error": "metadata not yet available", "status": "processing"}), 202

    return jsonify(json.loads(result["result_json"]))
