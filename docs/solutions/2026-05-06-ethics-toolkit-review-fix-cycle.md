---
title: "Ethics Toolkit -- Review Fix Cycle (P0 + P1 x2)"
date: 2026-05-06
tags: [swarm, review-fix-cycle, rls-hardening, atomic-rpc, ai-route-factory, hmac-security, channel-consolidation, idempotent-migrations]
status: resolved
companion_to: docs/solutions/2026-04-30-ethics-toolkit-platform-build.md
fix_commits:
  - { hash: 524bfe2, scope: p0, files: 17, net: "+261" }
  - { hash: 5a95867, scope: p1-round-1, files: 12, net: "+157" }
  - { hash: 2476db0, scope: p1-round-2, files: 16, net: "-273" }
---

# Ethics Toolkit -- Review Fix Cycle

Companion doc to the [15-agent swarm build](2026-04-30-ethics-toolkit-platform-build.md). This doc covers the 3 rounds of review fixes that resolved all P0/P1 items deferred in the original build.

## Summary

28 issues fixed across 3 commits. 45 file changes, 1,026 insertions, 881 deletions (net +145). The P1 R2 commit is net -273 lines thanks to the AI route factory eliminating ~390 lines of duplicated boilerplate.

## Round 1: P0 Fixes (524bfe2)

12 issues. Every failure was at an integration seam between agents, not within any single agent's work.

| Category | Issue | Fix |
|----------|-------|-----|
| Import mismatches (13 files) | `createClient` vs `createBrowserClient`, `ensureAnonymousSession` vs `getOrCreateAnonymousSessionId` | Alias exports: `export { createClient as createBrowserClient }` -- 3 lines across 3 files |
| Dead wiring (3 functions) | `scheduleTrialEmails`, `registerServiceWorker`, `withAiRateLimit` never imported | Wired into save-results route, attendee layout, AI routes |
| Race conditions (2 routes) | Upvote read-then-write, session claiming as 2 separate calls | PostgreSQL RPCs: `increment_upvote` (atomic UPDATE...RETURNING), `claim_anonymous_session` (PL/pgSQL transaction) |
| Missing timeouts | Bare Anthropic API calls could hang indefinitely | 15s AbortController on all 3 AI routes, mock fallback on abort |
| Channel kill bug | Child `channel.unsubscribe()` killed parent's shared channel | Removed child unsubscribe; parent owns lifecycle |
| Email timeout | 60s retry sleep exceeded Vercel function limit | Reduced to 5s |
| Session validation | save-results route accepted any session ID | Added ownership check: verify tool_events exist for claimed session |

**Key lesson**: Alias exports (`export { X as Y }`) are the cheapest cross-agent fix. O(1) source changes vs O(n) consumer updates.

## Round 2: P1 Security & Data Integrity (5a95867)

12 issues covering RLS, token security, FK cascades, and data quality.

| Category | Issue | Fix |
|----------|-------|-----|
| RLS too permissive | `USING(true)` on tool_events let any anon user read ALL events | Dropped anon SELECT policy; reads go through API routes with service role |
| Unsigned tokens | `Buffer.from(userId).toString('base64url')` -- trivially forgeable | HMAC-SHA256 signed tokens with `crypto.timingSafeEqual` verification |
| Missing FK cascades | 8 FKs with no ON DELETE -- 30-day cleanup would fail | Added CASCADE/SET NULL via ALTER TABLE DROP/ADD CONSTRAINT |
| Cron concurrency | Overlapping cron invocations could double-send emails | Atomic claim: `UPDATE email_jobs SET status='processing' WHERE status='pending'` |
| No login rate limit | Facilitator login endpoint brute-forceable | Added `checkDefaultRateLimit` |
| Mock shape mismatch | Budget mock returned `string`, consumers expected `{ ethicalAnalysis: string }` | Fixed mock return type to match schema |
| Non-idempotent seed | Festival policies INSERT failed on re-run | `ON CONFLICT (festival_name, year) DO NOTHING` |
| Duplicate enum | `ToolType` in both constants.ts and schemas/tool-event.ts | Removed duplicate, canonical source is schemas |
| Inconsistent session | Some pages used memory-only session, others DB-persisted | All tool pages standardized to `ensureAnonymousSession` |

**Key lesson**: RLS must be reviewed against actual data access patterns, not the schema. When the API layer already filters by user, RLS should be restrictive (service-role only), not permissive.

## Round 3: P1 Architecture & DRY (2476db0)

4 larger refactors addressing structural issues.

| Category | Issue | Fix |
|----------|-------|-----|
| Non-idempotent DDL | 14 CREATE TABLE + 4 CREATE INDEX without IF NOT EXISTS | Added IF NOT EXISTS to all statements |
| Validation boundary | Tool routes had inconsistent request shapes | Standardized to `{ input: ToolInput, eventId, anonymousSessionId }` |
| Channel proliferation | 5 dashboard widgets each creating own Realtime channel | `useWorkshopChannel` hook: 1 channel at page level, passed as props |
| Route duplication | 3 AI routes x ~150 identical lines | `createAiRouteHandler(config)` factory: each route ~20 lines of config |

**Key lesson**: Route factories eliminate cross-route drift by construction. When the P0 timeout fix had to be applied to 3 identical routes, it took 3 manual edits. With the factory, it's 1 edit.

## Reusable Code Patterns

### AI Route Factory

