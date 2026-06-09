Read HANDOFF.md. This is Sandbox, the compound-engineering autopilot repo.

Film Production PM spec convergence is COMPLETE on branch feat/film-production-pm
(Codex round folded + human structural-verification gate PASSED, zero P0s). This run is
the validate-on-real-build vehicle for the FROZEN orchestration-hardening branch
(feat/cpaa-event-replay-simulator, Codex GO x3) — it must exercise Tracks A/B/C.

Do this:
1. Confirm prerequisites: cwd is ~/Projects/sandbox AND dangerouslySkipPermissions: true
   is set in .claude/settings.local.json. If not, STOP and tell me — do not proceed.
2. git checkout feat/film-production-pm
3. Run /autopilot — the plan (docs/plans/film-production-pm-plan.md) has swarm: true,
   so it takes the 16-agent swarm path. This is run 070. Run fully unattended; do not
   break the loop between phases.
4. After the run, confirm validate-on-real-build — the reports MUST contain all three:
   - the 9w.6 spec-completeness PASS
   - the advisory spec-eval log (Track C: logs, does not block)
   - a per-worker cherry-pick base in docs/reports/070/assembly-summary.md (Track A)
   A 9w.6 false-FAIL that aborts before Track A = validation INCOMPLETE (re-run, don't
   call it done). Watch-item: GET <int:> routes aren't in Input Validation, but
   RestaurantOps/GigSheet passed 9w.6 with the identical structure — if 9w.6 false-FAILs
   on those, that's a checker bug to log, not a spec defect.
5. Then report whether the hardening branch is cleared to merge to master.
