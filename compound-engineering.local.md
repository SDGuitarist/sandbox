# Review Context — File Upload Service

## Risk Chain

**Brainstorm risk:** PIL thumbnail generation may fail silently or produce wrong output for edge-case image modes (RGBA, palette, 16-bit)

**Plan mitigation:** Plan specified mode conversion before thumbnail and context manager usage

**Work risk (from Feed-Forward):** PIL mode edge cases for non-RGB images

**Review resolution:** Review found 2 P1 PIL issues (decompression bomb + mode order), 8 P2 issues (blocked extensions, bounds check, stale SQL, metadata 202-forever, etc.). All fixed before commit.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| worker.py | PIL guard, RGB-before-thumbnail, stale SQL fix, get_file_upload_dir() | Image processing, stale job recovery |
| routes.py | BLOCKED_EXTENSIONS, NFKC sanitization, deterministic download, metadata 422 | File upload security, path traversal |
| schema.sql | file_ext column, UNIQUE(file_id, result_type) | Schema integrity |

## Plan Reference

`docs/plans/2026-04-05-file-upload-service-plan.md`
