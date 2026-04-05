"""
File processing worker.

Polls processing_jobs for pending work. Two job types:
  thumbnail: PIL Image.open → resize to 256x256 max → save as JPEG
  metadata:  os.stat + mimetypes + mutagen (audio/video) → JSON dict

Atomic claim pattern (from job-queue solution doc):
  SELECT id → UPDATE WHERE id AND status='pending' → rowcount check
  Fetch file_id from job row; never by worker_id.

Stale job recovery: reset running→pending for jobs claimed >120s ago.
Max attempts: 3; permanently failed after 3 failures.
"""
import json
import mimetypes
import os
import signal
import sqlite3
import time
import unicodedata
import uuid
import logging
from datetime import datetime, timezone

from PIL import Image
Image.MAX_IMAGE_PIXELS = 50_000_000  # decompression bomb guard (~7000x7000 px)

from db import get_connection, get_file_upload_dir, is_valid_file_id, UPLOAD_DIR

POLL_INTERVAL = max(1, int(os.environ.get("POLL_INTERVAL", "2")))
WORKER_ID = os.environ.get("WORKER_ID") or str(uuid.uuid4())
JOB_TIMEOUT_SECONDS = 120
THUMBNAIL_SIZE = (256, 256)
MAX_ERROR_LEN = 500

logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [worker:{WORKER_ID[:8]}] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

_running = True


def _handle_shutdown(signum, frame):
    global _running
    log.info("Shutdown signal — stopping after current job")
    _running = False


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Processor: thumbnail
# ---------------------------------------------------------------------------
def _process_thumbnail(file_dir: str, file_id: str) -> dict:
    """
    Generate a 256x256 max thumbnail from the original file.
    Returns {"result_path": path} on success.
    Raises exception on failure (non-image, corrupt file, etc.)
    """
    from PIL import UnidentifiedImageError

    # Find original file using validated directory from DB
    original = None
    for fname in os.listdir(file_dir):
        if fname.startswith("original"):
            original = os.path.join(file_dir, fname)
            break
    if original is None:
        raise FileNotFoundError("Original file not found in upload directory")

    with Image.open(original) as img:  # context manager prevents FD leak
        # Convert to RGB before thumbnail — avoids mode issues with palette/RGBA/P modes
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail(THUMBNAIL_SIZE)
        thumb_path = os.path.join(file_dir, "thumbnail.jpg")
        img.save(thumb_path, "JPEG", quality=85)

    log.info("Thumbnail saved: %s", thumb_path)
    return {"result_path": thumb_path}


# ---------------------------------------------------------------------------
# Processor: metadata
# ---------------------------------------------------------------------------
def _process_metadata(file_dir: str, file_id: str, original_filename: str, content_type: str, size_bytes: int) -> dict:
    """
    Extract metadata from the original file.
    Returns {"result_json": json_string} always (never raises on unrecognized type).
    """
    original = None
    for fname in os.listdir(file_dir):
        if fname.startswith("original"):
            original = os.path.join(file_dir, fname)
            break

    meta = {
        "file_id": file_id,
        "original_filename": original_filename,
        "content_type": content_type,
        "size_bytes": size_bytes,
    }

    if original:
        # Guess MIME from extension as fallback
        guessed_type, _ = mimetypes.guess_type(original_filename)
        if guessed_type:
            meta["guessed_content_type"] = guessed_type

        # Try Pillow for image dimensions
        try:
            from PIL import UnidentifiedImageError
            with Image.open(original) as img:
                meta["image"] = {
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "format": img.format,
                }
        except Exception:
            pass

        # Try mutagen for audio/video metadata
        try:
            import mutagen
            audio = mutagen.File(original)
            if audio is not None:
                meta["audio"] = {
                    "duration_seconds": getattr(audio.info, "duration", None),
                    "bitrate": getattr(audio.info, "bitrate", None),
                    "sample_rate": getattr(audio.info, "sample_rate", None),
                    "channels": getattr(audio.info, "channels", None),
                    "tags": {k: str(v) for k, v in (audio.tags or {}).items()},
                }
        except Exception:
            pass

    return {"result_json": json.dumps(meta)}


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------
def _recover_stale_jobs(conn):
    conn.execute(
        """
        UPDATE processing_jobs
        SET status = 'pending', claimed_at = NULL, worker_id = NULL
        WHERE status = 'running'
          AND (strftime('%s', 'now') - strftime('%s', claimed_at)) > ?
        """,
        (JOB_TIMEOUT_SECONDS,),
    )
    conn.commit()


