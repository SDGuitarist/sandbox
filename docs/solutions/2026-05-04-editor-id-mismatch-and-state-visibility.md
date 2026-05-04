---
title: "Editor ID Mismatch and State Visibility Bugs"
date: 2026-05-04
project: writers-room-council
tags: [supabase, uuid, react-state, editor, persistence]
failure_class: id-mismatch, dead-code, incomplete-lifecycle
agents_involved: manual (bug fix session)
complexity: medium
---

# Editor ID Mismatch and State Visibility Bugs

## Problem

Three related editor bugs prevented decisions from persisting and edits from displaying:

1. **ID mismatch (P0):** The `/api/editor/analyze` route generated `crypto.randomUUID()` for each suggestion and returned these IDs to the client, but did NOT include them in the database insert. Supabase auto-generated different UUIDs for the rows. When the client later called `/api/editor/decide` with the ID it received, the RPC function (`update_signature_after_decision`) found no matching row and silently returned.

2. **Dead rendering code (P1):** `DocumentView.tsx` filtered accepted suggestions out of `visibleSuggestions`, which meant the text region became a plain segment showing original text. The rendering branch for accepted suggestions (showing edited text) was dead code that could never execute.

3. **Incomplete lifecycle (P2):** Editor sessions were set to `'review'` status during analysis but never updated to `'completed'` after all decisions were made.

## Why It Was Hard to Find

- The decide API route, RPC function, and client code all looked correct in isolation. The bug was in the gap between two separate routes (analyze creates, decide looks up).
- The `postDecision` function had a `catch {}` that silently swallowed all errors, including the 500 from the RPC failure.
- The rendering code for accepted suggestions existed and looked correct, but was unreachable due to the filter logic above it.

## Solution

### Fix 1: Include generated IDs in database insert
**File:** `src/app/api/editor/analyze/route.ts`
Added `id: s.id` to all three insert blocks (mock mode, LLM mode, timeout fallback). Now the database row ID matches what the client receives.

### Fix 2: Keep accepted suggestions in segment calculation
**File:** `src/app/(app)/projects/[id]/editor/components/DocumentView.tsx`
Changed the `visibleSuggestions` filter to include accepted suggestions:
```typescript
// Before: filtered out accepted (broke edited text display)
(s) => !decisions[s.id] || decisions[s.id] === 'editing'

// After: keeps accepted so edited text renders correctly
(s) => !decisions[s.id] || decisions[s.id] === 'editing' || decisions[s.id] === 'accepted'
```
Rejected suggestions are still filtered out (original text shows as plain segment, which is correct).

### Fix 3: Mark session completed
**File:** `src/app/(app)/projects/[id]/editor/page.tsx`
When all suggestions are decided, update the editor session status via browser Supabase client (RLS allows it via existing policy).

## Pattern: Generated IDs Must Round-Trip

When you generate an ID in application code and return it to the client, that SAME ID must be stored in the database. Otherwise any subsequent lookup by that ID will fail silently.

**Rule:** If you call `crypto.randomUUID()` and include it in an API response, include it in the database insert too. Never rely on the database to auto-generate a matching ID.

## Pattern: Filter Logic Creates Dead Code

When a React component filters items out of a list, any rendering logic for those filtered items becomes dead code. If you need different rendering for different states (editing, accepted, rejected), keep the items in the list and branch on state during rendering.

**Rule:** Before filtering items from a render list, verify that no downstream rendering branch depends on those items being present.

## Verification

- `editor_suggestions.user_decision`: populated with accept/reject values
- `editorial_signatures.principle_weights`: populated with per-principle counts
- `editor_sessions.status`: shows 'completed' after all decisions
- Inline edited text persists visually after confirm
