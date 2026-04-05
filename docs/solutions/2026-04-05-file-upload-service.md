---
title: File Upload Service with Processing Pipeline
date: 2026-04-05
tags: [flask, sqlite, file-upload, workers, pillow, mutagen]
module: file_upload_service
lesson: PIL decompression bombs, BLOCKED_EXTENSIONS denylist, and result_path bounds checks are mandatory for any file-serving service — user-uploaded files are hostile input
origin_plan: docs/plans/2026-04-05-file-upload-service-plan.md
origin_brainstorm: docs/brainstorms/2026-04-05-file-upload-service.md
---

# File Upload Service with Processing Pipeline

## Problem

Build a file upload service that accepts files via REST API, queues async processing jobs (thumbnail generation, metadata extraction), and serves the processed results. Files must be stored safely and processing must be resilient to failures.

## Solution

Flask API accepts multipart uploads. Each upload gets a UUID file_id, stored files land in `upload_dir/<uuid>/original<ext>`. Two processing jobs are enqueued per file (thumbnail, metadata). A separate worker process polls the job queue, processes files, and stores results. Results are served via dedicated endpoints.

Key architecture decisions:
- **UUID file IDs** — prevents enumeration; UUID regex in `get_file_upload_dir()` prevents path traversal at the DB layer
- **Worker as separate process** — avoids gunicorn multi-worker duplicate fires
- **Atomic claim**: `SELECT id` → `BEGIN IMMEDIATE` → `UPDATE WHERE id=? AND status='pending'` → rowcount check
- **`claimed_at` timeout anchor** — stale jobs recovered after 120s using `strftime('%s','now') - strftime('%s', claimed_at)`
- **`UNIQUE(file_id, result_type)`** on `file_results` — prevents duplicate result rows on retry

## Why This Approach

- **No background threads** — Flask with gunicorn spawns multiple workers; background threads would fire jobs N times per upload
- **No Redis/Celery** — SQLite WAL mode + BEGIN IMMEDIATE gives sufficient throughput for moderate load without extra infrastructure
- **Per-file directory** — isolates uploads, avoids filename collisions, gives worker a clean working directory

## Risk Resolution

> **Flagged risk:** "PIL thumbnail generation may fail silently or produce wrong output for edge-case image modes (RGBA, palette, 16-bit)"

> **What actually happened:** Review found two PIL issues: (1) decompression bomb protection was completely absent — a crafted image could exhaust memory; (2) mode conversion was done AFTER thumbnail(), which can fail for palette/RGBA modes. Both were P1 fixes.

> **Lesson learned:** `Image.MAX_IMAGE_PIXELS = 50_000_000` must be set at module import time, before any Image.open() call. Convert to RGB/L BEFORE calling thumbnail(), not conditionally after — thumbnail() can fail mid-operation on non-RGB modes.

## Key Decisions

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| Job queue | SQLite processing_jobs | Redis/Celery | Zero extra infra; WAL handles concurrency |
| File storage | UUID dir + original<ext> | flat dir with hash names | Clean per-file isolation, deterministic path |
| Thumbnail format | JPEG 256x256 | WebP, PNG | Universal support; smaller than PNG |
| Worker model | Separate process | Flask background thread | Avoids gunicorn duplicate fires |

## Gotchas

### PIL decompression bomb — set MAX_IMAGE_PIXELS at module top
```python
from PIL import Image
Image.MAX_IMAGE_PIXELS = 50_000_000  # set BEFORE any Image.open()
```
A crafted image with a large declared size triggers a DoS. The guard must be set at import time, not inside the function.

### Convert to RGB before thumbnail(), not after
```python
with Image.open(original) as img:
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")  # BEFORE thumbnail
    img.thumbnail(THUMBNAIL_SIZE)
    img.save(thumb_path, "JPEG", quality=85)
```
Calling `thumbnail()` on a palette-mode image can produce unexpected results. Always convert first.

### PIL context manager prevents file descriptor leaks
```python
with Image.open(original) as img:  # always use context manager
    ...
```

### BLOCKED_EXTENSIONS denylist — required for any file-serving service
```python
BLOCKED_EXTENSIONS = {".php", ".py", ".sh", ".exe", ".htaccess", ...}
if ext in BLOCKED_EXTENSIONS:
    return jsonify({"error": f"file type not allowed: {ext}"}), 422
```
Without this, a server misconfiguration could execute uploaded files.

### result_path bounds check before send_file
```python
def _result_path_is_safe(result_path: str) -> bool:
    real = os.path.realpath(result_path)
    upload_real = os.path.realpath(UPLOAD_DIR)
    return real.startswith(upload_real + os.sep)
```
Even though result_path comes from the DB (worker-written), defense in depth requires verifying it stays within UPLOAD_DIR before calling send_file().

### Stale job SQL — use strftime arithmetic, not string concat
```sql
-- WRONG (string concat, fragile):
WHERE claimed_at <= datetime('now', ? || ' seconds')

-- RIGHT (numeric arithmetic):
WHERE (strftime('%s', 'now') - strftime('%s', claimed_at)) > ?
```

### Metadata endpoint must return 422 on permanent failure, not 202 forever
```python
if result is None:
    job = conn.execute("SELECT status, attempt_count, max_attempts FROM processing_jobs WHERE ...")
    if job and job["status"] == "failed" and job["attempt_count"] >= job["max_attempts"]:
        return jsonify({"error": "metadata extraction failed"}), 422
    return jsonify({"error": "metadata not yet available"}), 202
```

### Filename sanitization — NFKC before secure_filename
```python
name = unicodedata.normalize("NFKC", raw)
name = name.replace("\x00", "")  # strip null bytes
name = name[:MAX_FILENAME_LEN]
name = secure_filename(name)
```
`secure_filename` alone doesn't handle unicode homoglyphs or null bytes.

### Deterministic download path — store file_ext in DB
Store `file_ext` at upload time so the download endpoint uses `original{file_ext}` directly instead of os.listdir(). Eliminates a race condition and TOCTOU risk.

## Feed-Forward

- **Hardest decision:** Whether to use `os.listdir()` for the download path or store the extension — chose to store it to eliminate the race condition and avoid trusting filesystem state
- **Rejected alternatives:** Storing the full file path (too brittle if UPLOAD_DIR moves), using content-type for extension guessing (unreliable for ambiguous types like text/plain)
- **Least confident:** The PIL decompression bomb limit of 50M pixels may be too generous for some deployment contexts — operators should tune based on expected image sizes