def _update_file_status(conn, file_id: str):
    """
    Update files.status based on aggregate processing_jobs state:
    - done: all jobs completed
    - failed: any job permanently failed (attempt_count >= max_attempts)
    - processing: otherwise
    """
    jobs = conn.execute(
        "SELECT status, attempt_count, max_attempts FROM processing_jobs WHERE file_id = ?",
        (file_id,),
    ).fetchall()

    if not jobs:
        log.warning("_update_file_status: no jobs found for file_id=%s", file_id)
        return

    if any(j["status"] == "failed" and j["attempt_count"] >= j["max_attempts"] for j in jobs):
        new_status = "failed"
    elif all(j["status"] == "completed" for j in jobs):
        new_status = "done"
    else:
        new_status = "processing"

    conn.execute(
        "UPDATE files SET status = ? WHERE id = ?",
        (new_status, file_id),
    )


def _process_one_job() -> bool:
    conn = None
    try:
        conn = get_connection()
        _recover_stale_jobs(conn)

        # Find one pending job
        row = conn.execute(
            """
            SELECT id FROM processing_jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC LIMIT 1
            """
        ).fetchone()
        if row is None:
            return False

        job_id = row["id"]
        now = _now_str()

        # Atomic claim
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as e:
            log.warning("DB locked during claim: %s", e)
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return False

        try:
            cur = conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'running', claimed_at = ?, worker_id = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, WORKER_ID, job_id),
            )
            if cur.rowcount == 0:
                conn.execute("ROLLBACK")
                return False
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

        # Fetch job details
        job = conn.execute(
            """
            SELECT j.id, j.file_id, j.job_type, j.attempt_count, j.max_attempts,
                   f.original_filename, f.content_type, f.size_bytes
            FROM processing_jobs j
            JOIN files f ON f.id = j.file_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()

        if job is None:
            log.warning("Job %d vanished after claim", job_id)
            return True

        file_id = job["file_id"]
        job_type = job["job_type"]
        # Always derive path from validated UUID — never trust raw DB path
        file_dir = get_file_upload_dir(file_id)
        attempt = job["attempt_count"] + 1

        log.info("Processing job %d: type=%s file_id=%s attempt=%d", job_id, job_type, file_id, attempt)

        # Run processor
        result = None
        error_message = None
        try:
            if job_type == "thumbnail":
                result = _process_thumbnail(file_dir, file_id)
            elif job_type == "metadata":
                result = _process_metadata(
                    file_dir, file_id,
                    job["original_filename"], job["content_type"], job["size_bytes"]
                )
        except Exception as e:
            error_message = f"{type(e).__name__}: {str(e)}"[:MAX_ERROR_LEN]
            log.warning("Job %d failed: %s", job_id, error_message)

        completed_at = _now_str()

        if error_message:
            # Retry if attempts remain, else permanently failed
            new_status = "pending" if attempt < job["max_attempts"] else "failed"
            conn.execute(
                """
                UPDATE processing_jobs
                SET status = ?, attempt_count = ?, completed_at = ?,
                    error_message = ?, claimed_at = NULL, worker_id = NULL
                WHERE id = ?
                """,
                (new_status, attempt, completed_at, error_message, job_id),
            )
        else:
            # Success — insert result row
            conn.execute(
                """
                UPDATE processing_jobs
                SET status = 'completed', attempt_count = ?, completed_at = ?
                WHERE id = ?
                """,
                (attempt, completed_at, job_id),
            )
            result_path = result.get("result_path")
            result_json = result.get("result_json")
            conn.execute(
                """
                INSERT OR REPLACE INTO file_results (file_id, result_type, result_path, result_json)
                VALUES (?, ?, ?, ?)
                """,
                (file_id, job_type, result_path, result_json),
            )

        _update_file_status(conn, file_id)
        conn.commit()

        log.info(
            "Job %d %s (attempt=%d, error=%s)",
            job_id, "completed" if not error_message else "failed/retrying",
            attempt, error_message or "none",
        )
        return True

    finally:
        if conn:
            conn.close()


def run():
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)
    log.info("Worker started (id=%s, poll=%ds)", WORKER_ID, POLL_INTERVAL)

    while _running:
        try:
            processed = _process_one_job()
            if not processed:
                for _ in range(POLL_INTERVAL * 10):
                    if not _running:
                        break
                    time.sleep(0.1)
        except Exception as exc:
            log.error("Unhandled error: %s", exc, exc_info=True)
            time.sleep(1)

    log.info("Worker stopped")


if __name__ == "__main__":
    run()
