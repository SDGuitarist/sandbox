## Smoke Test Results

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| GET / | 302 redirect to /bookmarks/ | 302 | PASS |
| GET /bookmarks/ | 200 | 200 | PASS |
| GET /bookmarks/new | 200 | 200 | PASS |
| GET /tags/ | 200 | 200 | PASS |
| POST /bookmarks/new (create with CSRF) | 302 redirect | 302 | PASS |
| GET /bookmarks/ (shows created bookmark) | "Test Bookmark" in response | Found | PASS |
| GET /bookmarks/1 (detail) | 200 | 200 | PASS |
| GET /tags/ (shows created tags) | "test", "example" | Found | PASS |
| GET /bookmarks/?q=test (search) | "Test Bookmark" in response | Found | PASS |
| GET /tags/test (filter by tag) | 200 | 200 | PASS |

STATUS: PASS
