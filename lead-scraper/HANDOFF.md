# Browser Outreach Sender -- Operational Ramp

**Phase:** Operational (all code phases complete)
**Date:** 2026-05-14
**Plan:** docs/plans/2026-05-08-feat-browser-outreach-sender-plan.md
**Brainstorm:** docs/brainstorms/2026-05-08-browser-outreach-sender-brainstorm.md

## Current State

All 4 implementation phases are complete. The system is operational and has sent 82 messages (May 7-10). Sending has been idle since May 10.

**Database snapshot (May 14):**
- 4,198 total leads, 989 high-quality sendable (verified + quality >= 3)
- 60 approved messages sitting unsent across wave2 campaigns
- 20 needs_review messages awaiting manual triage
- 82 sent, 226 skipped, 1 declined
- 1 sender account ("personal"), 30/day cap, risk acknowledged

**Deadline:** May 30 workshop (16 days). At 30/day with 1 account, max ~480 more sends. Need a second account to reach 1,000.

## Next Action

Resume daily sending operations. Follow the Daily Operational Playbook in the plan (Phase 4c).

## Prompt for New Session

Read docs/plans/2026-05-08-feat-browser-outreach-sender-plan.md (Phase 4c: Daily Operational Playbook).

Resume operational sending. The code is complete. Focus on:
1. Send the 60 approved messages (`campaign send <id> --limit 30` per session)
2. Run quality gate on campaigns with remaining drafts
3. Force-approve or force-skip the 20 needs_review items
4. Generate new drafts for wave2 campaigns with unqueued leads
5. Consider adding a second sender account for throughput

**Critical rules:**
- NEVER run concurrent processes on leads.db
- Always use `--limit` with campaign send (no unlimited sends)
- Watch the headed browser during sends for restriction signals
- If account gets restricted: `account cooldown personal --hours 48`

**Key commands:**
```
python run.py account list                          # check account status
python run.py campaign status <id>                  # campaign metrics
python run.py campaign queue <id> --status approved # see what's ready
python run.py campaign send <id> --limit 30         # send a batch
python run.py campaign gate <id>                    # verify drafts
python run.py campaign queue <id> --status needs_review  # triage
python run.py campaign force-approve <id> --lead <id>    # approve after review
python run.py campaign force-skip <id> --lead <id>       # reject after review
```

## Phase Sequence

- [x] Brainstorm (2 Codex reviews, all blockers fixed)
- [x] Plan (3 Codex reviews, all blockers fixed)
- [x] Work Phase 1: Foundation (May 8)
- [x] Work Phase 2: Minimal Sender + Spike Test (May 8-10, 82 sent)
- [x] Work Phase 3: Quality Gate (May 8)
- [x] Work Phase 4: Full CLI Integration + Ramp (May 8)
- [ ] Review
- [ ] Compound

## Deferred Items

- Add second sender account (needed for 1,000 target by May 30)
- Haiku accuracy audit (plan says: after 50 AI-gated leads, spot-check 10 approved + 10 skipped)
- AUTO_APPROVE_LOGIN_WALLED toggle (currently 0, switch to 1 after confirming <10% error rate on login-walled leads)

## Prior Handoff (Reliability Hardening -- 2026-05-06)

- Inline retry loop, circuit breakers, manual_approved column, 12 new tests
- 8-agent review: 1 P1 + 4 P2 fixed
- Solution doc: docs/solutions/2026-05-06-reliability-hardening.md
