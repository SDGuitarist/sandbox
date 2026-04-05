---
title: "File Upload Service with Processing Pipeline"
date: 2026-04-05
status: complete
origin: "autopilot run"
---

# File Upload Service with Processing Pipeline — Brainstorm

## Problem
Developers need a service that accepts file uploads via API, runs asynchronous processing jobs (thumbnail generation for images, metadata extraction for any file type), and serves processed results. Without this, clients must handle all processing synchronously or manage their own worker infrastructure.

## Context
- Flask + SQLite stack
- Pillow available for thumbnail generation (images: JPEG, PNG, GIF, WebP)
- mutagen available for audio/video metadata extraction
- Prior art: job-queue (atomic worker claim), task-scheduler (scheduler process), url-health-monitor (worker process pattern)
- Processing is CPU/IO-bound — must be async, not inline with upload
- Files stored on disk (local filesystem); DB stores metadata only

## Options

### Option A: Upload → job queue → worker processes (recommended)
- Upload endpoint stores file to disk and inserts a `files` record + `processing_jobs` record
- Worker process polls `processing_jobs` for pending jobs, claims atomically, runs processor, stores results
- Flask serves results via `GET /files/<id>` and `GET /files/<id>/thumbnail`
- **Pros:** Clean separation, proven pattern from prior projects, async processing
- **Cons:** File must exist on disk when worker runs; worker and Flask must share same filesystem

### Option B: Synchronous processing in upload endpoint
- Upload, process, return results in one request
- **Pros:** Simpler code, immediate results
- **Cons:** Timeout risk for large files, blocks Flask workers, no retry on failure

### Option C: Celery + Redis for job queue
- **Pros:** Battle-tested, distributed
- **Cons:** Heavy dependencies, fights with our SQLite schema, out of scope for this project

## Decision
**Option A.** Same job-queue-backed worker pattern used in url-health-monitor and task-scheduler. New pieces: multipart file upload handling in Flask, secure filename sanitization, filesystem storage layout, and the two processor types (thumbnail, metadata).

## Open Questions
1. What file types get thumbnails? Images (JPEG, PNG, GIF, WebP, BMP) via Pillow.
2. What file types get metadata? All via Python standard library (mimetypes, os.stat) + mutagen for audio/video.
3. Max upload size? 16 MB (configurable via MAX_CONTENT_LENGTH).
4. Where are files stored? `upload_dir/` subdirectory of the project, organized as `upload_dir/<file_id>/original.<ext>` and `upload_dir/<file_id>/thumbnail.jpg`.
5. Should thumbnails be fixed size? Yes: 256x256 max, aspect-ratio-preserving.

## Feed-Forward
- **Hardest decision:** Whether to use one processing_jobs row per file or one per processor type (thumbnail + metadata = 2 rows per file). Decision: one row per processor type — allows independent retry and status tracking per job.
- **Rejected alternatives:** Synchronous processing (timeout/blocking risk), Celery (heavy deps), single job per file (can't track thumbnail vs metadata independently).
- **Least confident:** Path traversal security in the file serving endpoint — serving files from disk based on user-supplied IDs requires careful path validation to prevent directory traversal attacks.
