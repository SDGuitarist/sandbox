---
title: "Writers Room Council App: Autopilot Swarm Spec"
date: 2026-05-03
type: feat
status: spec
deadline: 2026-05-30
build_method: autopilot
swarm: true
brainstorm: docs/brainstorms/2026-05-02-writers-room-council-app-brainstorm.md
origin: docs/brainstorms/2026-05-02-writers-room-council-app-brainstorm.md
feed_forward:
  risk: "Two tied risks: (1) inline annotation system with editable-on-accept quality in autopilot timeframe, (2) prompt-porting from Claude Projects to API preserving Contrarian verb catch quality. Novel integration seam with no prior solution doc."
  verify_first: true
---

# Writers Room Council App: Autopilot Swarm Spec

**Execution Principle:** Rigid spec adherence. Agents build to exact contracts below. Do not infer schema changes. Reference source docs for detailed content (principle text, voice personas, golden transcripts) but build to the interfaces defined here.

**Enhancement Summary:**
- Deepened from brainstorm with 20 resolved decisions, 12 autopilot build requirements, Codex review, and NotebookLM cross-reference
- Key patterns applied: Export Names Table, Cross-Boundary Wiring, Data Ownership, Schema Pre-Gate, Mock Mode, Structured Outputs (all from Run 033 lessons)
- New territory (no prior solution docs): inline annotation with editable-on-accept, editorial signature learning via accept/reject, prompt porting from Claude Projects to per-call API
- **Deepened 2026-05-03** with 6 parallel research/review agents (Next.js 15 + AI SDK, Anthropic API, Supabase, inline annotation UI, security sentinel, architecture strategist). Key improvements below.

### Deepening Key Improvements
1. **Security: 3 critical fixes** applied to schema (SECURITY DEFINER auth check, INSERT policy on profiles, admin auth mechanism)
2. **Architecture: 3 P0 fixes** applied (register_leveling column, what_survives column, Phase 1 scoring floor dependency)
3. **SDK clarification:** Vercel AI SDK (`ai` package) for streaming to client, Anthropic SDK for non-streaming structured calls. Both used, different purposes.
4. **Inline annotation pattern:** Controlled React (no contenteditable). Plain text -> `splitTextByAnnotations()` -> styled spans. Radix UI Popover for suggestion display. Inline `<input>` on accept.
5. **AI SDK 6 `Output.object()`:** Streaming + structured output in ONE call (not two). Stream prose, validate structured result after completion.
6. **Supabase whitelist:** Auth Hook (`before_user_created` trigger) on `allowed_emails` table. Check happens before magic link is sent.
7. **RLS performance:** Nested subquery policies wrapped in `SECURITY DEFINER` helper functions. Indexes on all FK columns used in RLS.
8. **TranscriptEntry schema:** Defined as discriminated union to prevent swarm agents from diverging on JSONB structure.
9. **Rate limiting:** In-memory Map does NOT work on Vercel serverless (resets on cold starts). Added Supabase-based counter as primary limiter.
10. **Prompt caching:** 1,024-token minimum, 5-min TTL (refreshable on hit), 90% read discount. Voice templates + framework rules cached per session.

**Source Documents (agents read as needed, not all at once):**
- Brainstorm: `docs/brainstorms/2026-05-02-writers-room-council-app-brainstorm.md`
- WRC v1.4 framework: `~/Downloads/files/` (framework instructions, loaded in project context)
- Editor build brief v0.2: `~/Downloads/ai-human-editor-build-brief-v0.2.md`
- Core Voice document: `~/Projects/amplify-workshop/marketing/context/voice/core-voice.md`
- Golden transcripts: `~/Downloads/files/session-1-*.md`, `session-2-*.md`, `session-3-*.md`
- Ethics toolkit spec (format precedent): `docs/plans/2026-04-30-ethics-toolkit-platform-spec.md`

---

## 1. Global Constraints & Guardrails

### Product Constraints
- **Never rewrites.** The app never generates replacement prose. Allowed: flag a passage, name the principle violated, ask a diagnostic question, describe the structural move available. Forbidden: generate rewritten sentences, offer suggested revisions, produce AI-written "after" text, show replacement wording.
- **Every accept/reject is logged.** No silent applications. No bulk accept-all without per-decision logging.
- **App controls sequence, user controls voice.** Framework constraints (Phase 0 first, voices in order, beats in sequence) are enforced by the UX. Users speak freely within each step via free-text input.
- **Closing Handoff is non-negotiable.** Every Seed Council session delivers the closing handoff. If Beat 5 is skipped, handoff attaches to Beat 4.
- **Characters not scripts.** Five Council voices are persistent characters with consistent personalities. Questions are improvised live, calibrated to the writer's input. The UI and prompt templates must reflect this.

### Infrastructure Constraints
- **Mobile-responsive.** No mobile-specific layouts. Responsive design with min 16px body text, min 44px touch targets.
- **Offline degradation.** If Anthropic API is unreachable, fall back to mock mode. App remains navigable. Phase 0, project management, signature dashboard, and document viewing work without API.
- **Single-process deployment.** Vercel serverless. No background workers. Each API call is a separate function invocation.
- **Mock mode from day 1.** Every LLM call has a mock fallback returning valid structured data. One mock system (not per-phase). App works fully without ANTHROPIC_API_KEY.

