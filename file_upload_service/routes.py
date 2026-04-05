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
import unicodedata

from flask import Blueprint, request, jsonify, send_file, abort, url_for
from werkzeug.utils import secure_filename

from db import get_connection, generate_file_id, get_file_upload_dir, is_valid_file_id, UPLOAD_DIR

bp = Blueprint("file_upload", __name__)

MAX_FILENAME_LEN = 255

# Extensions that must never be stored/executed on the server
BLOCKED_EXTENSIONS = {
    ".php", ".php3", ".php4", ".php5", ".phtml",
    ".py", ".pyc", ".pyo",
    ".rb", ".pl", ".cgi",
    ".sh", ".bash", ".zsh", ".fish",
    ".exe", ".dll", ".so", ".dylib",
    ".js", ".jsx", ".ts", ".tsx",  # server-side script risk
    ".htaccess", ".htpasswd",
}


def _validate_file_id(file_id: str):
    """Return 400 response if file_id is not a valid UUID."""
    if not is_valid_file_id(file_id):
        abort(400, description="Invalid file ID format")


def _sanitize_filename(raw: str) -> str:
    """
    NFKC-normalize, strip null bytes, enforce length, then secure_filename.
    Returns 'upload' if result is empty.
    """
    # NFKC normalization prevents unicode homoglyph tricks
    name = unicodedata.normalize("NFKC", raw)
    # Strip null bytes
    name = name.replace("\x00", "")
    # Truncate before secure_filename (which may further shorten it)
    name = name[:MAX_FILENAME_LEN]
    name = secure_filename(name)
    return name if name else "upload"


def _result_path_is_safe(result_path: str) -> bool:
    """Verify result_path is within UPLOAD_DIR before serving."""
    try:
        real = os.path.realpath(result_path)
        upload_real = os.path.realpath(UPLOAD_DIR)
        return real.startswith(upload_real + os.sep) or real == upload_real
    except Exception:
        return False


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
    original_filename = _sanitize_filename(f.filename)

    # Determine content type and extension
    content_type = f.content_type or "application/octet-stream"
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower() if ext else ""

    # Reject blocked extensions
    if ext in BLOCKED_EXTENSIONS:
        return jsonify({"error": f"file type not allowed: {ext}"}), 422

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
            INSERT INTO files (id, original_filename, content_type, size_bytes, file_ext, upload_dir_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_id, original_filename, content_type, size_bytes, save_ext, file_dir),
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

    response = jsonify({
        "file_id": file_id,
        "original_filename": original_filename,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "status": "uploaded",
    })
    response.status_code = 202
    response.headers["Location"] = url_for("file_upload.get_file", file_id=file_id)
    return response


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
            "SELECT original_filename, content_type, file_ext, upload_dir_path FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    # Deterministic path using stored extension — no os.listdir needed
    file_dir = get_file_upload_dir(file_id)
    file_path = os.path.join(file_dir, f"original{row['file_ext']}")

    if not os.path.exists(file_path):
        return jsonify({"error": "file not found on disk"}), 404

    return send_file(
        file_path,
        download_name=row["original_filename"],
        as_attachment=True,
    )


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
    if not thumb_path or not _result_path_is_safe(thumb_path):
        return jsonify({"error": "thumbnail path invalid"}), 500
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
            # Check if job permanently failed
            job = conn.execute(
                "SELECT status, attempt_count, max_attempts FROM processing_jobs WHERE file_id = ? AND job_type = 'metadata'",
                (file_id,),
            ).fetchone()
            if job and job["status"] == "failed" and job["attempt_count"] >= job["max_attempts"]:
                return jsonify({"error": "metadata extraction failed"}), 422
            return jsonify({"error": "metadata not yet available", "status": "processing"}), 202

    try:
        return jsonify(json.loads(result["result_json"]))
    except (json.JSONDecodeError, TypeError):
        return jsonify({"error": "metadata corrupted"}), 500
