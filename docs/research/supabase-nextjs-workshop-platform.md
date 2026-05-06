# Supabase + Next.js Workshop Platform: Research Findings

> Researched 2026-04-30. For a workshop platform where 30+ attendees connect via QR code, interact in real-time, and optionally convert to authenticated users via magic link.

---

## Table of Contents

1. [Supabase Auth: Magic Link Flow in Next.js App Router](#1-supabase-auth-magic-link-flow-in-nextjs-app-router)
2. [Supabase Realtime Best Practices](#2-supabase-realtime-best-practices)
3. [RLS Patterns for Anonymous Users with Session IDs](#3-rls-patterns-for-anonymous-users-with-session-ids)
4. [Connection Limits: Free vs Pro Tier](#4-connection-limits-free-vs-pro-tier)
5. [Service Worker + Supabase: Offline-First Caching](#5-service-worker--supabase-offline-first-caching)
6. [Workshop-Specific Architecture Recommendations](#6-workshop-specific-architecture-recommendations)

---

## 1. Supabase Auth: Magic Link Flow in Next.js App Router

### Package: `@supabase/ssr` (not `@supabase/auth-helpers-nextjs`)

The older `@supabase/auth-helpers-nextjs` package is **deprecated**. All new projects must use `@supabase/ssr`, which fully supports Next.js App Router (Server Components, Route Handlers, middleware).

### Three Client Types

You need three separate Supabase client factories:

**Browser Client** (`utils/supabase/client.ts`):

```typescript
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
```

**Server Client** (`utils/supabase/server.ts`):

```typescript
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {
            // setAll can be called from a Server Component where
            // cookies can't be set -- this is safe to ignore
          }
        },
      },
    }
  )
}
```

**Middleware Client** (`utils/supabase/middleware.ts`):

```typescript
import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // IMPORTANT: Do NOT use getSession() -- it reads from cookies
  // which can be spoofed. getUser() sends a request to the Supabase
  // Auth server every time to revalidate the token.
  const { data: { user } } = await supabase.auth.getUser()

  // Optional: redirect unauthenticated users away from protected routes
  if (!user && request.nextUrl.pathname.startsWith('/dashboard')) {
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  return supabaseResponse
}
```

**Root middleware** (`middleware.ts`):

```typescript
import { type NextRequest } from 'next/server'
import { updateSession } from '@/utils/supabase/middleware'

export async function middleware(request: NextRequest) {
  return await updateSession(request)
}

export const config = {
  matcher: [
    // Match all routes except static files and _next internals
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
```

### Why Middleware Is Required

Server Components **cannot write cookies**. When a Supabase auth token expires, the client library refreshes it -- but this refresh needs to be written back to cookies. The middleware intercepts every request, calls `supabase.auth.getUser()` (which triggers the refresh if needed), and writes the new tokens to both the request (for downstream Server Components) and the response (for the browser).

### Magic Link Sign-In Flow

**Step 1: Send magic link** (Server Action or Route Handler):

```typescript
// app/login/actions.ts
'use server'

import { createClient } from '@/utils/supabase/server'

export async function signInWithMagicLink(formData: FormData) {
  const supabase = await createClient()
  const email = formData.get('email') as string

  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
    },
  })

  if (error) {
    return { error: error.message }
  }

  return { success: true }
}
```

**Step 2: Auth callback route** (`app/auth/callback/route.ts`):

```typescript
import { createClient } from '@/utils/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'

  if (code) {
    const supabase = await createClient()
    const { error } = await supabase.auth.exchangeCodeForSession(code)

    if (!error) {
      // Redirect to the intended page after successful auth
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  // If code exchange fails, redirect to an error page
  return NextResponse.redirect(`${origin}/auth/auth-code-error`)
}
```

### Anonymous-to-Authenticated Upgrade Pattern

This is the most relevant pattern for the workshop platform. Attendees start anonymous, then optionally upgrade.

**Step 1: Enable anonymous sign-ins** in Supabase Dashboard:
- Go to Authentication > Settings > User sign ups
- Toggle "Allow anonymous sign-ins" ON

**Step 2: Sign in anonymously on QR code scan**:

```typescript
// Called when attendee scans QR code and lands on workshop page
async function joinWorkshopAnonymously(workshopId: string) {
  const supabase = createClient()

  // This creates an anonymous user with a real user ID and JWT
  const { data, error } = await supabase.auth.signInAnonymously({
    options: {
      data: {
        workshop_id: workshopId,
        display_name: `Attendee-${Math.random().toString(36).slice(2, 6)}`,
      },
    },
  })

  // data.user.id is a real UUID -- use it for RLS
  // data.session contains access_token with is_anonymous: true claim
  return data
}
```

**Step 3: Upgrade anonymous user to permanent** (via magic link):

```typescript
// Option A: updateUser -- links email directly, sends confirmation
async function upgradeWithEmail(email: string) {
  const supabase = createClient()

  const { data, error } = await supabase.auth.updateUser({
    email,
  })
  // Supabase sends a confirmation email
  // After confirming, is_anonymous becomes false
  // The same user ID is preserved -- all data stays linked
}

// Option B: linkIdentity -- for OAuth providers
async function upgradeWithOAuth(provider: 'google' | 'github') {
  const supabase = createClient()

  const { data, error } = await supabase.auth.linkIdentity({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  })
}
```

### Critical Security Rule

**Always use `supabase.auth.getUser()`, never `supabase.auth.getSession()`** for protecting pages or data. `getSession()` reads from cookies which can be spoofed by the client. `getUser()` validates the token against the Supabase Auth server.

### Route Prefetching Pitfall

When Next.js prefetches routes (via `<Link>` components), the server-side requests may not have cookies set. After sign-in, redirect to ONE specific page that does not use route prefetching. Once the browser has the tokens, the user can navigate freely to prefetched routes.

---

## 2. Supabase Realtime Best Practices

### Three Modes: When to Use Each

| Mode | Use Case | Persistence | Performance | Workshop Use |
|------|----------|-------------|-------------|--------------|
| **Broadcast** | Ephemeral messages between clients | None (fire-and-forget) | Best -- no DB overhead | Live polls, reactions, Q&A typing indicators |
| **Presence** | Track who is online/what they're doing | In-memory only | Good -- syncs state automatically | "32 attendees connected" indicator |
| **Postgres Changes** | React to database mutations | Full (triggers from DB) | Worst -- 1 read per subscriber per change | Agenda updates, persistent results |

### Workshop Platform Recommendation

**Use Broadcast for 90% of workshop interactions.** Here is why:

- Broadcast is peer-to-peer via the Realtime server -- no database reads
- Postgres Changes triggers N reads for N subscribers on each change (30 attendees = 30 reads per INSERT)
- Broadcast latency is under 100ms; Postgres Changes adds DB query overhead
- Broadcast scales linearly; Postgres Changes hits a single-thread bottleneck

**Use Postgres Changes only for data that must persist** (e.g., saving final poll results to the DB, then letting all clients see it).

### Channel Naming Convention

```typescript
// Pattern: feature:resource_id
const CHANNELS = {
  workshop: (id: string) => `workshop:${id}`,           // main workshop channel
  poll: (id: string, pollId: string) => `poll:${id}:${pollId}`,  // specific poll
  presence: (id: string) => `presence:${id}`,            // who's online
}
```

Rules:
- Channel name can be any string **except** `'realtime'` (reserved)
- Private and public channels with the same topic name are treated as unique channels
- Use hierarchical names (`workshop:abc123`) for easy debugging
- One channel per logical concern -- do not multiplex unrelated events on one channel

### Broadcast Pattern (Workshop Interactions)

```typescript
// Facilitator sends a poll to all attendees
const channel = supabase.channel(`workshop:${workshopId}`)

channel
  .on('broadcast', { event: 'poll:start' }, (payload) => {
    // All attendees receive this
    setPollData(payload.payload)
  })
  .on('broadcast', { event: 'poll:vote' }, (payload) => {
    // Facilitator aggregates votes
    addVote(payload.payload)
  })
  .on('broadcast', { event: 'reaction' }, (payload) => {
    showReaction(payload.payload)
  })
  .subscribe()

// Send a vote
channel.send({
  type: 'broadcast',
  event: 'poll:vote',
  payload: {
    user_id: userId,
    poll_id: pollId,
    choice: selectedOption,
    timestamp: Date.now(),  // for deduplication
  },
})
```

### Presence Pattern (Attendee Tracking)

```typescript
const channel = supabase.channel(`presence:${workshopId}`)

channel
  .on('presence', { event: 'sync' }, () => {
    const state = channel.presenceState()
    // state is a map of presence_key -> [{ user metadata }]
    setAttendeeCount(Object.keys(state).length)
  })
  .on('presence', { event: 'join' }, ({ key, newPresences }) => {
    // Someone joined
  })
  .on('presence', { event: 'leave' }, ({ key, leftPresences }) => {
    // Someone left
  })
  .subscribe(async (status) => {
    if (status === 'SUBSCRIBED') {
      await channel.track({
        user_id: userId,
        display_name: displayName,
        is_anonymous: isAnonymous,
        joined_at: new Date().toISOString(),
      })
    }
  })
```

### Reconnection Handling

The default Supabase reconnection uses **exponential backoff**: 1s, 2s, 4s, 8s... up to ~30s. This is usually sufficient. However, for a live workshop where disconnection must be invisible:

```typescript
// Create the Supabase client with worker and heartbeat options
const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  {
    realtime: {
      // Use a Web Worker to prevent browser tab throttling
      worker: true,
      workerUrl: '/realtime-worker.js',

      // Monitor connection health
      heartbeatCallback: (status: string) => {
        if (status === 'disconnected') {
          console.warn('Realtime disconnected, attempting reconnect...')
          // The client reconnects automatically, but you can
          // show a UI indicator to the user
          setConnectionStatus('reconnecting')
        }
        if (status === 'ok') {
          setConnectionStatus('connected')
        }
      },
    },
  }
)
```

**Why `worker: true` matters for workshops:** When a user switches tabs (e.g., to check email during a workshop), browsers throttle JavaScript timers. This can cause heartbeat messages to stop, making the server think the client disconnected. The Web Worker runs in a separate thread that is not throttled.

### Client-Side Deduplication

Supabase Realtime does NOT deduplicate messages for you. During reconnections, you may receive the same message twice. Implement your own deduplication:

```typescript
// Simple deduplication using a Set of message IDs
const processedMessages = new Set<string>()
const MAX_CACHE_SIZE = 1000

function handleBroadcast(payload: any) {
  // Every message should include a unique ID from the sender
  const messageId = payload.payload.message_id

  if (processedMessages.has(messageId)) {
    return // Skip duplicate
  }

  processedMessages.add(messageId)

  // Prevent unbounded memory growth
  if (processedMessages.size > MAX_CACHE_SIZE) {
    const iterator = processedMessages.values()
    // Remove oldest 20%
    for (let i = 0; i < MAX_CACHE_SIZE * 0.2; i++) {
      processedMessages.delete(iterator.next().value)
    }
  }

  // Process the message
  handleMessage(payload.payload)
}
```

### Facilitator-Side Event Aggregation

For polls and reactions, the facilitator should aggregate on-device rather than in the database:

```typescript
// Facilitator's poll aggregation (runs only on facilitator's client)
function usePollAggregator(channel: RealtimeChannel, pollId: string) {
  const [votes, setVotes] = useState<Map<string, string>>(new Map())

  useEffect(() => {
    channel.on('broadcast', { event: 'poll:vote' }, (payload) => {
      const { user_id, choice } = payload.payload

      setVotes((prev) => {
        const next = new Map(prev)
        // Last-write-wins per user -- prevents double-voting
        next.set(user_id, choice)
        return next
      })
    })
  }, [channel, pollId])

  // Derived aggregation
  const results = useMemo(() => {
    const counts: Record<string, number> = {}
    votes.forEach((choice) => {
      counts[choice] = (counts[choice] || 0) + 1
    })
    return counts
  }, [votes])

  // Periodically broadcast aggregated results back to attendees
  useEffect(() => {
    const interval = setInterval(() => {
      channel.send({
        type: 'broadcast',
        event: 'poll:results',
        payload: { poll_id: pollId, results, total: votes.size },
      })
    }, 2000) // Every 2 seconds

    return () => clearInterval(interval)
  }, [results, votes.size])

  return { votes, results }
}
```

### Realtime Authorization (Private Channels)

To restrict who can join a workshop channel, use RLS on `realtime.messages`:

```sql
-- Only allow users who belong to the workshop to subscribe
CREATE POLICY "workshop_participants_only"
ON realtime.messages
FOR SELECT
USING (
  -- Extract workshop_id from channel name like 'workshop:abc123'
  EXISTS (
    SELECT 1 FROM workshop_participants
    WHERE workshop_participants.user_id = auth.uid()
    AND workshop_participants.workshop_id = split_part(
      realtime.topic(), ':', 2
    )
  )
);
```

Then subscribe with `private: true`:

```typescript
const channel = supabase.channel(`workshop:${workshopId}`, {
  config: { private: true },
})
```

### Cleanup on Unmount

Always unsubscribe when the component unmounts:

```typescript
useEffect(() => {
  const channel = supabase.channel(`workshop:${workshopId}`)
  // ... subscribe logic

  return () => {
    supabase.removeChannel(channel)
  }
}, [workshopId])
```

---

## 3. RLS Patterns for Anonymous Users with Session IDs

### How Anonymous Auth Works with RLS

When you call `signInAnonymously()`, Supabase creates a real user in `auth.users` with:
- A UUID (`auth.uid()` works normally)
- A JWT with `is_anonymous: true` claim
- The `authenticated` role (same as regular users)

This means **anonymous users go through RLS just like authenticated users**. The difference is only visible via the JWT claim.

### Pattern: Workshop Participation Table

```sql
-- Table for tracking workshop attendees
CREATE TABLE workshop_participants (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  workshop_id UUID REFERENCES workshops(id) NOT NULL,
  display_name TEXT NOT NULL DEFAULT 'Anonymous',
  is_anonymous BOOLEAN DEFAULT true,
  session_id TEXT NOT NULL,  -- browser session identifier for reconnection
  joined_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, workshop_id)
);

ALTER TABLE workshop_participants ENABLE ROW LEVEL SECURITY;

-- Anonymous users can see other participants in their workshop
CREATE POLICY "participants_can_view_same_workshop"
ON workshop_participants FOR SELECT
USING (
  workshop_id IN (
    SELECT wp.workshop_id FROM workshop_participants wp
    WHERE wp.user_id = auth.uid()
  )
);

-- Users can insert themselves (anonymous or not)
CREATE POLICY "users_can_join_workshop"
ON workshop_participants FOR INSERT
WITH CHECK (
  user_id = auth.uid()
);

-- Users can only update their own record
CREATE POLICY "users_can_update_own_record"
ON workshop_participants FOR UPDATE
USING (user_id = auth.uid())
WITH CHECK (user_id = auth.uid());
```

### Pattern: Restricting Anonymous Users vs Permanent Users

```sql
-- Poll responses table
CREATE TABLE poll_responses (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  poll_id UUID REFERENCES polls(id) NOT NULL,
  choice TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, poll_id)
);

ALTER TABLE poll_responses ENABLE ROW LEVEL SECURITY;

-- Both anonymous and permanent users can submit votes
CREATE POLICY "anyone_can_vote"
ON poll_responses FOR INSERT
WITH CHECK (user_id = auth.uid());

-- Only permanent (non-anonymous) users can view detailed results
CREATE POLICY "permanent_users_see_results"
ON poll_responses FOR SELECT
USING (
  -- Check is_anonymous claim in JWT
  (auth.jwt() ->> 'is_anonymous')::boolean = false
);

-- Anonymous users can only see their own votes
CREATE POLICY "anonymous_see_own_votes"
ON poll_responses FOR SELECT
USING (
  (auth.jwt() ->> 'is_anonymous')::boolean = true
  AND user_id = auth.uid()
);
```

### Pattern: Session ID for Reconnection (Without Auth)

If you want attendees to reconnect without re-authenticating (e.g., they close and reopen the QR code link), store a `session_id` in the user's metadata and in localStorage:

```typescript
// On first join
async function joinWorkshop(workshopId: string) {
  const supabase = createClient()

  // Check for existing session
  const existingSessionId = localStorage.getItem(`workshop_session_${workshopId}`)

  if (existingSessionId) {
    // Try to restore session
    const { data: { user } } = await supabase.auth.getUser()
    if (user) {
      return user // Already signed in, session restored
    }
  }

  // New anonymous sign-in
  const sessionId = crypto.randomUUID()
  const { data, error } = await supabase.auth.signInAnonymously({
    options: {
      data: {
        session_id: sessionId,
        workshop_id: workshopId,
      },
    },
  })

  if (data?.user) {
    localStorage.setItem(`workshop_session_${workshopId}`, sessionId)
  }

  return data?.user
}
```

### Important Caveats

1. **Anonymous users cannot sign back in.** If they clear cookies/localStorage, their anonymous account is gone forever. This is fine for ephemeral workshop interactions, but their historical data becomes orphaned.

2. **RLS policies are permissive by default** -- they combine with OR. If you have a policy that allows anonymous access AND a policy for authenticated access, both apply. Use restrictive policies when you need AND logic:
   ```sql
   CREATE POLICY "restrictive_anon_check"
   ON some_table AS RESTRICTIVE
   FOR SELECT
   USING ((auth.jwt() ->> 'is_anonymous')::boolean = false);
   ```

3. **After upgrading anonymous to permanent**, the `is_anonymous` claim in the JWT changes to `false`, but the `user_id` stays the same. All existing data remains linked.

---

## 4. Connection Limits: Free vs Pro Tier

### Realtime Connection Limits (as of April 2026)

| Resource | Free Tier | Pro Tier ($25/mo) | Overage Cost |
|----------|-----------|-------------------|--------------|
| Peak concurrent connections | 200 | 500 | $10 per 1,000 connections |
| Messages per month | 2 million | 5 million | $2.50 per 1 million messages |
| Channel joins per second | Rate limited | Rate limited | Contact support |
| Messages per second | Rate limited | Rate limited | Contact support |

### What This Means for Your Workshop

With 30+ attendees, the **Free tier (200 connections) is sufficient** for a single workshop. Each attendee uses 1 connection (even if they subscribe to multiple channels on that connection).

**However**, watch for these connection multipliers:
- Each browser tab = 1 connection
- Facilitator dashboard + presenter view = 2 connections
- If attendees refresh the page rapidly, old connections may linger for ~30 seconds before timing out
- Development/testing connections count toward the limit

### Message Volume Estimate for a Workshop

Rough math for a 2-hour workshop with 30 attendees:
- Presence heartbeats: ~30 users x 1 msg/30s x 7200s = ~7,200 messages
- Poll interactions (5 polls): ~30 votes x 5 polls = 150 messages
- Reactions/engagement: ~100 reactions
- Facilitator broadcasts: ~200 messages
- Results broadcasts: ~100 messages
- **Total: ~7,750 messages per workshop**

Even running 10 workshops/month = ~77,500 messages. The Free tier's 2 million messages is more than adequate.

### Rate Limiting Behavior

When you exceed rate limits:
- Connections will be **disconnected** if your project generates too many messages per second
- `supabase-js` will **automatically reconnect** when throughput drops below the limit
- Channel joins can be **refused** if there are too many joins per second

### Recommendation

**Start on Free tier.** It handles 200 concurrent connections and 2 million messages/month. Only upgrade to Pro if you plan to run multiple simultaneous workshops or expect 200+ concurrent attendees.

---

## 5. Service Worker + Supabase: Offline-First Caching

### Why Offline-First Matters for Workshops

Workshops in conference venues often have unreliable WiFi. If an attendee's connection drops during a poll, they should still be able to:
1. See the current poll question (cached)
2. Submit their vote (queued)
3. Have it sync when connectivity returns

### Architecture: Three Layers

```
[Browser UI]
    |
[Service Worker] -- caches static assets + API responses
    |
[IndexedDB] -- queues offline mutations
    |
[Supabase REST API] -- syncs when online
```

### Service Worker Registration (Next.js)

```typescript
// app/layout.tsx (or a client component)
'use client'

import { useEffect } from 'react'

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker
        .register('/sw.js')
        .then((reg) => {
          console.log('SW registered:', reg.scope)
        })
        .catch((err) => {
          console.error('SW registration failed:', err)
        })
    }
  }, [])

  return null
}
```

### Service Worker: Caching Strategy

```javascript
// public/sw.js

const CACHE_NAME = 'workshop-v1'
const STATIC_ASSETS = [
  '/',
  '/workshop',
  '/offline',
  // Add CSS, JS bundles as needed
]

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  )
  self.skipWaiting()
})

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  )
  self.clients.claim()
})

// Fetch: strategy depends on request type
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Supabase REST API calls: Network-First with offline queue
  if (url.hostname.includes('supabase.co') && url.pathname.startsWith('/rest/')) {
    event.respondWith(networkFirstWithQueue(event.request))
    return
  }

  // Supabase Realtime (WebSocket): skip caching entirely
  if (url.hostname.includes('supabase.co') && url.pathname.startsWith('/realtime/')) {
    return // Let it pass through
  }

  // Static assets: Cache-First
  if (event.request.destination === 'style' ||
      event.request.destination === 'script' ||
      event.request.destination === 'image') {
    event.respondWith(cacheFirst(event.request))
    return
  }

  // HTML pages: Stale-While-Revalidate
  event.respondWith(staleWhileRevalidate(event.request))
})

async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached

  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME)
      cache.put(request, response.clone())
    }
    return response
  } catch {
    return new Response('Offline', { status: 503 })
  }
}

async function staleWhileRevalidate(request) {
  const cached = await caches.match(request)

  const fetchPromise = fetch(request).then((response) => {
    if (response.ok) {
      const cache = caches.open(CACHE_NAME)
      cache.then((c) => c.put(request, response.clone()))
    }
    return response
  }).catch(() => cached || new Response('Offline', { status: 503 }))

  return cached || fetchPromise
}

async function networkFirstWithQueue(request) {
  try {
    const response = await fetch(request)
    // Cache GET responses for offline reads
    if (request.method === 'GET' && response.ok) {
      const cache = await caches.open(CACHE_NAME)
      cache.put(request, response.clone())
    }
    return response
  } catch {
    // For GET: return cached
    if (request.method === 'GET') {
      const cached = await caches.match(request)
      if (cached) return cached
    }

    // For POST/PATCH/DELETE: queue for later
    if (request.method !== 'GET') {
      const body = await request.clone().text()
      await queueMutation({
        url: request.url,
        method: request.method,
        headers: Object.fromEntries(request.headers.entries()),
        body,
        timestamp: Date.now(),
      })
      return new Response(JSON.stringify({ queued: true }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response('Offline', { status: 503 })
  }
}

// IndexedDB queue for offline mutations
function queueMutation(mutation) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('workshop-sync', 1)
    request.onupgradeneeded = (e) => {
      e.target.result.createObjectStore('mutations', {
        keyPath: 'timestamp',
      })
    }
    request.onsuccess = (e) => {
      const db = e.target.result
      const tx = db.transaction('mutations', 'readwrite')
      tx.objectStore('mutations').add(mutation)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    }
  })
}

// Background Sync: replay queued mutations when online
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-mutations') {
    event.waitUntil(replayMutations())
  }
})

async function replayMutations() {
  const db = await new Promise((resolve) => {
    const req = indexedDB.open('workshop-sync', 1)
    req.onsuccess = (e) => resolve(e.target.result)
  })

  const tx = db.transaction('mutations', 'readonly')
  const store = tx.objectStore('mutations')
  const mutations = await new Promise((resolve) => {
    const req = store.getAll()
    req.onsuccess = () => resolve(req.result)
  })

  for (const mutation of mutations) {
    try {
      await fetch(mutation.url, {
        method: mutation.method,
        headers: mutation.headers,
        body: mutation.body,
      })

      // Remove from queue on success
      const deleteTx = db.transaction('mutations', 'readwrite')
      deleteTx.objectStore('mutations').delete(mutation.timestamp)
    } catch {
      // Will retry on next sync
      break
    }
  }
}
```

### Alternative: PowerSync for Full Offline-First

If you need robust offline-first with conflict resolution, consider **PowerSync** (official Supabase partner):

- Provides an embedded SQLite database in the browser
- Automatically syncs with Supabase Postgres via WAL replication
- Handles conflict resolution, retry logic, and queue management
- Much more robust than a hand-rolled service worker queue
- Trade-off: additional dependency and complexity

For a workshop platform with simple interactions (polls, reactions), the **service worker approach above is sufficient**. PowerSync is better suited for apps where users create complex data offline that must merge cleanly.

### Do NOT Cache WebSocket Connections

Service workers cannot intercept or cache WebSocket connections (Supabase Realtime). The service worker strategy only applies to:
- Static assets (CSS, JS, images)
- Supabase REST API calls (reads and writes)
- HTML pages

When offline, Realtime simply stops working. Design the UI to degrade gracefully:

```typescript
function useConnectionStatus() {
  const [status, setStatus] = useState<'online' | 'offline' | 'reconnecting'>('online')

  useEffect(() => {
    const handleOnline = () => setStatus('online')
    const handleOffline = () => setStatus('offline')

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  return status
}
```

---

## 6. Workshop-Specific Architecture Recommendations

### Recommended Stack

```
Next.js App Router
  + @supabase/ssr (auth + DB client)
  + Supabase Anonymous Auth (QR code entry)
  + Supabase Realtime Broadcast (polls, reactions)
  + Supabase Realtime Presence (attendee count)
  + Supabase Postgres + RLS (persistent data)
  + Service Worker (offline resilience)
```

### Data Flow for a Live Poll

```
1. Facilitator creates poll -> INSERT into polls table (Postgres)
2. Facilitator broadcasts poll:start -> Broadcast (ephemeral)
3. Attendees see poll -> Broadcast listener
4. Attendee votes -> Broadcast poll:vote (ephemeral)
5. Facilitator aggregates -> Client-side Map (no DB)
6. Facilitator broadcasts results -> Broadcast poll:results
7. Workshop ends -> Facilitator saves final results to DB
```

This minimizes database load during the live session. Only final results hit Postgres.

### Pitfalls to Avoid

1. **Do not use Postgres Changes for live interactions.** With 30 subscribers, every INSERT triggers 30 RLS checks. Use Broadcast instead.

2. **Do not create a new Supabase client on every render.** Create it once and pass it via React Context or a singleton.

3. **Do not forget to call `supabase.removeChannel()` on cleanup.** Leaked channels consume connection slots.

4. **Do not use `getSession()` for authorization.** Always use `getUser()` which validates against the server.

5. **Do not skip the middleware.** Without it, auth tokens silently expire and Server Components return null users.

6. **Do not assume Realtime messages are ordered or deduplicated.** Always include timestamps and message IDs, and deduplicate on the client.

7. **Do not use Realtime without filters in production.** Unfiltered Postgres Changes subscriptions can overload connections. Always filter by table and optionally by column values.

---

## Sources

- [Setting up Server-Side Auth for Next.js | Supabase Docs](https://supabase.com/docs/guides/auth/server-side/nextjs)
- [Advanced Auth Guide | Supabase Docs](https://supabase.com/docs/guides/auth/server-side/advanced-guide)
- [Anonymous Sign-Ins | Supabase Docs](https://supabase.com/docs/guides/auth/auth-anonymous)
- [Identity Linking | Supabase Docs](https://supabase.com/docs/guides/auth/auth-identity-linking)
- [Creating a Supabase Client for SSR | Supabase Docs](https://supabase.com/docs/guides/auth/server-side/creating-a-client)
- [Realtime Concepts | Supabase Docs](https://supabase.com/docs/guides/realtime/concepts)
- [Broadcast | Supabase Docs](https://supabase.com/docs/guides/realtime/broadcast)
- [Postgres Changes | Supabase Docs](https://supabase.com/docs/guides/realtime/postgres-changes)
- [Realtime Limits | Supabase Docs](https://supabase.com/docs/guides/realtime/limits)
- [Realtime Pricing | Supabase Docs](https://supabase.com/docs/guides/realtime/pricing)
- [Realtime Authorization | Supabase Docs](https://supabase.com/docs/guides/realtime/authorization)
- [Realtime: Handling Silent Disconnections | Supabase Docs](https://supabase.com/docs/guides/troubleshooting/realtime-handling-silent-disconnections-in-backgrounded-applications-592794)
- [Row Level Security | Supabase Docs](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase RLS Best Practices | MakerKit](https://makerkit.dev/blog/tutorials/supabase-rls-best-practices)
- [Realtime Duplicate Event Handling | DrDroid](https://drdroid.io/stack-diagnosis/supabase-realtime-duplicate-event-handling)
- [Supabase Realtime in Practice: Reconnection Strategies | BetterLink](https://eastondev.com/blog/en/posts/dev/supabase-realtime-practice/)
- [PowerSync: Bringing Offline-First to Supabase](https://www.powersync.com/blog/bringing-offline-first-to-supabase)
- [Building an Offline-First PWA with Next.js, IndexedDB, and Supabase | Medium](https://oluwadaprof.medium.com/building-an-offline-first-pwa-notes-app-with-next-js-indexeddb-and-supabase-f861aa3a06f9)
- [Manage Realtime Peak Connections Usage | Supabase Docs](https://supabase.com/docs/guides/platform/manage-your-usage/realtime-peak-connections)
- [Supabase Pricing 2026 | Metacto](https://www.metacto.com/blogs/the-true-cost-of-supabase-a-comprehensive-guide-to-pricing-integration-and-maintenance)
- [exchangeCodeForSession Breaking Change | GitHub Issue](https://github.com/supabase/supabase-js/issues/2037)
