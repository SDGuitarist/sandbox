# Review Context — Service Mesh Dashboard

## Risk Chain

**Brainstorm risk:** "SSRF DNS rebinding gap — register with public DNS that later resolves to 127.0.0.1 after validation. Document the gap; use allow_redirects=False in worker as second defense line."

**Plan mitigation:** Two-layer SSRF: IP check at registration + allow_redirects=False in worker. Verify-first test confirms both layers. DNS rebinding documented in ssrf.py module docstring.

**Work risk (from Feed-Forward):** Events FK semantics — whether to CASCADE or SET NULL when a service is deleted.

**Review resolution:** 1 P1 + 3 P2 + 3 P3. Key fixes: P1-001 (events table missing FK — added ON DELETE SET NULL, not CASCADE), P2-002 (auth middleware needs immediate=True to close TOCTOU on key validation), P2-003 (3xx should be degraded not healthy with allow_redirects=False), P2-004 (complete_job needs AND status='running' guard). All fixed.

Discovered during P1 fix: ON DELETE CASCADE (as suggested by reviewer) deletes the service.deleted audit event itself. Changed to ON DELETE SET NULL to preserve audit records.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| dashboard/schema.sql | events.service_id changed to ON DELETE SET NULL | FK cascade semantics |
| dashboard/auth.py | immediate=True added to get_db call | TOCTOU on key validation |
| dashboard/worker.py | 3xx threshold changed to < 300 | Health status classification |
| dashboard/jobs.py | complete_job guard AND status='running' added | Double-complete prevention |
| dashboard/ssrf.py | is_link_local check moved before is_private | SSRF check ordering |

## Plan Reference

`docs/plans/2026-04-05-feat-service-mesh-dashboard-plan.md`