### Security Constraints
- **Use `getUser()` not `getSession()`** in middleware. `getSession()` doesn't revalidate the token and can be spoofed.
- **HTML-escape all user-pasted text before rendering.** Inline annotations use safe DOM manipulation (styled spans around text nodes). DO NOT use `dangerouslySetInnerHTML` with user content.
- **CSRF protection:** All state-mutating API routes validate `Content-Type: application/json` and check the `Origin` header. HTML forms cannot send `application/json`, which prevents most CSRF.
- **Admin routes** (`/api/admin/*`) require `is_admin = true` on the user's profile. Only Alex's email is admin in beta.
- **Prompt injection mitigation:** System prompts include explicit instruction to ignore instructions embedded in user documents. User text sandboxed within `<user_document>` XML tags in prompts.
- **Error responses:** Never send raw LLM output to the client on validation failure. Log server-side, return generic error.
- **Security headers:** `next.config.ts` sets `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
- **Input max lengths:** `draft_versions.content` max 100,000 chars (~20,000 words). Enforced in Zod schema and SQL CHECK constraint.

---

## 2. Identity & Auth Architecture

### Auth Flow (Supabase Magic Link)
- Default state: unauthenticated. Landing page with email input.
- User enters email, receives magic link via Supabase Auth.
- Post-auth: user record created in `profiles` table. Phase 0 onboarding begins.
- Beta cohort: whitelisted emails only. Non-whitelisted emails see: "Beta access is by invitation. Contact alex@amplifyai.to."
- Post-beta: waitlist page for non-whitelisted emails.

### Session Management
- Supabase session via `@supabase/ssr` cookie-based auth.
- Middleware checks auth on all routes except `/`, `/auth/callback`, `/api/auth/*`.
- Unauthenticated users redirected to `/`.

### No Anonymous Access
Unlike the ethics toolkit, there is no anonymous session mode. All features require authentication because the signature learning system requires persistent per-user state.

---

## 3. Authoritative Database Schema

```sql
-- Migration 001: Core Schema

-- Users (extends Supabase auth.users)
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  display_name TEXT,
  is_beta_whitelisted BOOLEAN DEFAULT false,
  is_admin BOOLEAN DEFAULT false,
  phase0_completed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Phase 0 Fingerprint (user-level, runs once)
CREATE TABLE fingerprints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  -- Council calibration
  primary_genre TEXT NOT NULL,
  thematic_obsessions TEXT NOT NULL,
  structural_failure_patterns TEXT NOT NULL,
  voice_tone_self_report TEXT NOT NULL,
  -- Editor calibration
  worst_writing_habit TEXT NOT NULL,
  register_and_reader TEXT NOT NULL,
  -- Shared inputs
  writing_sample TEXT NOT NULL,
  before_after_passage_before TEXT,
  before_after_passage_after TEXT,
  before_after_required BOOLEAN DEFAULT true,
  scoring_floor_passed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id)
);

-- Projects
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  genre TEXT NOT NULL DEFAULT 'essay_longform',
  -- Project-level Phase 0
  description TEXT,
  intent TEXT,
  protecting TEXT,
  -- Handoff state (drives contextual next-step UX)
  handoff_state TEXT NOT NULL DEFAULT 'ready',
  -- CHECK (handoff_state IN ('ready', 'seed_complete', 'awaiting_draft', 'council_complete_greenlight', 'council_complete_rewrite', 'council_complete_pass', 'awaiting_revision', 'editor_ready'))
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_projects_user ON projects(user_id);

-- Draft Versions (pasted text snapshots)
CREATE TABLE draft_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  word_count INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_drafts_project ON draft_versions(project_id);

-- Council Sessions (Seed, Standard, RWP)
CREATE TABLE council_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  mode TEXT NOT NULL,
  -- CHECK (mode IN ('seed_council', 'standard_council', 'returning_writer'))
  draft_version_id UUID REFERENCES draft_versions(id),
  previous_session_id UUID REFERENCES council_sessions(id),
  -- Structured session data
  transcript JSONB NOT NULL DEFAULT '[]',
  -- Seed outputs
  named_intent TEXT,
  unanswerable_question TEXT,
  closing_handoff_delivered BOOLEAN DEFAULT false,
  -- Standard Council / RWP outputs
  verdict TEXT,
  -- CHECK (verdict IN ('greenlight', 'rewrite', 'pass'))
  pass_subtype TEXT,
  -- CHECK (pass_subtype IN ('premise_broken', 'reckoning_insufficient'))
  verdict_explanation TEXT,
  central_question TEXT,
  revision_map TEXT,
  what_survives TEXT,
  -- Status
  status TEXT NOT NULL DEFAULT 'in_progress',
  -- CHECK (status IN ('in_progress', 'completed', 'abandoned'))
  current_step INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX idx_sessions_project ON council_sessions(project_id);

-- Editor Sessions
CREATE TABLE editor_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  draft_version_id UUID NOT NULL REFERENCES draft_versions(id),
  status TEXT NOT NULL DEFAULT 'analyzing',
  -- CHECK (status IN ('analyzing', 'review', 'completed'))
  suppression_count INTEGER DEFAULT 0,
  signature_snapshot JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX idx_editor_sessions_project ON editor_sessions(project_id);

-- Editor Suggestions (all generated, including suppressed)
CREATE TABLE editor_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  editor_session_id UUID NOT NULL REFERENCES editor_sessions(id) ON DELETE CASCADE,
  principle_id INTEGER NOT NULL,
  -- CHECK (principle_id BETWEEN 1 AND 15)
  classification TEXT NOT NULL,
  -- CHECK (classification IN ('structural_catch', 'voice_formalization', 'voice_protection'))
  -- Deterministic pre-LLM flags (P7, P8) always classified as 'voice_protection'
  -- P9 classified by LLM as 'voice_protection' when register matches
  -- P1-6, 10-15 classified by LLM as 'structural_catch' or 'voice_formalization'
  is_suppressed BOOLEAN NOT NULL DEFAULT false,
  -- true when classification = 'voice_formalization' and register_leveling is off
  flag_text TEXT NOT NULL,
  question_text TEXT,
  original_text_segment TEXT NOT NULL,
  char_offset_start INTEGER NOT NULL,
  char_offset_end INTEGER NOT NULL,
  -- User decision (null until decided)
  user_decision TEXT,
  -- CHECK (user_decision IN ('accept', 'reject', 'accept_no_edit'))
  decided_at TIMESTAMPTZ,
  user_note TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_suggestions_session ON editor_suggestions(editor_session_id);
CREATE INDEX idx_suggestions_principle ON editor_suggestions(principle_id);

-- Beta Whitelist (checked via Auth Hook before magic link is sent)
CREATE TABLE allowed_emails (
  email TEXT PRIMARY KEY,
  invited_at TIMESTAMPTZ DEFAULT now()
);

-- Editorial Signature (per-user principle weights)
CREATE TABLE editorial_signatures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  -- Principle weights: frequency-weighted invocation profile
  -- Keys: "p1" through "p15"
  -- Values: { accept_count, reject_count, accept_no_edit_count, total_flagged, weight }
  principle_weights JSONB NOT NULL DEFAULT '{}',
  register_leveling BOOLEAN DEFAULT false,
  total_documents_edited INTEGER DEFAULT 0,
  total_decisions_logged INTEGER DEFAULT 0,
  total_suppressions INTEGER DEFAULT 0,
  last_updated TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id)
);
```

```sql
-- Migration 002: RLS Policies

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE fingerprints ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE draft_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE council_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE editor_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE editor_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE editorial_signatures ENABLE ROW LEVEL SECURITY;

-- All tables: authenticated users can only access their own data
CREATE POLICY "Users insert own profile" ON profiles FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "Users read own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users manage own fingerprint" ON fingerprints FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own projects" ON projects FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own drafts" ON draft_versions FOR ALL
  USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()));
CREATE POLICY "Users manage own sessions" ON council_sessions FOR ALL
  USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()));
CREATE POLICY "Users manage own editor sessions" ON editor_sessions FOR ALL
  USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()));
CREATE POLICY "Users manage own suggestions" ON editor_suggestions FOR ALL
  USING (editor_session_id IN (
    SELECT es.id FROM editor_sessions es
    JOIN projects p ON es.project_id = p.id
    WHERE p.user_id = auth.uid()
  ));
CREATE POLICY "Users manage own signature" ON editorial_signatures FOR ALL USING (auth.uid() = user_id);
```

```sql
-- Migration 003: RPC Functions (Atomic Operations)

-- Atomic signature update after accept/reject decision
CREATE OR REPLACE FUNCTION update_signature_after_decision(
  p_user_id UUID,
  p_suggestion_id UUID,
  p_principle_id INTEGER,
  p_decision TEXT,
  p_user_note TEXT DEFAULT NULL,
  p_decided_at TIMESTAMPTZ DEFAULT now()
) RETURNS void AS $$
DECLARE
  v_key TEXT;
  v_current JSONB;
BEGIN
  -- SECURITY: verify caller owns this data
  IF p_user_id != auth.uid() THEN
    RAISE EXCEPTION 'unauthorized';
  END IF;

  -- Update the suggestion
  UPDATE editor_suggestions
  SET user_decision = p_decision, decided_at = p_decided_at, user_note = p_user_note
  WHERE id = p_suggestion_id;

  -- Build principle key
  v_key := 'p' || p_principle_id::TEXT;

  -- Upsert signature with principle weight update
  INSERT INTO editorial_signatures (user_id, principle_weights, total_decisions_logged, last_updated)
  VALUES (p_user_id, jsonb_build_object(v_key, jsonb_build_object(
    'accept_count', CASE WHEN p_decision IN ('accept', 'accept_no_edit') THEN 1 ELSE 0 END,
    'reject_count', CASE WHEN p_decision = 'reject' THEN 1 ELSE 0 END,
    'accept_no_edit_count', CASE WHEN p_decision = 'accept_no_edit' THEN 1 ELSE 0 END,
    'total_flagged', 1
  )), 1, now())
  ON CONFLICT (user_id) DO UPDATE SET
    principle_weights = jsonb_set(
      COALESCE(editorial_signatures.principle_weights, '{}'),
      ARRAY[v_key],
      jsonb_build_object(
        'accept_count', COALESCE((editorial_signatures.principle_weights->v_key->>'accept_count')::int, 0)
          + CASE WHEN p_decision IN ('accept', 'accept_no_edit') THEN 1 ELSE 0 END,
        'reject_count', COALESCE((editorial_signatures.principle_weights->v_key->>'reject_count')::int, 0)
          + CASE WHEN p_decision = 'reject' THEN 1 ELSE 0 END,
        'accept_no_edit_count', COALESCE((editorial_signatures.principle_weights->v_key->>'accept_no_edit_count')::int, 0)
          + CASE WHEN p_decision = 'accept_no_edit' THEN 1 ELSE 0 END,
        'total_flagged', COALESCE((editorial_signatures.principle_weights->v_key->>'total_flagged')::int, 0) + 1
      )
    ),
    total_decisions_logged = editorial_signatures.total_decisions_logged + 1,
    last_updated = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Auth Hook: whitelist enforcement (prevents magic link for non-whitelisted emails)
-- NOTE: This function must be wired to auth.users via Supabase Dashboard > Auth > Hooks > "Before User Created"
-- The trigger cannot be created via SQL migration because auth.users is managed by Supabase
CREATE OR REPLACE FUNCTION check_email_allowed()
RETURNS trigger AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM allowed_emails WHERE email = NEW.email) THEN
    RAISE EXCEPTION 'Signup not allowed for this email';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RLS helper: get user's project IDs (avoids per-row subquery in RLS policies)
CREATE OR REPLACE FUNCTION auth.user_project_ids()
RETURNS SETOF uuid
LANGUAGE sql SECURITY DEFINER STABLE
SET search_path = ''
AS $$
  SELECT p.id FROM public.projects p WHERE p.user_id = (SELECT auth.uid())
$$;
```

```sql
-- Migration 004: Seed Data

-- Beta whitelist (populated by Alex before workshop)
-- INSERT INTO profiles (id, email, is_beta_whitelisted) VALUES (...);
-- Seed data is managed via admin route, not migration
```

---

## 4. Core Workflow Contracts

### 4.1 Phase 0 Fingerprint

**Three layers, each with specific questions:**

**Layer 1: User-level (runs once at account creation)**

Council calibration:
1. "What kind of writing do you do most?" (genre/form)
2. "What's a theme or subject you keep returning to?" (thematic obsessions)
3. "When your writing doesn't work, what's usually the problem?" (structural failure patterns)
4. "Describe your voice in a sentence." (voice/tone self-report)

Editor calibration:
5. "What's your worst writing habit?" (editorial failure pattern)
6. "What register are you working in, and who's the reader?" (Crystal filter baseline)

Shared inputs:
7. Writing sample (500-1000 words)
8. Before/after passage (REQUIRED, editorial signature baseline)

**Scoring Floor check:** After intake, LLM evaluates whether the writing sample + before/after passage provide enough texture for Council voices to generate genuine questions (ask, not tell). If insufficient, flag: "Your intake doesn't give the council enough to work with. Add more detail."

**Layer 2: Project-level (runs per project)**
1. "What are you working on?"
2. "What's this piece trying to do?"
3. "What are you protecting in this piece?"

**Layer 3: Seed Council micro-interview (within Seed Council only, NOT Phase 0)**
- Coaxing prompt (verbatim from v1.4 framework)
- Three micro-interview questions calibrated to the seed

#### Phase 0 Zod Schemas

```typescript
// lib/schemas/fingerprint.ts

const FingerprintInput = z.object({
  primaryGenre: z.string().min(1).max(500),
  thematicObsessions: z.string().min(1).max(1000),
  structuralFailurePatterns: z.string().min(1).max(1000),
  voiceToneSelfReport: z.string().min(1).max(500),
  worstWritingHabit: z.string().min(1).max(500),
  registerAndReader: z.string().min(1).max(500),
  writingSample: z.string().min(100).max(10000),
  beforeAfterBefore: z.string().min(50).max(5000).optional(),
  beforeAfterAfter: z.string().min(50).max(5000).optional(),
});

const ScoringFloorResult = z.object({
  passed: z.boolean(),
  reason: z.string().optional(),
});

const ProjectCalibration = z.object({
  description: z.string().min(1).max(500),
  intent: z.string().min(1).max(500),
  protecting: z.string().min(1).max(500),
});
```

### 4.1b Transcript Entry Schema (Shared Across All Council Modes)

All council session transcripts use this discriminated union. Prevents swarm agents from inventing incompatible JSONB structures.

```typescript
// lib/schemas/transcript.ts

const TranscriptEntry = z.discriminatedUnion('type', [
  z.object({ type: z.literal('coaxing'), content: z.string() }),
  z.object({ type: z.literal('micro_interview'), question: z.string(), response: z.string() }),
  z.object({ type: z.literal('beat'), beat: z.number(), voiceName: z.string(), content: z.string() }),
  z.object({ type: z.literal('voice'), voiceNumber: z.number(), voiceName: z.string(), content: z.string(), keyQuestion: z.string() }),
  z.object({ type: z.literal('writer_response'), content: z.string(), respondingTo: z.string() }),
  z.object({ type: z.literal('closing_handoff'), content: z.string() }),
  z.object({ type: z.literal('verdict'), verdict: z.string(), explanation: z.string(), centralQuestion: z.string() }),
]);

type Transcript = z.infer<typeof TranscriptEntry>[];
```

All agents writing to `council_sessions.transcript` MUST use this schema. Agent 2.0 (schemas pre-gate) validates it with fixtures.

### 4.2 Seed Council Mode

**Flow:** Coaxing prompt -> micro-interview (3 questions) -> 5 beats with 4 writer-response moments -> Closing Handoff

Each beat is one API call. The app advances beats; the user responds between them.

```typescript
// lib/schemas/seed-council.ts

const SeedBeatResponse = z.object({
  beat: z.number().min(1).max(5),
  voiceName: z.enum(['champion', 'contrarian']),
  content: z.string().min(1).max(2000),
  // Beat 2: Champion reflects + asks protection question
  protectionQuestion: z.string().optional(),
  // Beat 4: Contrarian's unanswerable question
  unanswerableQuestion: z.string().optional(),
  // Beat 5: Champion's final question
  finalQuestion: z.string().optional(),
});

const SeedClosingHandoff = z.object({
  handoffText: z.string(), // Fixed text from v1.4 framework
  namedIntent: z.string(), // Writer's answer to Beat 5
  unanswerableQuestion: z.string(), // From Beat 4
});
```

**Beat sequence:**
1. Champion asks 2 questions (writer responds)
2. Champion reflects, asks "what would you fight to keep?" (writer responds)
3. Contrarian asks 1 question targeting the assumption (writer responds)
4. Contrarian destabilizes, asks the unanswerable question (writer reads/responds)
5. Champion asks: "what's the version that survives?" (writer names it)
6. Closing Handoff (non-negotiable, delivered after Beat 5 or Beat 4 if skipped)

### 4.3 Standard Council Mode

**Flow:** 5 voices in fixed sequence, each completes fully before the next begins. Writer responds after each voice. Verdict delivered after all 5 complete.

```typescript
// lib/schemas/standard-council.ts

const CouncilVoiceResponse = z.object({
  voiceNumber: z.number().min(1).max(5),
  voiceName: z.enum(['champion', 'story_architect', 'character_interrogator', 'audience_proxy', 'contrarian']),
  content: z.string().min(1).max(3000),
  // Voice-specific structured outputs
  keyQuestion: z.string(), // The main question this voice asks
  specificReferences: z.array(z.string()), // Specific script references cited
});

const CouncilVerdict = z.object({
  verdict: z.enum(['greenlight', 'rewrite', 'pass']),
  passSubtype: z.enum(['premise_broken', 'reckoning_insufficient']).optional(),
  verdictExplanation: z.string().min(1).max(2000),
  centralQuestion: z.string().min(1).max(500),
  revisionMap: z.string().min(1).max(2000),
  whatSurvives: z.string().min(1).max(1000),
});
```

**Verdict handoff (contextual next step):**
- Greenlight: display central question + revision map. Prompt: [Run Editor pass] or [Start new project]. Set handoff_state = 'council_complete_greenlight'.
- Rewrite: display central question + revision map. Prompt: [Submit revised draft]. Set handoff_state = 'council_complete_rewrite'.
- Pass: display explanation + what survives. Prompt: [Return to Seed Council] or [Start new project]. Set handoff_state = 'council_complete_pass'.

### 4.4 Returning Writer Protocol

**Flow:** Reads previous session's central question, verdict, and revision map from project record. Runs full 5-voice council calibrated against the previous pass. New verdict accounts for revision progress.

```typescript
// lib/schemas/rwp.ts

const RWPContext = z.object({
  previousCentralQuestion: z.string(),
  previousVerdict: z.enum(['greenlight', 'rewrite', 'pass']),
  previousRevisionMap: z.string(),
});

// Uses same CouncilVoiceResponse and CouncilVerdict schemas
// Each voice receives RWPContext in the prompt
```

### 4.5 Editor Mode

**Two-pass processing:**

**Pass 1 (Pre-LLM, deterministic):** Grep for em-dashes (P7) and banned vocabulary (P8). These bypass the Crystal filter entirely. Zero tokens.

**Pass 2 (LLM judgment):** Analyze document against principles 1-6, 9-15. Return ALL suggestions tagged as structural_catch, voice_formalization, or voice_protection.

```typescript
// lib/schemas/editor.ts

const EditorSuggestion = z.object({
  principleId: z.number().min(1).max(15),
  classification: z.enum(['structural_catch', 'voice_formalization', 'voice_protection']),
  flagText: z.string().min(1).max(500),
  questionText: z.string().max(500).optional(), // P7 has no question (hard rule)
  originalTextSegment: z.string().min(1),
  charOffsetStart: z.number().min(0),
  charOffsetEnd: z.number().min(0),
});

const EditorAnalysisResponse = z.object({
  suggestions: z.array(EditorSuggestion),
  totalGenerated: z.number(),
  suppressedCount: z.number(),
});

// Crystal filter: suppress suggestions where classification = 'voice_formalization'
// Unless user has toggled register_leveling = true
```

**Accept/reject flow:**
- Accept: annotation clears, cursor lands in flagged text, user rewrites in place. Decision logged as 'accept'. If user navigates away without changing text, logged as 'accept_no_edit'.
- Reject: annotation clears. Decision logged as 'reject'.
- All decisions update the editorial signature via RPC function (atomic).

**15 Principles reference:** Full operational definitions (triggers, flags, questions, before/after examples) are in `~/Downloads/ai-human-editor-build-brief-v0.2.md`. Agents building the Editor MUST read that file. The principle IDs and their categories:

| ID | Name | Category | Pass |
|----|------|----------|------|
| 1 | Don't stack statistics | Argument | LLM |
| 2 | Mechanism leads, studies illustrate | Argument | LLM |
| 3 | Compress via hinge | Argument | LLM |
| 4 | Concessions advance argument | Argument | LLM |
| 5 | Headers name what you show | Argument | LLM |
| 6 | Trust the reader | Argument | LLM |
| 7 | No em-dashes | Voice | Pre-LLM grep |
| 8 | Five-tier banned vocabulary | Voice | Pre-LLM grep |
| 9 | Peer-to-peer register | Voice | LLM (voice_protection) |
| 10 | Crystal Principle (meta-filter) | Discipline | Filter logic |
| 11 | Don't tell after showing | Discipline | LLM |
| 12 | Fold minor citations | Argument | LLM |
| 13 | Cut due diligence paragraphs | Discipline | LLM |
| 14 | Function determines form | Argument | LLM |
| 15 | Delete narration of demonstration | Discipline | LLM |

**Banned vocabulary source:** Tiers 1, 2, 5 complete in `~/Projects/amplify-workshop/marketing/context/voice/core-voice.md`. Tiers 3-4 have category names + few examples (adequate for beta). Load all tiers into a static array at build time.

### 4.6 Signature Dashboard

**Empty state (pre-Editor):** Display Phase 0 data back to user (worst habit, register, before/after preview). "0 documents edited. Run your first Editor pass."

**Active state:** Principle acceptance rates (bar chart per principle), total documents, total decisions, suppression count ("N voice formalizations suppressed"), compounding indicators.

**Must be readable after 2 sessions.** Even with 3 decisions logged, show: "tell-after-show flagged twice, both accepted."

---

## 5. Streaming & Realtime Contracts

### SDK Roles (Two SDKs, Different Purposes)
- **Vercel AI SDK (`ai` package):** All streaming responses to the client. Provides `streamText()`, `Output.object()`, `useChat` hook, `DefaultChatTransport`, and `toUIMessageStreamResponse()`. This is the primary SDK for Council voice outputs and Editor analysis.
- **Anthropic SDK (`@anthropic-ai/sdk`):** Non-streaming structured calls only (Scoring Floor check, classification validation). Used via `client.messages.create()` with `output_config.format.json_schema` for guaranteed structured JSON.
- **DO NOT mix SDKs for the same call.** Streaming = Vercel AI SDK. Non-streaming structured = Anthropic SDK.

### LLM Response Streaming (Council Modes)
- All Council voice outputs stream via Vercel AI SDK `streamText()` with `Output.object()` for combined streaming + structured extraction.
- `Output.object()` streams prose to the client AND validates a structured result after stream completes. One call, not two.
- Streaming is architectural, not polish. The "characters not scripts" framing requires voices that feel alive.
- Each beat/voice is a separate API call (not one long-running function). No serverless timeout risk.
- Client uses `useChat` with `DefaultChatTransport({ api: '/api/council/seed' })`.

### LLM Response (Editor Mode)
- Editor analysis is NOT streamed. User pastes text, clicks "Run Editor", waits for results.
- Use Anthropic SDK `client.messages.create()` with `output_config.format.json_schema` for guaranteed structured JSON.
- Returns `EditorAnalysisResponse` (array of suggestions with classifications).

### Structured Output After Stream (Council)
- `Output.object()` handles extraction automatically. Access via `await result.output` server-side.
- If structured extraction fails, store the raw text and flag `schema_validation_failed: true`. Do not crash. Do not send raw LLM text to client on failure (could leak system prompt fragments). Return generic error.

### No Supabase Realtime
- Unlike the ethics toolkit, this app has no multi-user realtime features.
- All data flows are single-user: user -> API -> database -> user.

---

## 6. Locked Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Stack | Next.js 15 + Supabase + Vercel | Proven in Run 033 |
| 2 | Auth | Supabase Magic Link | Lowest friction for writers |
| 3 | LLM | Opus 4.6 for all modes | Verb catch requires Opus-level judgment |
| 4 | Editor UI | Inline annotations, editable on accept | Thesis felt in the writing |
| 5 | Document input | Paste text | No file parsing complexity |
| 6 | Phase 0 | 3-layer (user + project + micro-interview) | Serves both Council and Editor |
| 7 | Project model | Project-based containers | RWP needs first-class fields |
| 8 | Signature | Dedicated dashboard view | Must be readable after 2 sessions |
| 9 | Genre profile | Essay/Long-form only | One tight profile > two loose ones |
| 10 | Access | Beta cohort, 14-day free | Not free trial |
| 11 | Build order | Editor first, 4 sequential phases | Hardest problem first |
| 12 | Navigation | Read-only scroll back | Forward-only progression, full transcript visible |
| 13 | Verdicts | Contextual next step | Arc only works with guided handoff |
| 14 | Crystal filter | Generate then filter (LLM tags, code suppresses) | Auditable, deterministic enforcement |
| 15 | P7-P8 bypass | Pre-LLM grep, always surface | Voice protection, not formalization |
| 16 | P9 register | LLM-classified as voice_protection | Contextual check, not deterministic |

---

## 7. External Integration Contracts (Anthropic API)

### Client Pattern
```typescript
// lib/ai/client.ts
import Anthropic from '@anthropic-ai/sdk';

let client: Anthropic | null = null;

export function getClient(): Anthropic {
  if (!client) {
    client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return client;
}

export function hasApiKey(): boolean {
  return !!process.env.ANTHROPIC_API_KEY;
}

export const MODELS = {
  OPUS: 'claude-opus-4-6' as const,
} as const;
```

### API Call Pattern (Every Route)
1. Check `hasApiKey()`. If false, return mock response.
2. Construct system prompt from prompt template + fingerprint + project calibration + session context.
3. Call API with 30-second AbortController timeout (longer than ethics toolkit's 15s because Council responses are longer).
4. Validate response against Zod schema.
5. If validation fails, return raw text with `schema_validation_failed: true` flag.
6. On timeout or API error, return mock response with `is_mock: true` flag.

### Prompt Caching
- Use Anthropic prompt caching for the system prompt portion (voice persona + framework rules).
- Cache is per-session (voice templates are static within a session).
- Accept that cache may drop between user inputs (5-min TTL). Full context reconstruction on every call.

### Cost Estimate
- Opus 4.6 pricing with prompt caching.
- Per full Standard Council session (5 voices + user responses, ~10 API calls): estimated $2-5 with caching.
- Per Editor session (1-2 API calls depending on document length): estimated $1-3.
- Beta cohort of 5-15 users: manageable.

---

## 8. Prompt Templates & Context Assembly

### Context Assembly Pattern
Every API call assembles context from these sources (in order):

```
System prompt:
  1. Voice persona (from prompt template)
  2. Framework rules (never rewrite, identification not declaration, etc.)
  3. User's Phase 0 fingerprint (from database)
  4. Project calibration (from database)

User messages:
  5. Session transcript so far (structured, from database)
  6. Current user input (free text)
  7. Draft text (for Standard Council and Editor, from draft_versions)
```

### Prompt Templates (One Per Voice/Beat)
Each voice needs a prompt template that includes:
- The voice's persona and mandate (from WRC v1.4 framework)
- The framework's rules (never rewrite, identification not declaration)
- Question shapes the voice draws from (from v1.4)
- What the voice never does (from v1.4)
- Output format instructions (structured JSON + prose)

Templates stored in `lib/prompts/` as TypeScript template literal functions that accept fingerprint, project, and session context.

### Golden Transcript Regression
- 5 golden transcripts recorded in Claude Projects serve as quality baselines.
- For each voice, define 2-3 input/output pairs as regression fixtures.
- Minimum quality bar: Contrarian's verb catch must land. Champion must identify, not declare.
- Fixtures stored in `lib/prompts/__fixtures__/` and run as part of Phase 3 gate.

---

## 9. Rate Limiting

**In-memory Map does NOT work on Vercel serverless** (resets on cold starts, not shared across instances). Use Supabase-based counter for per-user limits on expensive AI routes. In-memory Map acceptable for per-IP burst protection on cheap routes.

| Route Pattern | Limit | Scope | Storage |
|--------------|-------|-------|---------|
| `/api/ai/*` | 10 req/hour, 50 req/day | User | Supabase `rate_limits` table |
| `/api/editor/*` | 5 req/hour, 25 req/day | User | Supabase `rate_limits` table |
| All other `/api/*` | 60 req/min | IP | In-memory Map (best-effort) |

```sql
-- Include in Migration 001 (database agent creates this alongside other tables)
CREATE TABLE rate_limits (
  user_id UUID NOT NULL REFERENCES profiles(id),
  route_pattern TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  request_count INTEGER DEFAULT 1,
  PRIMARY KEY (user_id, route_pattern, window_start)
);
```

Response on limit: HTTP 429 with `{ "error": "rate_limited", "retryAfter": <seconds> }`.

**Daily cost circuit breaker:** If total AI API calls across all users exceed 500/day, disable AI routes and return mock responses. Prevents runaway costs during beta.

---

## 10. Autopilot Phasing Strategy

### Phase 1: Foundation (3 agents, days 1-3)

**Scope:**
- Next.js 15 scaffolding with App Router
- Supabase setup (schema, RLS, RPC functions from Section 3)
- Magic link auth flow
- Phase 0 onboarding UI (8 inputs across user-level questions)
- Project creation + project-level calibration
- App shell with dashboard (mode selector)
- Scoring Floor check API

**Gate:** User can sign up via magic link, complete Phase 0 (all 8 inputs), create a project with calibration, see the mode selector dashboard. Scoring Floor check returns pass/fail.

### Phase 2: Editor (4 agents, days 4-14)

**Pre-gate 2.0 (1 agent):** Zod schemas for ALL modes (fingerprint, seed council, standard council, RWP, editor) plus fixture tests. All TypeScript types match SQL schema. MUST pass before Phase 2 agents start.

**Scope:**
- Paste text input with document rendering
- Pre-LLM deterministic pass (P7 em-dash grep, P8 banned vocab matching)
- LLM analysis pass (principles 1-6, 9, 11-15) with Crystal filter classification
- Inline annotation system (highlights with popover showing principle, flag, question)
- Accept/reject UI with editable-on-accept behavior
- Decision trail storage (atomic via RPC)
- Signature learning (weighted principle profile)
- Signature dashboard (empty state with Phase 0 echo, active state with principle rates)
- Mock mode for LLM (returns valid EditorAnalysisResponse)

**Gate:** Paste a document, receive inline annotations (including pre-LLM P7/P8 flags), Crystal filter correctly suppresses voice_formalization suggestions, accept/reject works with decision logging, signature dashboard shows logged decisions. Mock mode works without API key. Classification test cases (10-15 golden examples) pass at >80% accuracy.

### Phase 3: Council Modes (4 agents, days 15-24)

**Scope:**
- Seed Council Mode (coaxing prompt, micro-interview, 5-beat sequence with streaming)
- Standard Council (5 voices in sequence with streaming, verdict system, contextual handoff)
- Returning Writer Protocol (reads previous session, runs 5-voice council, new verdict)
- Prompt templates per voice/beat constructed from v1.4 framework
- Session transcript storage as structured JSONB
- Read-only scroll back for session history
- Verdict handoff UX (contextual next steps per verdict type)
- Golden transcript regression (2-3 fixtures per voice)

**Gate:** Run each mode end-to-end. Seed produces named intent + unanswerable question + closing handoff. Standard produces verdict with central question, revision map, and contextual handoff. RWP reads previous verdict and evaluates new draft. Golden transcript regression fixtures pass (verb catch lands, identification not declaration holds). Scoring Floor activates correctly when intake is too weak. Streaming responses feel like characters speaking, not text rendering.

### Phase 4: Polish + Demo Prep (2 agents, days 25-28)

**Scope:**
- Signature dashboard polish (compounding indicators, Crystal filter suppression count display)
- Alex's own data pre-loaded (essay editing sessions for demo)
- Demo flow rehearsal path (Seed Council live + Editor pre-loaded)
- Edge cases and error handling (mid-session API failure, malformed LLM output)
- UX polish (loading states, transitions between modes, responsive layout)
- Beta whitelist management (admin route for adding emails)
- Export text functionality

**Gate:** Full app functional. Alex's demo data loaded. All four modes operational. Signature dashboard readable with real data. Demo rehearsal completed at least once end-to-end.

**May 25 readiness gate:** If not ready by May 25, switch marketing to "early-access invite" language per the execution plan's fallback.

---

## 11. Swarm Execution Guardrails

### File Ownership
Each phase has explicit file ownership. Pre-merge gate: `git diff --name-only` against declared file list. Any out-of-scope edit fails.

### Bash Command Rules (MANDATORY for all agents)
```
DO NOT: cd /path && command       USE: full paths or git -C
DO NOT: source .venv/bin/activate USE: full venv paths
DO NOT: for x in ...; do done     USE: multiple individual Bash calls
DO NOT: echo "${variable}"        USE: Write tool for variable content
DO NOT: && or ; to chain          USE: one command per Bash call
```

### Verification Pipeline (after each phase merge)
1. Ownership gate (git diff --name-only)
2. Spec contract check (grep for exact export names, validate Zod schemas)
3. Cross-boundary wiring check (verify all exported functions have consumers)
4. Smoke test (start app, hit routes, verify status codes)
5. Test suite (run all Vitest tests)
6. Assembly-fix (1 retry per failure type, then escalate)

### Agent Strict Rules
1. Create ONLY files in assignment. No other files.
2. Use EXACT names from spec for functions, routes, classes, variables.
3. Do not make design decisions. Spec decides everything.
4. Do not import from other agents' files unless spec defines the import.
5. Follow directory structure exactly.
6. If spec is ambiguous, pick simplest interpretation.
7. Do not add features, comments, or extras beyond spec.
8. Write production-quality code. No TODOs, placeholders.
9. Create directories needed for files.
10. When done, commit all files with descriptive message.

---

## 12. Environment Variables

```bash
# Required in production
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
ANTHROPIC_API_KEY=
NEXT_PUBLIC_APP_URL=

# Optional (missing = mock/fallback mode)
# No email, no payments, no cron in beta v1
```

**Fallback mode:** Missing `ANTHROPIC_API_KEY` triggers mock mode for all LLM calls. Only `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_APP_URL` are required in dev.

---

## 13. Items Deferred to Post-Launch

- Multi-genre profile management or genre switching
- Email/business communication profile
- Subscription/payment mechanics (beta is free)
- Mobile-specific layouts
- Collaborative/multi-user features
- Voice generation or rewriting features
- Apprenticeship Simulator integration
- Group Seed Council variant
- Premise Pass vs Reckoning Pass as separate formal verdicts
- Selective voice deployment (partial council runs)
- Outline/Treatment Council mode
- Genre expansion (speeches/presentations)
- Full Tier 3-4 banned vocabulary expansion
- Concurrent session handling (optimistic locking)
- Error monitoring beyond console/Vercel logs

---

## Export Names Table

| File | Export | Consumers |
|------|--------|-----------|
| `lib/supabase/client.ts` | `createBrowserClient` | All client components, hooks |
| `lib/supabase/server.ts` | `createServerClient` | All API routes, middleware |
| `lib/ai/client.ts` | `getClient` | All AI API routes |
| `lib/ai/client.ts` | `hasApiKey` | All AI API routes (mock check) |
| `lib/ai/client.ts` | `MODELS` | All AI API routes |
| `lib/schemas/index.ts` | `TranscriptEntry` | All Council routes, project-flow components |
| `lib/schemas/index.ts` | `FingerprintInput` | Phase 0 routes, fingerprint components |
| `lib/schemas/index.ts` | `ScoringFloorResult` | Phase 0 routes |
| `lib/schemas/index.ts` | `ProjectCalibration` | Project routes |
| `lib/schemas/index.ts` | `SeedBeatResponse` | Seed Council routes |
| `lib/schemas/index.ts` | `SeedClosingHandoff` | Seed Council routes |
| `lib/schemas/index.ts` | `CouncilVoiceResponse` | Standard Council routes, RWP routes |
| `lib/schemas/index.ts` | `CouncilVerdict` | Standard Council routes, RWP routes |
| `lib/schemas/index.ts` | `RWPContext` | RWP routes |
| `lib/schemas/index.ts` | `EditorSuggestion` | Editor routes, annotation components |
| `lib/schemas/index.ts` | `EditorAnalysisResponse` | Editor routes |
| `lib/ai/mock.ts` | `getMockSeedBeat` | Seed Council routes (mock mode) |
| `lib/ai/mock.ts` | `getMockVoiceResponse` | Standard Council routes (mock mode) |
| `lib/ai/mock.ts` | `getMockVerdict` | Standard Council routes (mock mode) |
| `lib/ai/mock.ts` | `getMockEditorAnalysis` | Editor routes (mock mode) |
| `lib/editor/deterministic.ts` | `runDeterministicPass` | Editor routes (P7/P8 grep) |
| `lib/editor/vocabulary.ts` | `BANNED_VOCABULARY` | deterministic.ts |
| `lib/prompts/seed.ts` | `buildSeedBeatPrompt` | Seed Council routes |
| `lib/prompts/council.ts` | `buildVoicePrompt` | Standard Council routes, RWP routes |
| `lib/prompts/editor.ts` | `buildEditorPrompt` | Editor routes |
| `lib/prompts/phase0.ts` | `buildScoringFloorPrompt` | Phase 0 routes |
| `lib/rate-limit.ts` | `withRateLimit` | All API routes |
| `lib/auth/middleware.ts` | `authMiddleware` | middleware.ts |

---

## Cross-Boundary Wiring Section

| Function | Created By | Called By | When In Flow |
|----------|-----------|-----------|--------------|
| `createBrowserClient()` | auth agent | All client components | On component mount |
| `createServerClient()` | auth agent | All API routes | Start of every route handler |
| `runDeterministicPass()` | editor-deterministic agent | editor-api agent | Before LLM analysis in Editor |
| `buildSeedBeatPrompt()` | prompts agent | seed-api agent | Per beat in Seed Council |
| `buildVoicePrompt()` | prompts agent | council-api agent | Per voice in Standard Council |
| `buildEditorPrompt()` | prompts agent | editor-api agent | LLM analysis call |
| `update_signature_after_decision()` | database agent | editor-api agent | After accept/reject |
| `withRateLimit()` | rate-limit agent | All API routes | Top of every route handler |
| `getMockSeedBeat()` | mock agent | seed-api agent | When hasApiKey() = false |
| `getMockEditorAnalysis()` | mock agent | editor-api agent | When hasApiKey() = false |

---

## Data Ownership Table

| Table | Writer | Reader(s) |
|-------|--------|-----------|
| `profiles` | auth module | All modules |
| `fingerprints` | phase0 module | council, editor, signature dashboard |
| `projects` | project module | All modules |
| `draft_versions` | project module (paste text) | council, editor, RWP |
| `council_sessions` | council module | RWP module, project view, session history |
| `editor_sessions` | editor module | signature dashboard |
| `editor_suggestions` | editor module | signature dashboard, annotation UI |
| `editorial_signatures` | editor module (via RPC) | signature dashboard |

---

## Swarm Agent Assignment

### Phase 1: Foundation (3 agents)

#### Agent 1: `scaffold-auth`
| | |
|---|---|
| **Spec sections** | 1, 2, 6, 12 |
| **Creates** | `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/globals.css`, `src/app/auth/callback/route.ts`, `src/app/(app)/layout.tsx`, `src/app/(app)/dashboard/page.tsx`, `src/middleware.ts`, `src/lib/supabase/client.ts`, `src/lib/supabase/server.ts`, `src/lib/supabase/middleware.ts`, `src/lib/auth/middleware.ts`, `next.config.ts`, `tailwind.config.ts`, `tsconfig.json`, `package.json`, `.env.example` |
| **Reads** | None (first agent) |

#### Agent 2: `database`
| | |
|---|---|
| **Spec sections** | 3 |
| **Creates** | `supabase/migrations/001_core_schema.sql`, `supabase/migrations/002_rls_policies.sql`, `supabase/migrations/003_rpc_functions.sql`, `supabase/migrations/004_seed_data.sql`, `src/types/database.ts` |
| **Reads** | None |

#### Agent 3: `phase0-ui`
| | |
|---|---|
| **Spec sections** | 4.1 |
| **Creates** | `src/app/(app)/onboarding/page.tsx`, `src/app/(app)/onboarding/components/FingerprintForm.tsx`, `src/app/(app)/onboarding/components/ScoringFloorCheck.tsx`, `src/app/(app)/projects/new/page.tsx`, `src/app/(app)/projects/new/components/ProjectForm.tsx`, `src/app/api/phase0/fingerprint/route.ts`, `src/app/api/phase0/scoring-floor/route.ts`, `src/app/api/projects/route.ts`, `src/lib/prompts/phase0.ts` |
| **Reads** | `lib/supabase/server.ts`, `types/database.ts`, `lib/ai/client.ts` (NOTE: lib/ai/client.ts does not exist in Phase 1. Phase0-ui agent must create a minimal version with `hasApiKey()` + mock fallback. Phase 2 editor-core agent will replace it with the full version.) |

### Phase 2: Editor (4 agents)

#### Agent 2.0: `schemas` (PRE-GATE)
| | |
|---|---|
| **Spec sections** | 4.1-4.6 (all Zod schemas) |
| **Creates** | `src/lib/schemas/fingerprint.ts`, `src/lib/schemas/transcript.ts`, `src/lib/schemas/seed-council.ts`, `src/lib/schemas/standard-council.ts`, `src/lib/schemas/rwp.ts`, `src/lib/schemas/editor.ts`, `src/lib/schemas/index.ts`, `src/lib/schemas/__tests__/schemas.test.ts` |
| **Reads** | `types/database.ts` |

#### Agent 2.1: `editor-core`
| | |
|---|---|
| **Spec sections** | 4.5, 7 |
| **Creates** | `src/lib/editor/deterministic.ts`, `src/lib/editor/vocabulary.ts`, `src/lib/ai/client.ts`, `src/lib/ai/mock.ts`, `src/lib/prompts/editor.ts`, `src/lib/rate-limit.ts`, `src/app/api/editor/analyze/route.ts`, `src/app/api/editor/decide/route.ts` |
| **Reads** | `lib/schemas/index.ts`, `lib/supabase/server.ts`, `types/database.ts` |

#### Agent 2.2: `editor-ui`
| | |
|---|---|
| **Spec sections** | 4.5 |
| **Creates** | `src/app/(app)/projects/[id]/editor/page.tsx`, `src/app/(app)/projects/[id]/editor/components/DocumentView.tsx`, `src/app/(app)/projects/[id]/editor/components/InlineAnnotation.tsx`, `src/app/(app)/projects/[id]/editor/components/SuggestionPopover.tsx`, `src/app/(app)/projects/[id]/editor/components/PasteInput.tsx`, `src/components/ui/Button.tsx`, `src/components/ui/TextArea.tsx` |
| **Reads** | `lib/schemas/index.ts`, `lib/supabase/client.ts` |

#### Agent 2.3: `signature-dashboard`
| | |
|---|---|
| **Spec sections** | 4.6 |
| **Creates** | `src/app/(app)/signature/page.tsx`, `src/app/(app)/signature/components/SignatureOverview.tsx`, `src/app/(app)/signature/components/PrincipleChart.tsx`, `src/app/(app)/signature/components/DecisionHistory.tsx`, `src/app/(app)/signature/components/EmptyState.tsx`, `src/app/api/signature/route.ts` |
| **Reads** | `lib/schemas/index.ts`, `lib/supabase/server.ts`, `lib/supabase/client.ts`, `types/database.ts` |

### Phase 3: Council Modes (4 agents)

#### Agent 3.1: `council-prompts`
| | |
|---|---|
| **Spec sections** | 8 |
| **Creates** | `src/lib/prompts/seed.ts`, `src/lib/prompts/council.ts`, `src/lib/prompts/shared-rules.ts`, `src/lib/prompts/__fixtures__/seed-fixtures.ts`, `src/lib/prompts/__fixtures__/council-fixtures.ts`, `src/lib/prompts/__tests__/regression.test.ts` |
| **Modifies** | `src/lib/prompts/phase0.ts` (created in Phase 1 as minimal version, Phase 3 replaces with full implementation including golden transcript-calibrated prompts) |
| **Reads** | `lib/schemas/index.ts`, `lib/ai/client.ts` |

#### Agent 3.2: `seed-council`
| | |
|---|---|
| **Spec sections** | 4.2 |
| **Creates** | `src/app/(app)/projects/[id]/seed/page.tsx`, `src/app/(app)/projects/[id]/seed/components/CoaxingPrompt.tsx`, `src/app/(app)/projects/[id]/seed/components/MicroInterview.tsx`, `src/app/(app)/projects/[id]/seed/components/BeatView.tsx`, `src/app/(app)/projects/[id]/seed/components/ClosingHandoff.tsx`, `src/app/api/council/seed/route.ts` |
| **Reads** | `lib/schemas/index.ts`, `lib/prompts/seed.ts`, `lib/ai/client.ts`, `lib/ai/mock.ts`, `lib/supabase/server.ts`, `lib/supabase/client.ts` |

#### Agent 3.3: `standard-council-rwp`
| | |
|---|---|
| **Spec sections** | 4.3, 4.4 |
| **Creates** | `src/app/(app)/projects/[id]/council/page.tsx`, `src/app/(app)/projects/[id]/council/components/VoiceView.tsx`, `src/app/(app)/projects/[id]/council/components/VerdictDisplay.tsx`, `src/app/(app)/projects/[id]/council/components/HandoffActions.tsx`, `src/app/(app)/projects/[id]/council/components/SessionTranscript.tsx`, `src/app/(app)/projects/[id]/rwp/page.tsx`, `src/app/api/council/standard/route.ts`, `src/app/api/council/rwp/route.ts` |
| **Reads** | `lib/schemas/index.ts`, `lib/prompts/council.ts`, `lib/ai/client.ts`, `lib/ai/mock.ts`, `lib/supabase/server.ts`, `lib/supabase/client.ts` |

#### Agent 3.4: `project-flow`
| | |
|---|---|
| **Spec sections** | 4.3 (verdict handoff), 15 (session navigation) |
| **Creates** | `src/app/(app)/projects/[id]/page.tsx`, `src/app/(app)/projects/[id]/components/ProjectDashboard.tsx`, `src/app/(app)/projects/[id]/components/SessionHistory.tsx`, `src/app/(app)/projects/[id]/components/HandoffState.tsx`, `src/app/(app)/projects/[id]/components/ModeSelector.tsx` |
| **Reads** | `lib/schemas/index.ts`, `lib/supabase/client.ts`, `types/database.ts` |

### Phase 4: Polish (2 agents)

#### Agent 4.1: `demo-prep`
| | |
|---|---|
| **Spec sections** | 10 (Phase 4 scope) |
| **Creates** | `src/app/api/admin/whitelist/route.ts`, `src/app/api/admin/seed-demo/route.ts`, `src/lib/demo/seed-data.ts`, `src/app/(app)/projects/[id]/editor/components/ExportButton.tsx` |
| **Reads** | `lib/supabase/server.ts`, `types/database.ts` |

#### Agent 4.2: `polish`
| | |
|---|---|
| **Spec sections** | 1 (guardrails), 10 (Phase 4 scope) |
| **Creates** | `src/app/(app)/components/LoadingStates.tsx`, `src/app/(app)/components/ErrorBoundary.tsx`, `src/app/(app)/components/Navigation.tsx` |
| **Modifies** | `src/app/globals.css` (add annotation highlight colors, voice persona colors, custom Tailwind utilities) |
| **Reads** | `lib/supabase/client.ts` |

---

## Cross-Phase File Ownership Summary

| File/Directory | Owning Agent | Phase |
|---|---|---|
| `src/app/layout.tsx`, `src/middleware.ts`, `next.config.ts`, `package.json` | scaffold-auth | 1 |
| `src/lib/supabase/*` | scaffold-auth | 1 |
| `src/lib/auth/*` | scaffold-auth | 1 |
| `supabase/migrations/*` | database | 1 |
| `src/types/database.ts` | database | 1 |
| `src/app/(app)/onboarding/*`, `src/app/api/phase0/*`, `src/app/api/projects/*` | phase0-ui | 1 |
| `src/lib/schemas/*` | schemas | 2.0 |
| `src/lib/editor/*`, `src/lib/ai/*`, `src/lib/rate-limit.ts`, `src/app/api/editor/*` | editor-core | 2 |
| `src/lib/prompts/editor.ts` | editor-core | 2 |
| `src/app/(app)/projects/[id]/editor/*`, `src/components/ui/*` | editor-ui | 2 |
| `src/app/(app)/signature/*`, `src/app/api/signature/*` | signature-dashboard | 2 |
| `src/lib/prompts/seed.ts`, `src/lib/prompts/council.ts`, `src/lib/prompts/phase0.ts`, `src/lib/prompts/shared-rules.ts`, `src/lib/prompts/__fixtures__/*`, `src/lib/prompts/__tests__/*` | council-prompts | 3 |
| `src/app/(app)/projects/[id]/seed/*`, `src/app/api/council/seed/*` | seed-council | 3 |
| `src/app/(app)/projects/[id]/council/*`, `src/app/(app)/projects/[id]/rwp/*`, `src/app/api/council/standard/*`, `src/app/api/council/rwp/*` | standard-council-rwp | 3 |
| `src/app/(app)/projects/[id]/page.tsx`, `src/app/(app)/projects/[id]/components/*` | project-flow | 3 |
| `src/app/api/admin/*`, `src/lib/demo/*` | demo-prep | 4 |
| `src/app/(app)/components/*`, `src/app/globals.css` | polish | 4 |

---

## Acceptance Tests (EARS)

### Happy Path
- WHEN a user clicks the magic link THE SYSTEM SHALL create a profile and redirect to Phase 0 onboarding
- WHEN a user completes all 8 Phase 0 inputs THE SYSTEM SHALL store the fingerprint and redirect to the dashboard
- WHEN a user creates a project with calibration THE SYSTEM SHALL show the mode selector with Seed, Council, and Editor options
- WHEN a user starts Seed Council Mode THE SYSTEM SHALL run the coaxing prompt, micro-interview, and 5-beat sequence with streaming responses
- WHEN Beat 5 completes THE SYSTEM SHALL deliver the Closing Handoff with named intent and unanswerable question
- WHEN a user pastes text in the Editor THE SYSTEM SHALL run the deterministic pass (P7/P8) followed by LLM analysis and display inline annotations
- WHEN a user clicks Accept on an annotation THE SYSTEM SHALL clear the annotation, place cursor in the text, log the decision, and update the signature
- WHEN a user navigates to My Signature THE SYSTEM SHALL display their principle acceptance rates, total decisions, and suppression count
- WHEN the Standard Council delivers a Rewrite verdict THE SYSTEM SHALL display the central question, revision map, and prompt to submit a revised draft
- WHEN a returning writer submits a revision THE SYSTEM SHALL read the previous central question and verdict before running the 5-voice council

### Error Cases
- WHEN the Anthropic API is unreachable THE SYSTEM SHALL fall back to mock mode and display an indicator that responses are simulated
- WHEN the LLM returns malformed JSON THE SYSTEM SHALL store the raw text and flag schema_validation_failed without crashing
- WHEN a non-whitelisted email attempts login THE SYSTEM SHALL display the beta-only message
- WHEN the Scoring Floor check fails THE SYSTEM SHALL display the insufficient-intake message and prevent Council from running
- WHEN a user accepts a suggestion but makes no text changes THE SYSTEM SHALL log the decision as accept_no_edit

### Verification Commands
- `npm run dev` starts the app on localhost:3000
- `npm test` runs all Vitest tests
- `curl -s http://localhost:3000/api/phase0/scoring-floor -X POST -H "Content-Type: application/json" -d '{"writingSample":"test"}' | jq .passed` returns false (too short)
- Manual: complete Phase 0, create project, run Seed Council through Beat 5, verify Closing Handoff appears

---

## Feed-Forward

- **Hardest decision:** Opus 4.6 for all modes vs. tiered models. Chose Opus everywhere because the Contrarian's verb catch and Crystal Principle filtering are signature moments requiring Opus-level judgment. Cost is manageable for beta.
- **Rejected alternatives:** Chat-based interaction (enforcement logic on top), side-panel Editor (grammar checker feel), auto-detect for RWP (failure modes before May 30), parallel build tracks (integration seams fail per Run 033), prompt-to-suppress for Crystal filter (unreliable, non-auditable).
- **Least confident:** Two tied risks. (1) Inline annotation with editable-on-accept quality. Rich interactive UI that needs to feel satisfying. (2) Prompt porting from Claude Projects to API. Novel integration seam with no prior solution doc. Both should be verified first in their respective phases.
- **Key architectural split:** Editor has two processing passes. Pre-LLM deterministic (P7/P8 grep, zero tokens) + LLM judgment (P1-6, 9, 11-15 with Crystal filter). P9 goes through LLM but classified as voice_protection.
- **Prompt-porting risk:** v1.4 system prompt designed for Claude Projects. API porting requires golden transcripts, prompt templates, structured outputs, context assembly, and regression fixtures. Golden transcripts are a pre-build input, not a build artifact.

---

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-05-02-writers-room-council-app-brainstorm.md](docs/brainstorms/2026-05-02-writers-room-council-app-brainstorm.md)
- Key decisions carried forward: all 20 resolved decisions, 12 autopilot build requirements, 10 architectural constraints

### Internal References
- Ethics toolkit spec (format precedent): `docs/plans/2026-04-30-ethics-toolkit-platform-spec.md`
- Spec convergence loop: `docs/solutions/2026-04-30-spec-convergence-loop.md`
- Autopilot swarm orchestration: `docs/solutions/2026-04-09-autopilot-swarm-orchestration.md`

### External Source Materials
- WRC v1.4 framework: `~/Downloads/files/` (project instructions)
- Editor build brief v0.2: `~/Downloads/ai-human-editor-build-brief-v0.2.md`
- Core Voice document: `~/Projects/amplify-workshop/marketing/context/voice/core-voice.md`
- Golden transcripts: `~/Downloads/files/session-*.md`
