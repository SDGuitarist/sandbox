---
title: "File Upload Service with Processing Pipeline"
type: feat
status: active
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-file-upload-service.md
feed_forward:
  risk: "Path traversal security in the file serving endpoint — serving files from disk based on user-supplied IDs requires careful path validation to prevent directory traversal attacks."
  verify_first: true
---

# feat: File Upload Service with Processing Pipeline

## Enhancement Summary

**Deepened on:** 2026-04-05
**Research agents used:** solution-doc-searcher (job-queue atomics, url-health-monitor worker pattern)

### Key Corrections From Research
- Atomic claim: SELECT id → UPDATE WHERE id AND status='pending' → rowcount check (not worker_id fetch)
- Use `claimed_at` as timeout anchor for stale worker detection
- Per-item try/except with continue in worker loop (one bad job doesn't kill loop)
- WAL + busy_timeout=5000ms on every connection
- Path traversal: use `os.path.basename(secure_filename(f.filename))` + serve only from known `upload_dir/<uuid>/` paths

## What Must Not Change

- All existing projects in /workspace — no modifications
- `file_upload_service/` must be self-contained with its own SQLite DB and upload directory
- Atomic claim pattern must not be simplified away
- File IDs must be UUIDs (not sequential integers) to prevent enumeration

## Prior Phase Risk

> "Path traversal security in the file serving endpoint — serving files from disk based on user-supplied IDs requires careful path validation to prevent directory traversal attacks."

**Response:** File IDs are UUIDs (v4) generated server-side — never from user input. File serving uses only the DB-validated `file_id` to construct the path: `os.path.join(UPLOAD_DIR, file_id, 'original.<ext>')`. No user-supplied path components. `werkzeug.utils.secure_filename` applied to original filename before storage (metadata only — not used in path construction). Validated in Phase 1 before any other code.

## Smallest Safe Plan

### Phase 1: Schema + DB layer + security validation
**Files:** `file_upload_service/schema.sql`, `file_upload_service/db.py`
**Shape:**
- `files`: id (UUID TEXT PK), original_filename (sanitized display name), content_type, size_bytes, upload_dir_path, status (uploaded/processing/done/failed), created_at
- `processing_jobs`: id (INTEGER PK), file_id (FK), job_type (thumbnail/metadata), status (pending/running/completed/failed), created_at, claimed_at, worker_id, completed_at, error_message
- `file_results`: id INTEGER PK, file_id FK, result_type (thumbnail/metadata), result_path (for thumbnail) or result_json (for metadata), created_at
- db.py: WAL + busy_timeout; init_db; generate_file_id() → uuid.uuid4()
- Path safety helper: `safe_file_path(file_id, filename)` — validates file_id matches UUID pattern before constructing path
**Gate:** DB initializes; safe_file_path rejects non-UUID inputs

### Phase 2: Upload API
**Files:** `file_upload_service/app.py`, `file_upload_service/routes.py`
**Shape:**
- `POST /files` — multipart upload; `secure_filename` on original_filename; generate UUID file_id; save to `upload_dir/<file_id>/original.<sanitized_ext>`; insert files row; insert 2 processing_jobs rows (thumbnail + metadata); return 202 with file_id and status
- `GET /files/<file_id>` — return file metadata + processing_jobs status
- `GET /files/<file_id>/download` — serve original file (path from DB, not user input)
- `GET /files/<file_id>/thumbnail` — serve thumbnail if processing_jobs[thumbnail]=completed
- `GET /files/<file_id>/metadata` — return extracted metadata JSON
- `GET /files` — list all files
**Gate:** Upload returns 202; non-image upload still accepted (thumbnail job will fail gracefully); invalid file_id returns 404

### Phase 3: Worker process
**Files:** `file_upload_service/worker.py`
**Shape:**
- Poll every 2 seconds for pending processing_jobs
- Atomic claim via UPDATE WHERE id=? AND status='pending' → rowcount check
- Dispatch to processor based on job_type:
  - `thumbnail`: PIL Image.open → thumbnail(256,256) → save as JPEG to `upload_dir/<file_id>/thumbnail.jpg` → insert file_results row
  - `metadata`: os.stat + mimetypes.guess_type + mutagen (if audio/video) → JSON dict → insert file_results row with result_json
- Update files.status to 'done' when both jobs completed; 'failed' if any job permanently fails
- Timeout recovery: reset running→pending for jobs claimed >120s ago
- Max retries: 3; on 3rd failure mark job permanently failed
**Gate:** Upload an image → worker generates thumbnail.jpg → GET /thumbnail returns the image

### Phase 4: Wire up + README
**Files:** `file_upload_service/requirements.txt`, `file_upload_service/README.md`
**Gate:** Fresh checkout can upload, process, and retrieve results

## Rejected Options

- **Synchronous processing:** Timeout/blocking risk; no retry on failure
- **Celery/Redis:** Heavy dependencies; fights our SQLite schema
- **Single job per file:** Can't track thumbnail vs metadata independently; can't retry one without re-running the other

## Risks And Unknowns

1. **Pillow can't thumbnail non-images:** Must catch `UnidentifiedImageError` and mark job failed gracefully
2. **mutagen can't parse all files:** Returns None for unrecognized types — handle None gracefully
3. **Large file upload:** Flask's `MAX_CONTENT_LENGTH` (16 MB) is enforced before our code runs — OK
4. **Disk space:** No cleanup/quota. Acceptable for this scope.
5. **Content-type spoofing:** User can claim `image/jpeg` for any file. Worker opens the actual file bytes — Pillow handles non-images gracefully with an exception.

## Most Likely Way This Plan Is Wrong

The `files.status` aggregation logic: "done when both jobs completed, failed if any permanently fails." If we query `processing_jobs WHERE file_id=?` to check aggregate status, we need to handle: (1) only one job exists (e.g., non-image skips thumbnail), (2) partial completion. Exact rule: `done` when all non-failed jobs are completed; `failed` when ANY job has reached max_retries and is marked permanently failed.

## Scope Creep Check

All items traced to brainstorm. UUID file IDs added (security, not in brainstorm — justified). README added. No scope creep.

## Acceptance Criteria

- `POST /files` with multipart image returns 202 with file_id (UUID format)
- `POST /files` with no file returns 400
- `GET /files/<file_id>` returns file metadata with processing_jobs array
- `GET /files/<file_id>/thumbnail` returns JPEG after worker runs (image uploads)
- `GET /files/<file_id>/thumbnail` returns 404 or 422 for non-image uploads
- `GET /files/<file_id>/metadata` returns JSON dict with at least size_bytes and content_type
- `GET /files/<unknown_id>` returns 404
- Path traversal attempt (e.g., file_id=`../../etc/passwd`) returns 400

## Tests Or Checks

```bash
cd file_upload_service
python -c "from db import init_db; init_db()"
flask run --port 5007 &

# Upload an image
curl -s -X POST http://localhost:5007/files \
  -F "file=@/path/to/test.jpg" | python -m json.tool

# Check status
curl -s http://localhost:5007/files/<file_id> | python -m json.tool

# Start worker
python worker.py &
sleep 3

# Get thumbnail
curl -s http://localhost:5007/files/<file_id>/thumbnail -o thumb.jpg
file thumb.jpg  # should be JPEG

# Get metadata
curl -s http://localhost:5007/files/<file_id>/metadata | python -m json.tool
```

## Rollback Plan

All code in `file_upload_service/`. `rm -rf file_upload_service/` removes everything. No modifications to existing projects.

## Claude Code Handoff Prompt

```text
Read docs/plans/2026-04-05-feat-file-upload-service-plan.md.

PREREQUISITE: File serving uses UUID-based paths from DB only — never user-supplied path components.

Files in scope:
- file_upload_service/schema.sql
- file_upload_service/db.py
- file_upload_service/app.py
- file_upload_service/routes.py
- file_upload_service/worker.py
- file_upload_service/requirements.txt
- file_upload_service/README.md

Scope boundaries: DO NOT modify any files outside file_upload_service/

Acceptance criteria:
- POST /files returns 202 with UUID file_id
- GET /files/<id>/thumbnail returns JPEG after worker processes image
- GET /files/<id>/metadata returns JSON dict
- Path traversal attempt returns 400
```

## Sources

- Brainstorm: docs/brainstorms/2026-04-05-file-upload-service.md

## Feed-Forward

- **Hardest decision:** One processing_jobs row per processor type (not per file). Independent retry and status tracking per job type justifies the extra rows.
- **Rejected alternatives:** Synchronous processing, Celery, single job per file
- **Least confident:** `files.status` aggregation when one job type permanently fails — exact rule for when to mark whole file as 'failed' vs 'partial'.
