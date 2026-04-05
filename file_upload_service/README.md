# File Upload Service with Processing Pipeline

A Flask + SQLite file upload service. Upload files via API, async processing workers generate thumbnails (images) and extract metadata (all files), serve processed results.

## How It Works

1. **Flask API** — `POST /files` accepts multipart uploads, returns file_id (UUID)
2. **worker.py** — polls processing_jobs queue, generates thumbnails (Pillow) and extracts metadata (mutagen + Pillow)
3. **SQLite** — files + processing_jobs + file_results tables, WAL mode

## Setup

```bash
pip install flask pillow mutagen
cd file_upload_service
python db.py    # creates uploads.db and upload_dir/
```

## Start

```bash
# Terminal 1 — Flask API
python app.py        # http://localhost:5007

# Terminal 2 — Worker
python worker.py
```

## API

### Upload a file

```bash
curl -X POST http://localhost:5007/files \
  -F "file=@photo.jpg"
# Returns: {"file_id": "uuid", "status": "uploaded", ...}
```

### Check processing status

```bash
curl http://localhost:5007/files/<file_id>
# Returns: file metadata + processing_jobs with status per type
```

### Get thumbnail (images only)

```bash
curl http://localhost:5007/files/<file_id>/thumbnail -o thumb.jpg
```

### Get extracted metadata

```bash
curl http://localhost:5007/files/<file_id>/metadata
```

### Download original file

```bash
curl -O http://localhost:5007/files/<file_id>/download
```

### List all files

```bash
curl http://localhost:5007/files
```

## Processing jobs

Each upload creates 2 processing jobs:

| Job type | What it does | Supported files |
|----------|-------------|-----------------|
| `thumbnail` | 256×256 JPEG thumbnail | JPEG, PNG, GIF, WebP, BMP |
| `metadata` | Size, type, dimensions, audio info | All files |

Non-image files will have `thumbnail` job marked `failed` after 3 attempts — this is expected. `metadata` always completes.

## File status transitions

`uploaded` → `processing` → `done` (all jobs completed)  
`uploaded` → `processing` → `failed` (any job permanently failed after 3 retries)

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UPLOAD_DB` | `./uploads.db` | SQLite database path |
| `UPLOAD_DIR` | `./upload_dir/` | File storage directory |
| `POLL_INTERVAL` | `2` | Worker poll interval (seconds) |
| `WORKER_ID` | random UUID | Worker identifier |