```typescript
// lib/ai/route-factory.ts
interface AiRouteConfig {
  inputSchema: ZodType;
  outputSchema: ZodType;
  model: string;
  maxTokens: number;
  systemPrompt: string;
  buildUserMessage: (input: unknown) => string;
  getMock: () => Promise<unknown>;
  routeLabel: string;
}
export function createAiRouteHandler(config: AiRouteConfig) {
  return async function POST(request: NextRequest) { ... };
}

// Each route becomes:
export const POST = createAiRouteHandler({
  inputSchema: BudgetInput,
  outputSchema: BudgetAI,
  model: MODELS.SONNET,
  maxTokens: 1024,
  routeLabel: '/api/ai/budget',
  systemPrompt: '...',
  buildUserMessage: (input) => JSON.stringify(input),
  getMock: getMockBudgetAI,
});
```

### Shared Realtime Channel Hook

```typescript
// lib/realtime/use-workshop-channel.ts
export function useWorkshopChannel(sessionId: string | null) {
  const [connected, setConnected] = useState(false);
  const channelRef = useRef<RealtimeChannel | null>(null);
  useEffect(() => {
    if (!sessionId) return;
    const supabase = createClient();
    const channel = supabase.channel(`workshop:${sessionId}`);
    channelRef.current = channel;
    channel.subscribe((status) => setConnected(status === "SUBSCRIBED"));
    return () => { supabase.removeChannel(channel); };
  }, [sessionId]);
  return { channel: channelRef.current, connected };
}
```

Page creates 1 channel, passes `channel` + `connected` as props. Children call `channel.on()` but never `subscribe()`/`unsubscribe()`.

### HMAC Unsubscribe Token

```typescript
export function generateUnsubscribeToken(userId: string): string {
  const payload = Buffer.from(userId).toString('base64url');
  const sig = crypto.createHmac('sha256', secret).update(userId).digest('base64url');
  return `${payload}.${sig}`;
}
export function verifyUnsubscribeToken(token: string): string | null {
  const [payload, sig] = token.split('.');
  const userId = Buffer.from(payload, 'base64url').toString('utf-8');
  const expected = crypto.createHmac('sha256', secret).update(userId).digest('base64url');
  if (!crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) return null;
  return userId;
}
```

### Atomic Cron Claim

```typescript
const { data: claimed } = await supabase
  .from('email_jobs')
  .update({ status: 'processing' })
  .eq('id', job.id)
  .eq('status', 'pending')
  .select('id')
  .single();
if (!claimed) continue; // Another worker got it
```

## Failure Classes Hit

| agent-pitfalls.md Class | Manifestation |
|-------------------------|---------------|
| FC1: Naming Divergence | 13 import mismatches across agent boundaries |
| FC3: Dead Wiring | 3 functions built but never called (ownership boundary) |
| FC4: Validation Gap | RLS `USING(true)` -- nobody owned anonymous access restriction |
| FC5: Swarm Consistency | 5 widgets independently creating channels; 3 routes with identical code |
| FC6: Non-Transactional | Upvote read-then-write, session claiming as 2 separate calls |

## Prevention: Top 4 by ROI

1. **Export Name Registry in spec** + `tsc --noEmit` at gate -- catches 12/28 issues (all import mismatches)
2. **Atomicity annotations** on every mutation -- catches the 2 scariest bugs (race conditions)
3. **Route uniqueness list** + collision gate check -- prevents largest code waste (3x150 lines)
4. **One-sentence idempotency rule** in spec template -- trivial effort, eliminates an entire P1 class

These 4 preventions would have caught 20 of 28 issues with <1 hour of additional spec work.

## Related Docs

- [Ethics Toolkit Swarm Build](2026-04-30-ethics-toolkit-platform-build.md) -- the build this fix cycle resolves
- [Spec Convergence Loop](2026-04-30-spec-convergence-loop.md) -- upstream spec hardening that reduced fix cycle scope
- [WRC Swarm Build](2026-05-03-writers-room-council-swarm-build.md) -- parallel case study with identical failure classes
- [Tunestamp Power Features](../../tunestamp/docs/solutions/2026-05-06-power-features-swarm-build.md) -- RLS enumeration + integration wiring gap
- [Lead Scraper Cascade Fixes](../../lead-scraper/docs/solutions/2026-04-21-v2-review-cascade-fixes.md) -- fix ordering pattern (zero-risk first)

## Remaining Deferred Items

**P2 (15 items):** `as any` casts, security headers, quote style, button styling, LIKE wildcard escaping, Service Worker cache expiry, TypeScript nullability gaps. Low severity individually but compound risk if codebase grows.

**Operational:** Pre-workshop load test, iPhone Safari + Android Chrome testing, projector setup. Square webhook automation, behavior-triggered email, festival auto-scraping.

## Feed-Forward

- **Hardest decision:** AI route factory extraction -- balancing DRY with readability for routes that share rate-limiting, timeout, preflight, mock fallback, and Zod validation
- **Rejected alternatives:** Fixing all P1s in a single monolithic commit (chose 2 rounds to keep each reviewable and bisectable)
- **Least confident:** P2 items still deferred -- especially `as any` casts and missing security headers. Low severity individually but compound risk if the codebase grows before cleanup
- **Resolved from prior:** RLS `USING(true)` on tool_events and unsigned unsubscribe tokens -- the two items flagged as "least confident" in the original build doc -- are now fixed
