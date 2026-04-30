---
title: "AI Filmmaking Ethics Platform: Autopilot Spec Sheet"
date: 2026-04-30
status: spec
deadline: 2026-05-30
build_method: autopilot
swarm: true
brainstorm: docs/brainstorms/2026-04-30-ethics-toolkit-brainstorm.md
feed_forward:
  risk: "Autopilot swarm at platform complexity -- cross-cutting concerns (auth, realtime, LLM, payments, email) across 5 tools have never been tested at this scale"
  verify_first: true
---

# AI Filmmaking Ethics Platform: Autopilot Spec Sheet

**Target Model:** Claude Opus 4.6
**Execution Principle:** Opus 4.6 is a highly capable inferential model but is prone to overengineering and over-inferring unstated intent; therefore, this spec defines strict scope boundaries, explicit acceptance criteria, and rigid guardrails.

### Enhancement Summary

**Deepened on:** 2026-04-30
**Research agents used:** 8 (Supabase, Square/Resend, Architecture, Security, Data Integrity, Spec Flow, Performance, Vercel Deployment) + Learnings Researcher (6 solution docs)

**Key Patterns Applied from Prior Builds:**
1. Shared spec scales to 6 agents with 0 mismatches when prescriptive (lifecycle contracts, route manifests, ownership tables) -- validated in 10+ builds
2. Contract-check -> assembly-fix pipeline catches mechanical errors (wrong names, missing imports) but NOT design errors -- spec must be unambiguous
3. Cross-module writes work when spec defines: (a) who owns the table, (b) exact function signature with usage example, (c) transaction pattern
4. Zod validation at every LLM boundary prevents silent JSON corruption (producer-brief)
5. In-memory rate limiting Map prevents wallet-denial attacks without external infra (producer-brief)
6. `git -C <path>` not `cd && git` -- compound bash commands trigger security heuristics regardless of permissions

**New Territory (no prior solution docs):**
- Anonymous-to-auth identity flow (magic link session upgrade)
- Supabase Realtime for workshop sync (broadcast + persisted channels)
- Square checkout links + manual entitlement
- Resend lifecycle emails with Vercel Cron
- Service Worker caching for Next.js on Vercel

---

## 1. Global Platform Constraints & Guardrails

- **Legal Disclaimer:** ALL AI-generated and deterministic outputs must be explicitly labeled with "Guidance, not legal advice. Consult an entertainment attorney for legal counsel."
- **Offline Degradation:** Offline means deterministic-only mode.
  - Cached UI shell, Festival JSON, and Rate JSON must work without network.
  - Auth, LLM, Square, email, and realtime actions require network.
  - Network-dependent actions must show queued/retry/unavailable states. Never block the UI.
  - Offline mode must never block local deterministic tool use.
- **Mobile-First Attendee UX:**
  - Minimum 16pt body text.
  - Minimum 44pt tap targets.
  - Primary actions restricted to the bottom thumb zone.
  - Single-action per screen (one question, one tap, one result).
- **Data Privacy:** Render aggregated facilitator views only when at least 5 responses exist. Below 5: display "Waiting for more responses."
- **Model Access Preflight:** At startup (or deployment), check that Haiku 4.5 and Sonnet 4.6 are reachable. If unavailable:
  - App falls back to mock mode automatically.
  - User-facing UI shows deterministic output and "AI recommendation temporarily unavailable."
  - All tests must pass in mock mode without API keys.
- **CORS:** QR join uses same-origin app URLs only. No cross-origin attendee frontend is supported in v1.
- **Logging:** Log API errors to console/Vercel logs with `requestId`, route, `userId`/`anonymousSessionId` when available. Do not log project descriptions, disclosure text, or provenance notes.

---

## 2. Identity & Monetization Architecture

### Identity Flow (Option A)

- **Default State:** Anonymous. Users join via QR code or URL. Generate an ephemeral `anonymousSessionId` (UUID, stored in browser `localStorage`).
- **Server-Side Persistence:** Anonymous workshop tool outputs are stored server-side in `tool_events` keyed by `anonymousSessionId`, with no PII. This data is hard-deleted after 30 days if the user never converts.
- **Conversion State:** End-of-session prompt: "Want to keep your results?"
- **Authentication:** Magic Link email capture via Supabase Auth. On successful auth, the system claims all data for that `anonymousSessionId` into the authenticated `userId` by updating `anonymous_sessions.user_id` and all related `tool_events.user_id`.
- **Post-Conversion:** Data is now tied to the `userId` and persists until the user deletes their account.
- **Browser Storage:** Browser `localStorage` caches `anonymousSessionId` and last tool outputs for offline deterministic use. Server-side is the source of truth for conversion and entitlement.

### Monetization (Reverse Trial)

- **Trigger:** Email capture initiates a 14-day premium trial. See Section 8 for email scheduling.
- **Boundary Execution:** Do not gate core functionality or hide premium features. Display all features, but visually distinguish the "value gap" (e.g., showing template formats for free tier vs. AI-customized wording for premium).
- **Downgrade:** Execute graceful downgrade to the free tier strictly via UI when `trial_ends_at` is reached.
- **Pricing:** $15/mo subscription only. $49 one-time Project Export is deferred to post-launch evaluation.

### Facilitator Authentication

- Facilitator route `/facilitator` is protected by one env-configured password.
- `FACILITATOR_PASSWORD_HASH` is a **bcrypt** hash. Use `bcrypt.compare()` server-side.
- On successful comparison, set an `httpOnly`, `secure`, `sameSite=lax` cookie named `facilitator_session` with a signed value (e.g., JWT or HMAC-signed token using a server secret) and `maxAge: 86400` (24 hours).
- No attendee account can access facilitator routes.
- All facilitator API routes validate the `facilitator_session` cookie before processing.

---

## 3. Authoritative Database Schema

All tables live in Supabase (PostgreSQL). `profiles.user_id` references `auth.users(id)`. Do not modify Supabase `auth.users` directly.

```sql
-- User profiles (created on magic link auth)
CREATE TABLE profiles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  email_opt_out BOOLEAN DEFAULT false,
  trial_started_at TIMESTAMPTZ,
  trial_ends_at TIMESTAMPTZ,
  current_trial_id UUID, -- generated on conversion, used as idempotency key for email_jobs
  entitlement_status TEXT DEFAULT 'free'
    CHECK (entitlement_status IN ('free','trial','active','past_due','cancelled','expired')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Anonymous sessions (created on first app load)
CREATE TABLE anonymous_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  anonymous_session_id TEXT UNIQUE NOT NULL,
  user_id UUID REFERENCES profiles(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  claimed_at TIMESTAMPTZ -- set when user converts
);
CREATE INDEX idx_anon_sessions_unclaimed ON anonymous_sessions(created_at)
  WHERE user_id IS NULL; -- for 30-day cleanup

-- Workshop sessions (created by facilitator)
CREATE TABLE workshop_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_code TEXT UNIQUE NOT NULL, -- short code for QR join
  facilitator_id UUID REFERENCES profiles(user_id),
  started_at TIMESTAMPTZ DEFAULT now(),
  ended_at TIMESTAMPTZ,
  status TEXT DEFAULT 'active' CHECK (status IN ('active','ended'))
);

-- Tool events (all persisted tool outputs)
CREATE TABLE tool_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE NOT NULL, -- client-generated UUID for idempotency
  schema_version INTEGER DEFAULT 1,
  workshop_session_id UUID REFERENCES workshop_sessions(id),
  anonymous_session_id TEXT NOT NULL REFERENCES anonymous_sessions(anonymous_session_id),
  user_id UUID REFERENCES profiles(user_id),
  tool_type TEXT NOT NULL CHECK (tool_type IN ('DISCLOSURE','RISK','PROVENANCE','BUDGET')),
  deterministic_payload JSONB NOT NULL,
  probabilistic_payload JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_tool_events_session ON tool_events(anonymous_session_id);
CREATE INDEX idx_tool_events_user ON tool_events(user_id) WHERE user_id IS NOT NULL;
-- Note: Festival Policy Lookup is read-only and does NOT create tool_events.

-- Festival policies (human-curated seed data)
CREATE TABLE festival_policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  festival_name TEXT NOT NULL,
  year INTEGER NOT NULL,
  ai_policy TEXT NOT NULL CHECK (ai_policy IN ('banned','restricted','disclosure_required','allowed','no_stated_policy')),
  policy_details TEXT NOT NULL,
  source_url TEXT NOT NULL,
  last_reviewed_date DATE NOT NULL,
  confidence_level TEXT NOT NULL CHECK (confidence_level IN ('verified','inferred','unverified')),
  categories TEXT[] NOT NULL, -- e.g. {'writing','music','vfx','voice'}
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(festival_name, year)
);

-- Workshop risk score aggregates (for realtime tool aggregation)
CREATE TABLE workshop_risk_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE NOT NULL,
  workshop_session_id UUID NOT NULL REFERENCES workshop_sessions(id),
  anonymous_session_id TEXT NOT NULL REFERENCES anonymous_sessions(anonymous_session_id),
  risk_tier TEXT NOT NULL CHECK (risk_tier IN ('low','medium','high','critical')),
  top_risk_departments TEXT[] NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Q&A questions
CREATE TABLE qna_questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE NOT NULL,
  workshop_session_id UUID NOT NULL REFERENCES workshop_sessions(id),
  anonymous_session_id TEXT NOT NULL REFERENCES anonymous_sessions(anonymous_session_id),
  question_text TEXT NOT NULL,
  upvote_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Q&A votes (one vote per session per question)
CREATE TABLE qna_votes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE NOT NULL,
  question_id UUID NOT NULL REFERENCES qna_questions(id) ON DELETE CASCADE,
  anonymous_session_id TEXT NOT NULL REFERENCES anonymous_sessions(anonymous_session_id),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(question_id, anonymous_session_id) -- enforce one vote per user per question
);

-- Processed events (idempotency for realtime)
CREATE TABLE processed_events (
  event_id TEXT PRIMARY KEY,
  anonymous_session_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Square entitlements
CREATE TABLE square_entitlements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID UNIQUE NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
  square_customer_id TEXT,
  square_subscription_id TEXT,
  square_payment_id TEXT,
  current_period_ends_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Email jobs
CREATE TABLE email_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
  email_type TEXT NOT NULL CHECK (email_type IN ('welcome','day12_warning','day14_downgrade')),
  trial_id UUID,
  scheduled_for TIMESTAMPTZ NOT NULL,
  sent_at TIMESTAMPTZ,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending','sent','failed','skipped')),
  idempotency_key TEXT UNIQUE NOT NULL, -- format: {userId}:{emailType}:{trialId}
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_email_jobs_pending ON email_jobs(scheduled_for) WHERE status = 'pending';
```

### RLS Rules (Supabase Row Level Security)

- Anonymous users (no auth): can INSERT into `anonymous_sessions`, `tool_events`, `workshop_risk_scores`, `qna_questions`, `qna_votes`, `processed_events` using their `anonymousSessionId`.
- Anonymous users: can SELECT their own rows from `tool_events`, `qna_questions` (filtered by `anonymous_session_id`).
- Authenticated users: can SELECT/UPDATE their own `profiles` row, SELECT their own `tool_events`, `square_entitlements`.
- `festival_policies`: SELECT open to all (public read). INSERT/UPDATE restricted to service role (admin).
- `email_jobs`: no client access. Service role only (cron job).
- `workshop_sessions`: INSERT restricted to facilitator role. SELECT open to all (needed for QR join validation).

---

## 4. Core Workflow Contracts (The 5 Tools)

Agents must strictly separate deterministic data handling from probabilistic LLM generation to control costs and latency.

### Tool 1: AI Disclosure Generator

- **Zod Input Schema:**
  ```typescript
  const DisclosureInput = z.object({
    projectTitle: z.string().min(1).max(200),
    aiUsageAreas: z.array(z.object({
      department: z.enum(['writing','music','vfx','voice','storyboard','editing','sound_design','colorist','other']),
      description: z.string().min(1).max(500),
      toolsUsed: z.array(z.string().min(1)).min(1),
      usageLevel: z.enum(['assistive','generative']),
      humanSupervisor: z.string().max(200).optional(),
      trainingDataAcknowledged: z.boolean().default(false),
      consentDocumented: z.boolean().default(false),
      compensationNotes: z.string().max(500).optional(),
      unionComplianceChecked: z.boolean().default(false)
    })).min(1),
    distributionTargets: z.array(z.string()).optional(),
    unionStatus: z.enum(['sag_aftra','wga','iatse','non_union','unknown'])
  });
  ```
- **Deterministic Output:**
  ```typescript
  const DisclosureOutput = z.object({
    checklist: z.array(z.object({
      item: z.string(),
      satisfied: z.boolean(),
      requirement: z.string()
    })),
    disclosureFields: z.object({
      projectTitle: z.string(),
      departments: z.array(z.string()),
      toolsUsed: z.array(z.string()),
      unionStatus: z.string(),
      generatedAt: z.string()
    }),
    templateText: z.string() // deterministic template with placeholders
  });
  ```
- **Exact Checklist Items:**
  1. `{ item: "AI tools identified", requirement: "List every AI tool used by name and version" }`
  2. `{ item: "Departments disclosed", requirement: "Identify which departments used AI (writing, music, VFX, etc.)" }`
  3. `{ item: "Usage level specified", requirement: "For each department, state whether AI was assistive or generative" }`
  4. `{ item: "Human oversight documented", requirement: "Name the human who supervised/approved each AI output" }`
  5. `{ item: "Training data acknowledged", requirement: "Note whether AI models were trained on copyrighted material" }`
  6. `{ item: "Consent obtained", requirement: "If voice/likeness AI was used, document consent from all parties" }`
  7. `{ item: "Compensation addressed", requirement: "If AI replaced a human role, document fair compensation considerations" }`
  8. `{ item: "Union compliance checked", requirement: "Verify AI usage complies with applicable union agreements" }`
- **Probabilistic Output (Haiku 4.5):** Natural language disclosure statement. Zod schema:
  ```typescript
  const DisclosureAI = z.object({ disclosureText: z.string().min(50).max(2000) });
  ```
- **Free Tier:** Shows checklist + template structure. AI wording placeholder: "Upgrade to generate custom disclosure language."
- **Premium:** Full AI-generated disclosure wording.
- **Error States:** Missing required fields -> inline validation. LLM failure -> show deterministic template with "AI wording unavailable."
- **Stored in ToolEvent:** Yes. `deterministicPayload` = DisclosureOutput, `probabilisticPayload` = disclosure text string.
- **Fixture:**
  ```json
  {
    "input": {
      "projectTitle": "Midnight Signal",
      "aiUsageAreas": [
        { "department": "music", "description": "Background score generated from text prompts", "toolsUsed": ["Suno v4"], "usageLevel": "generative", "trainingDataAcknowledged": false, "consentDocumented": false, "unionComplianceChecked": false },
        { "department": "storyboard", "description": "Initial frame sketches from scene descriptions", "toolsUsed": ["Midjourney v6"], "usageLevel": "assistive", "humanSupervisor": "Jane Park", "trainingDataAcknowledged": false, "consentDocumented": false, "unionComplianceChecked": false }
      ],
      "distributionTargets": ["Sundance", "SXSW"],
      "unionStatus": "non_union"
    },
    "expectedOutput": {
      "checklist": [
        { "item": "AI tools identified", "satisfied": true, "requirement": "List every AI tool used by name and version" },
        { "item": "Departments disclosed", "satisfied": true, "requirement": "Identify which departments used AI" },
        { "item": "Usage level specified", "satisfied": true, "requirement": "For each department, state whether AI was assistive or generative" },
        { "item": "Human oversight documented", "satisfied": false, "requirement": "Name the human who supervised/approved each AI output" },
        { "item": "Training data acknowledged", "satisfied": false, "requirement": "Note whether AI models were trained on copyrighted material" },
        { "item": "Consent obtained", "satisfied": true, "requirement": "If voice/likeness AI was used, document consent from all parties" },
        { "item": "Compensation addressed", "satisfied": false, "requirement": "If AI replaced a human role, document fair compensation considerations" },
        { "item": "Union compliance checked", "satisfied": true, "requirement": "Verify AI usage complies with applicable union agreements" }
      ],
      "_satisfaction_trace": [
        "Item 1: true — both items have non-empty toolsUsed",
        "Item 2: true — aiUsageAreas has 2 items",
        "Item 3: true — both items have usageLevel set",
        "Item 4: false — music item has no humanSupervisor",
        "Item 5: false — both items have trainingDataAcknowledged = false",
        "Item 6: true — no voice department listed",
        "Item 7: false — music item has usageLevel 'generative' but no compensationNotes",
        "Item 8: true — unionStatus is 'non_union'"
      ]
      ]
    }
  }
  ```
  - `satisfied` logic (references explicit fields on each `aiUsageAreas` item):
    1. "AI tools identified" — satisfied if every item has a non-empty `toolsUsed` array.
    2. "Departments disclosed" — satisfied if `aiUsageAreas` has at least one item.
    3. "Usage level specified" — satisfied if every item has `usageLevel` set.
    4. "Human oversight documented" — satisfied if every item has a non-empty `humanSupervisor`.
    5. "Training data acknowledged" — satisfied if every item has `trainingDataAcknowledged === true`.
    6. "Consent obtained" — satisfied if no `voice` department is listed, OR every `voice` item has `consentDocumented === true`.
    7. "Compensation addressed" — satisfied if every item with `usageLevel === 'generative'` has a non-empty `compensationNotes`.
    8. "Union compliance checked" — satisfied if `unionStatus` is `non_union` or `unknown`, OR every item has `unionComplianceChecked === true`.

### Tool 2: Festival Policy Lookup

- **Input Schema:**
  ```typescript
  const PolicyLookupInput = z.object({
    query: z.string().min(1).max(500),
    filters: z.object({
      aiPolicy: z.enum(['banned','restricted','disclosure_required','allowed','no_stated_policy']).optional(),
      category: z.enum(['writing','music','vfx','voice','full_ban','no_policy']).optional()
    }).optional()
  });
  ```
- **Output:** Array of `FestivalPolicy` records (see database schema). Paginated, 20 per page.
- **Search:** Case-insensitive substring match on `festival_name` and `policy_details`. Filter by `ai_policy` and `categories` (array contains).
- **No LLM. Fully free. No free/paid boundary.**
- **Not stored in ToolEvent.** Read-only, stateless.
- **Error States:** No results -> "No matching festivals found." Empty database -> "Festival data is loading."
- **Seed Data (12 records, insert during Phase 2):**

  ```json
  [
    { "festivalName": "Cannes Film Festival", "year": 2026, "aiPolicy": "banned", "policyDetails": "Generative AI for scripting, visuals, or performances makes films ineligible for the Palme d'Or and Official Competition. Technical AI (sound restoration, VFX cleanup) still allowed.", "sourceUrl": "https://www.festival-cannes.com/en/rules", "lastReviewedDate": "2026-04-15", "confidenceLevel": "verified", "categories": ["writing","music","vfx","voice"] },
    { "festivalName": "TIFF (Toronto International Film Festival)", "year": 2026, "aiPolicy": "disclosure_required", "policyDetails": "Must disclose which components use AI. Failure may result in disqualification.", "sourceUrl": "https://www.tiff.net/submissions", "lastReviewedDate": "2026-04-15", "confidenceLevel": "verified", "categories": ["writing","music","vfx","voice"] },
    { "festivalName": "Sundance Film Festival", "year": 2026, "aiPolicy": "disclosure_required", "policyDetails": "Ask how you used AI on submission form. Treated as research data, not gatekeeping. Voluntary but strongly encouraged.", "sourceUrl": "https://www.sundance.org/festivals/sundance-film-festival/submit", "lastReviewedDate": "2026-04-15", "confidenceLevel": "verified", "categories": ["writing","music","vfx","voice"] },
    { "festivalName": "Berlinale (Berlin International Film Festival)", "year": 2026, "aiPolicy": "disclosure_required", "policyDetails": "Asks about AI usage in submission. Treats disclosure as informational, not disqualifying.", "sourceUrl": "https://www.berlinale.de/en/festival/programme/submission.html", "lastReviewedDate": "2026-04-15", "confidenceLevel": "verified", "categories": ["writing","music","vfx","voice"] },
    { "festivalName": "SXSW Film & TV Festival", "year": 2026, "aiPolicy": "disclosure_required", "policyDetails": "Requires disclosure of AI usage in submission materials. No blanket ban.", "sourceUrl": "https://www.sxsw.com/film/submissions/", "lastReviewedDate": "2026-04-15", "confidenceLevel": "inferred", "categories": ["writing","music","vfx","voice"] },
    { "festivalName": "Venice Film Festival", "year": 2026, "aiPolicy": "no_stated_policy", "policyDetails": "No explicit AI policy published as of last review. Check current submission guidelines.", "sourceUrl": "https://www.labiennale.org/en/cinema", "lastReviewedDate": "2026-04-15", "confidenceLevel": "unverified", "categories": [] },
    { "festivalName": "Tribeca Festival", "year": 2026, "aiPolicy": "disclosure_required", "policyDetails": "Asks about AI/immersive technology usage. Has dedicated immersive/new media category.", "sourceUrl": "https://tribecafilm.com/festival/submissions", "lastReviewedDate": "2026-04-15", "confidenceLevel": "inferred", "categories": ["writing","music","vfx","voice"] },
    { "festivalName": "CREDO 23 / No AI Allowed Festival", "year": 2026, "aiPolicy": "banned", "policyDetails": "Strictly human-made films only. Founded by Justine Bateman, Reed Morano, Matthew Weiner, Juliette Lewis. Zero tolerance for any AI-generated content.", "sourceUrl": "https://www.noaiallowed.com", "lastReviewedDate": "2026-04-15", "confidenceLevel": "verified", "categories": ["writing","music","vfx","voice"] },
    { "festivalName": "Sato48 Springfield", "year": 2026, "aiPolicy": "restricted", "policyDetails": "AI may be used for pre-production and planning only. Final deliverable must be human-created.", "sourceUrl": "https://sato48.com/rules", "lastReviewedDate": "2026-04-15", "confidenceLevel": "verified", "categories": ["writing","storyboard"] },
    { "festivalName": "Cannes Lions (Advertising)", "year": 2026, "aiPolicy": "disclosure_required", "policyDetails": "Mandatory disclosure of AI components in advertising entries. Failure may result in disqualification.", "sourceUrl": "https://www.canneslions.com/enter/rules", "lastReviewedDate": "2026-04-15", "confidenceLevel": "verified", "categories": ["writing","music","vfx","voice"] },
    { "festivalName": "48 Hour Film Project", "year": 2026, "aiPolicy": "restricted", "policyDetails": "AI-generated music rules under active review. Policy being escalated to global HQ. Check local chapter rules.", "sourceUrl": "https://www.48hourfilm.com/rules", "lastReviewedDate": "2026-04-27", "confidenceLevel": "inferred", "categories": ["music"] },
    { "festivalName": "San Diego Streaming Film Festival (SDSFF)", "year": 2026, "aiPolicy": "no_stated_policy", "policyDetails": "No explicit AI policy. Michael Howard (organizer) open to AI discussion. Alex delivered workshop April 4 and April 11.", "sourceUrl": "https://www.sdstreamingfilmfestival.com", "lastReviewedDate": "2026-04-11", "confidenceLevel": "verified", "categories": [] }
  ]
  ```

### Tool 3: Project Risk Scanner

- **Input Schema:**
  ```typescript
  const RiskScannerInput = z.object({
    projectType: z.enum(['feature','short','documentary','commercial','music_video','web_series']),
    budgetTier: z.enum(['student','indie','professional','studio']),
    departments: z.array(z.object({
      role: z.enum(['screenwriter','composer','vfx_artist','voice_actor','editor','sound_designer','colorist','storyboard_artist','director']),
      aiUsageLevel: z.enum(['none','assisted','generated']),
      description: z.string().max(500).optional()
    })).min(1),
    distributionType: z.enum(['none','online','indie_festival','major_festival','broadcast_theatrical']),
    unionAffiliation: z.enum(['sag_aftra','wga','iatse','non_union','mixed'])
  });
  ```
- **Deterministic Scoring -- Executable Formulas:**

  **Step 1: Per-department base points**

  | aiUsageLevel | Points |
  |-------------|--------|
  | none | 0 |
  | assisted | 1 |
  | generated | 3 |

  **Step 2: Role vulnerability multiplier**

  Roles are classified as front-of-camera (higher protection) or behind-camera (lower protection):

  | Role | Classification | Multiplier |
  |------|---------------|-----------|
  | voice_actor | front_of_camera | 1.5 |
  | screenwriter | behind_camera_high_visibility | 1.3 |
  | composer | behind_camera_low_visibility | 1.2 |
  | director | front_of_camera | 1.0 |
  | vfx_artist | behind_camera_low_visibility | 1.0 |
  | editor | behind_camera_low_visibility | 1.0 |
  | sound_designer | behind_camera_low_visibility | 1.0 |
  | colorist | behind_camera_low_visibility | 0.8 |
  | storyboard_artist | behind_camera_low_visibility | 0.8 |

  `departmentScore = basePoints * roleMultiplier`

  **Step 3: Dimension raw scores**

  - `legalRaw = sum(departmentScore for all departments)`
  - `ethicalRaw = sum(departmentScore for departments where role IN (voice_actor, composer, screenwriter))`
  - `reputationalRaw = sum(departmentScore for departments where aiUsageLevel = 'generated')`
  - `unionRaw = sum(departmentScore for departments where aiUsageLevel IN ('assisted', 'generated'))`

  **Step 4: Dimension multipliers**

  | Factor | Multiplier | Applied to |
  |--------|-----------|-----------|
  | unionAffiliation = sag_aftra or wga | 1.5x | unionRaw |
  | unionAffiliation = iatse or mixed | 1.3x | unionRaw |
  | unionAffiliation = non_union | 0.5x | unionRaw |
  | distributionType = major_festival or broadcast_theatrical | 1.5x | reputationalRaw |
  | distributionType = indie_festival | 1.2x | reputationalRaw |
  | distributionType = online or none | 1.0x | reputationalRaw |

  **Step 5: Normalize and weight**

  ```
  dimensionScore = clamp(round(rawScore * multiplier), 0, 10)
  totalScore = round(legal * 0.30 + ethical * 0.25 + reputational * 0.25 + union * 0.20)
  ```

  **Step 6: Tier mapping**

  | totalScore | Tier |
  |-----------|------|
  | 0-2 | low |
  | 3-5 | medium |
  | 6-7 | high |
  | 8-10 | critical |

  **Step 7: Per-department vulnerability flags**

  | departmentScore | Flag |
  |----------------|------|
  | 0 | safe |
  | 0.1-1.5 | caution |
  | 1.6-3.0 | warning |
  | 3.1+ | critical |

- **Deterministic Output:**
  ```typescript
  const RiskScannerOutput = z.object({
    totalScore: z.number().min(0).max(10),
    tier: z.enum(['low','medium','high','critical']),
    dimensions: z.object({
      legal: z.object({ raw: z.number(), multiplied: z.number(), score: z.number() }),
      ethical: z.object({ raw: z.number(), multiplied: z.number(), score: z.number() }),
      reputational: z.object({ raw: z.number(), multiplied: z.number(), score: z.number() }),
      union: z.object({ raw: z.number(), multiplied: z.number(), score: z.number() })
    }),
    departmentFlags: z.array(z.object({
      role: z.string(),
      flag: z.enum(['safe','caution','warning','critical']),
      score: z.number()
    }))
  });
  ```
- **Probabilistic Output (Sonnet 4.6):** Contextual mitigation recommendations. Zod schema:
  ```typescript
  const RiskAI = z.object({ recommendations: z.array(z.string().min(10).max(500)).min(1).max(10) });
  ```
- **Free Tier:** Tier (low/medium/high/critical) + department flags.
- **Premium:** Full dimension breakdown + AI recommendations.
- **Error States:** Missing required fields -> inline validation. LLM failure -> show deterministic score with "AI recommendations unavailable."
- **Stored in ToolEvent:** Yes.
- **Fixture:**
  ```json
  {
    "input": {
      "projectType": "feature",
      "budgetTier": "indie",
      "departments": [
        { "role": "composer", "aiUsageLevel": "generated" },
        { "role": "screenwriter", "aiUsageLevel": "assisted" },
        { "role": "vfx_artist", "aiUsageLevel": "none" }
      ],
      "distributionType": "major_festival",
      "unionAffiliation": "non_union"
    },
    "expectedOutput": {
      "totalScore": 4,
      "tier": "medium",
      "departmentFlags": [
        { "role": "composer", "flag": "critical", "score": 3.6 },
        { "role": "screenwriter", "flag": "caution", "score": 1.3 },
        { "role": "vfx_artist", "flag": "safe", "score": 0 }
      ]
    }
  }
  ```

### Tool 4: AI Provenance Chain Builder

- **Zod Input Schema:**
  ```typescript
  const ProvenanceInput = z.object({
    projectTitle: z.string().min(1).max(200),
    entries: z.array(z.object({
      department: z.string().min(1).max(100),
      taskDescription: z.string().min(1).max(500),
      attribution: z.enum(['human_made','ai_assisted','ai_generated']),
      toolUsed: z.string().max(200).optional(),
      humanContributor: z.string().max(200).optional(),
      notes: z.string().max(500).optional()
    })).min(1)
  });
  ```
- **Deterministic Output:**
  ```typescript
  const ProvenanceOutput = z.object({
    projectTitle: z.string(),
    entries: z.array(z.object({
      department: z.string(),
      taskDescription: z.string(),
      attribution: z.enum(['human_made','ai_assisted','ai_generated']),
      toolUsed: z.string().optional(),
      humanContributor: z.string().optional(),
      notes: z.string().optional()
    })),
    summary: z.object({
      totalEntries: z.number(),
      humanMade: z.number(),
      aiAssisted: z.number(),
      aiGenerated: z.number(),
      percentageHuman: z.number()
    }),
    generatedAt: z.string()
  });
  ```
- **No LLM integration.**
- **Free Tier:** 1 project, view only, no export.
- **Premium:** Unlimited projects + PDF export.
- **PDF Export Format (Premium):**
  - Library: `@react-pdf/renderer` (works in Next.js)
  - Filename: `provenance-chain-{projectTitle}-{date}.pdf`
  - Sections in order: (1) Header with project title + generation date + disclaimer, (2) Summary stats table, (3) Entry-by-entry provenance log as a table (Department | Task | Attribution | Tool | Human | Notes), (4) Footer with "Generated by Ethics Toolkit. Guidance, not legal advice."
- **Validation:** Duplicate detection: warn if same `department` + `taskDescription` combination exists. Do not block.
- **Error States:** Invalid entry -> inline validation per field. Export failure -> "PDF generation failed. Your data is saved."
- **Stored in ToolEvent:** Yes.
- **Fixture:**
  ```json
  {
    "input": {
      "projectTitle": "Midnight Signal",
      "entries": [
        { "department": "Music", "taskDescription": "Background score", "attribution": "ai_generated", "toolUsed": "Suno v4" },
        { "department": "Storyboard", "taskDescription": "Initial frame sketches", "attribution": "ai_assisted", "toolUsed": "Midjourney v6", "humanContributor": "Jane Park" },
        { "department": "Editing", "taskDescription": "Final cut assembly", "attribution": "human_made", "humanContributor": "Tom Rivera" }
      ]
    },
    "expectedOutput": {
      "summary": {
        "totalEntries": 3,
        "humanMade": 1,
        "aiAssisted": 1,
        "aiGenerated": 1,
        "percentageHuman": 33
      }
    }
  }
  ```
  - `percentageHuman` = `round((humanMade / totalEntries) * 100)` = `round((1/3) * 100)` = 33.

### Tool 5: Budget vs. Ethics Calculator

- **Zod Input Schema:**
  ```typescript
  const BudgetInput = z.object({
    role: z.enum(['composer','vfx_artist','storyboard_artist','screenwriter','voice_actor','editor','sound_designer','colorist']),
    budgetTier: z.enum(['student','indie','professional','studio']),
    projectScope: z.string().min(1).max(500),
    currentBudgetForRole: z.number().min(0).optional()
  });
  ```
- **Deterministic Output:**
  ```typescript
  const BudgetOutput = z.object({
    roleName: z.string(),
    budgetTier: z.string(),
    humanCostRange: z.object({ low: z.number(), high: z.number() }),
    unionMinimum: z.number().nullable(),
    displacementRisk: z.enum(['high','medium','low']),
    userBudgetDelta: z.object({ low: z.number(), high: z.number() }).nullable()
  });
  ```
- **Inline Rate Table (normalized from `docs/reports/031-film-crew-rates-ai-comparison.md`):**

  ```typescript
  const RATE_TABLE: Record<string, Record<string, { low: number; high: number; unionMin: number | null; displacementRisk: 'high' | 'medium' | 'low' }>> = {
    composer: {
      student: { low: 1500, high: 5000, unionMin: null, displacementRisk: 'high' },
      indie: { low: 2000, high: 25000, unionMin: null, displacementRisk: 'high' },
      professional: { low: 10000, high: 100000, unionMin: null, displacementRisk: 'medium' },
      studio: { low: 50000, high: 500000, unionMin: null, displacementRisk: 'low' }
    },
    vfx_artist: {
      student: { low: 500, high: 2000, unionMin: null, displacementRisk: 'high' },
      indie: { low: 5000, high: 25000, unionMin: null, displacementRisk: 'high' },
      professional: { low: 25000, high: 100000, unionMin: null, displacementRisk: 'medium' },
      studio: { low: 100000, high: 500000, unionMin: null, displacementRisk: 'low' }
    },
    storyboard_artist: {
      student: { low: 500, high: 2500, unionMin: null, displacementRisk: 'high' },
      indie: { low: 2500, high: 15000, unionMin: null, displacementRisk: 'high' },
      professional: { low: 5000, high: 30000, unionMin: null, displacementRisk: 'medium' },
      studio: { low: 15000, high: 50000, unionMin: null, displacementRisk: 'low' }
    },
    screenwriter: {
      student: { low: 500, high: 5000, unionMin: null, displacementRisk: 'medium' },
      indie: { low: 2500, high: 15000, unionMin: null, displacementRisk: 'medium' },
      professional: { low: 10000, high: 40000, unionMin: 77495, displacementRisk: 'medium' },
      studio: { low: 50000, high: 150000, unionMin: 147920, displacementRisk: 'low' }
    },
    voice_actor: {
      student: { low: 200, high: 500, unionMin: null, displacementRisk: 'high' },
      indie: { low: 500, high: 2000, unionMin: 249, displacementRisk: 'high' },
      professional: { low: 1000, high: 5000, unionMin: 810, displacementRisk: 'high' },
      studio: { low: 2000, high: 10000, unionMin: 1246, displacementRisk: 'medium' }
    },
    editor: {
      student: { low: 500, high: 2000, unionMin: null, displacementRisk: 'medium' },
      indie: { low: 5000, high: 25000, unionMin: null, displacementRisk: 'medium' },
      professional: { low: 15000, high: 50000, unionMin: null, displacementRisk: 'low' },
      studio: { low: 50000, high: 200000, unionMin: null, displacementRisk: 'low' }
    },
    sound_designer: {
      student: { low: 500, high: 2000, unionMin: null, displacementRisk: 'medium' },
      indie: { low: 2000, high: 15000, unionMin: null, displacementRisk: 'medium' },
      professional: { low: 10000, high: 35000, unionMin: null, displacementRisk: 'medium' },
      studio: { low: 25000, high: 100000, unionMin: null, displacementRisk: 'low' }
    },
    colorist: {
      student: { low: 300, high: 1000, unionMin: null, displacementRisk: 'high' },
      indie: { low: 2000, high: 10000, unionMin: null, displacementRisk: 'high' },
      professional: { low: 5000, high: 15000, unionMin: null, displacementRisk: 'medium' },
      studio: { low: 15000, high: 50000, unionMin: null, displacementRisk: 'low' }
    }
  };
  ```
- **Rate Selection Rule:** Look up `RATE_TABLE[role][budgetTier]`. If `currentBudgetForRole` is provided, `userBudgetDelta = { low: currentBudgetForRole - humanCostRange.high, high: currentBudgetForRole - humanCostRange.low }`. Negative delta = under market rate.
- **Probabilistic Output (Sonnet 4.6):** Ethical implications. Zod schema:
  ```typescript
  const BudgetAI = z.object({ ethicalAnalysis: z.string().min(50).max(2000) });
  ```
- **Free Tier:** Cost comparison numbers + displacement risk rating.
- **Premium:** Full AI ethical analysis.
- **Error States:** Missing required fields -> inline validation. Unknown role/tier combo -> "Rate data unavailable." LLM failure -> show deterministic comparison with "Ethical analysis unavailable."
- **Stored in ToolEvent:** Yes.
- **Fixture:**
  ```json
  {
    "input": {
      "role": "composer",
      "budgetTier": "indie",
      "projectScope": "10-minute short film score, 3 themes",
      "currentBudgetForRole": 1500
    },
    "expectedOutput": {
      "roleName": "composer",
      "budgetTier": "indie",
      "humanCostRange": { "low": 2000, "high": 25000 },
      "unionMinimum": null,
      "displacementRisk": "high",
      "userBudgetDelta": { "low": -23500, "high": -500 }
    }
  }
  ```
  - Rate lookup: `RATE_TABLE['composer']['indie']` = `{ low: 2000, high: 25000, unionMin: null, displacementRisk: 'high' }`.
  - `userBudgetDelta.low` = `1500 - 25000` = `-23500`. `userBudgetDelta.high` = `1500 - 2000` = `-500`. Negative = under market rate.

---

## 5. Realtime Sync & Dual-Mode UX

**Implementation:** Supabase Realtime.

### Channel & Message Contract

**Channel name:** `workshop:{workshopSessionId}`

All messages include `eventId` (UUID, client-generated).

**Idempotency by interaction type:**
- **Broadcast-first interactions:** Idempotency is facilitator-side only. The facilitator client keeps an in-memory `Set<string>` of received `eventId` values per workshop session and ignores duplicates. No server involvement.
- **Authoritative-state interactions:** Server checks `processed_events` table and silently rejects duplicates. `processed_events` is used only for API-backed persisted interactions: `risk.aggregate`, `qna.question`, `qna.upvote`.

#### Broadcast-First Interactions (client-only Supabase broadcast, no server persistence)

**1. Poll Response:**
```typescript
{ eventId: string, type: 'poll.response', workshopSessionId: string, anonymousSessionId: string, pollId: string, optionId: string, createdAt: string }
```
Facilitator UI: bar chart aggregate by `optionId` count.

**2. Word Cloud Submission:**
```typescript
{ eventId: string, type: 'word_cloud.submit', workshopSessionId: string, anonymousSessionId: string, promptId: string, phrase: string, createdAt: string }
```
`phrase`: max 50 chars. Facilitator UI: word cloud sized by frequency.

**3. Confidence Slider:**
```typescript
{ eventId: string, type: 'confidence.submit', workshopSessionId: string, anonymousSessionId: string, phase: 'before' | 'after', value: number, createdAt: string }
```
`value`: integer 1-10. Facilitator UI: before/after delta chart.

#### Authoritative-State Interactions (persisted via API routes, broadcast after persistence)

**Persisted realtime routes:**
- `POST /api/workshop/risk-aggregate`
- `POST /api/workshop/qna/question`
- `POST /api/workshop/qna/upvote`

**4. Risk Scanner Aggregate:**
```typescript
{ eventId: string, type: 'risk.aggregate', workshopSessionId: string, anonymousSessionId: string, riskTier: 'low' | 'medium' | 'high' | 'critical', topRiskDepartments: string[], createdAt: string }
```
Persisted in `workshop_risk_scores`. On reconnect, server replays last known score for that `anonymousSessionId` -- does not duplicate. Facilitator UI: percentage breakdown by tier.

**5. Q&A Question:**
```typescript
{ eventId: string, type: 'qna.question', workshopSessionId: string, anonymousSessionId: string, questionText: string, createdAt: string }
```
Persisted in `qna_questions`. Server assigns `questionId` and broadcasts back with ID.

**6. Q&A Upvote:**
```typescript
{ eventId: string, type: 'qna.upvote', workshopSessionId: string, anonymousSessionId: string, questionId: string, createdAt: string }
```
Persisted in `qna_votes`. Unique constraint `(question_id, anonymous_session_id)` enforced at DB level. Server increments `upvote_count` on `qna_questions` and broadcasts updated count. Duplicate upvote attempt returns silently (no error to client).

**Strict scope -- do NOT build:** gamification, free-text chat, collaborative editing, leaderboards.

---

## 6. Locked Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Stack | Next.js + Vercel | Existing patterns from Producer Brief. Solution docs available. |
| 2 | Auth | Supabase Auth + Magic Link | Lowest friction for anonymous-to-auth conversion. Unified with realtime. |
| 3 | Realtime | Supabase Realtime | Keeps stack unified. Broadcast for polls, persisted state for Q&A. |
| 4 | Payments | Square (sandbox checkout links + manual entitlement for v1) | Consistency with existing workshop payments. Full webhook automation post-launch. |
| 5 | Email | Resend | Simple API, generous free tier. v1 sends 3 lifecycle emails only. |
| 6 | Price | $15/mo subscription | $49 Project Export deferred to post-launch. |
| 7 | Trial | 14 days | Research-backed (Gartner/Recurly). |
| 8 | LLM Routing | Haiku 4.5 (Tool 1) / Sonnet 4.6 (Tools 3, 5) | Simple generation vs complex analysis. Tools 2, 4 have no LLM. |
| 9 | Offline | Service Worker + deterministic-only mode | Cache UI shell, Festival JSON, Rate JSON. Network-dependent actions show unavailable state. |
| 10 | App Name | Ethics Toolkit (internal/repo name) | Final public name TBD. Does not block the build. |
| 11 | Phasing | 4 sequential phases with integration gates | See Section 8. |

---

## 7. Square Integration Contract (v1: Checkout Links + Manual Entitlement)

**v1 scope for May 30:** Square sandbox checkout links + manual entitlement confirmation. Do NOT implement full Square subscription webhooks in autopilot v1.

### Flow

1. User clicks "Subscribe" in app.
2. App redirects to Square-hosted checkout page (sandbox mode). URL configured via `SQUARE_CHECKOUT_URL` env var.
3. User completes payment on Square.
4. User returns to app. App shows "Payment processing -- your access will be activated shortly."
5. Alex (facilitator) uses admin route to confirm payment and activate entitlement.

### Admin Route

- `POST /api/admin/activate` (facilitator-authenticated)
- Body: `{ userEmail: string, squarePaymentId: string }`
- Action: look up `profiles` by email, set `entitlement_status = 'active'`, create `square_entitlements` row with `square_payment_id`.

### Full Square webhook automation is deferred to post-launch.

---

## 8. Email Lifecycle Contract

**Service:** Resend. Simple opt-in lifecycle emails only. No behavior-triggered automation.

### Email Schedule

On user conversion (magic link auth):
- Generate a new UUID and set `profiles.current_trial_id = <uuid>`
- Set `profiles.trial_started_at = now()`
- Set `profiles.trial_ends_at = now() + interval '14 days'`
- Create 3 `email_jobs` rows (using `current_trial_id` as the `trial_id` for idempotency keys):

| Email | `scheduled_for` | Subject Line |
|-------|----------------|-------------|
| Welcome | `now()` | "Your Ethics Toolkit results are saved" |
| Day 12 Warning | `trial_ends_at - interval '2 days'` | "Your premium trial ends in 2 days" |
| Day 14 Downgrade | `trial_ends_at` | "Your premium trial has ended" |

### Email Structure (all 3 emails)

- **Format:** HTML with plain-text fallback.
- **Required elements:** Subject line (as above), body text, deep link back to app (`{APP_URL}/results`), unsubscribe link (`{APP_URL}/unsubscribe?token={token}`), legal disclaimer footer.
- **Welcome body:** "Here's what you created today: [list of tools used with links]. Your premium access is active for 14 days."
- **Day 12 body:** "Your trial ends on {date}. Here's what you've used: [tool usage summary]. After your trial, you'll keep your data but lose [list premium features]. Subscribe for $15/mo to keep full access."
- **Day 14 body:** "Your trial has ended. You still have access to [free features]. Upgrade anytime to restore [premium features]. Subscribe for $15/mo."

### Idempotency & Safety

- Idempotency key: `{userId}:{emailType}:{trialId}`. Stored as `UNIQUE` constraint on `email_jobs.idempotency_key`.
- Before sending: check `profiles.email_opt_out`. If true, set job `status = 'skipped'`.
- Retry: if Resend returns 5xx, retry once after 60 seconds. If still failing, set `status = 'failed'`.
- Unsubscribe: sets `profiles.email_opt_out = true`. Check before every send.

### Scheduling

Daily Vercel Cron job at `/api/cron/process-emails`:
- Protected by `CRON_SECRET` (Vercel cron authorization header).
- Query: `SELECT * FROM email_jobs WHERE status = 'pending' AND scheduled_for <= now()`.
- For each job: check `email_opt_out`, send via Resend API, update `status = 'sent'` and `sent_at = now()`.

---

## 9. Rate Limiting

**Storage:** Use an in-memory `Map<string, { count: number; resetAt: number }>` for v1 rate limiting. This is acceptable for the May 30 single-process deployment and is testable without external dependencies. Do not add Upstash, Redis, or any new infrastructure.

| Route Pattern | Limit | Scope |
|--------------|-------|-------|
| `/api/ai/*` | 10 requests/hour, 30 requests/day | Per IP (hourly), per user (daily) |
| `/api/realtime/*` | 120 requests/minute | Per IP |
| `/api/auth/save-results` | 5 requests/hour | Per IP |
| All other `/api/*` | 60 requests/minute | Per IP |

On limit: return HTTP 429 with body `{ "error": "rate_limited", "retryAfter": <seconds> }`.

Mock mode bypasses Anthropic API but still enforces rate limits and input validation.

---

## 10. Autopilot Phasing Strategy

Execute in four sequential phases with hard integration gates. Reference prior solution docs:
- `docs/solutions/2026-04-09-autopilot-swarm-orchestration.md`
- `docs/solutions/2026-04-12-error-injection-pipeline-recovery.md`

### Shared Interface Specification

All persisted tool outputs implement the `ToolEvent` interface. Festival Policy Lookup is read-only and does NOT create ToolEvent records.

```typescript
type ToolType = 'DISCLOSURE' | 'RISK' | 'PROVENANCE' | 'BUDGET';

interface ToolEvent<TPayload, TAI = never> {
  eventId: string;             // UUID, client-generated
  schemaVersion: 1;
  workshopSessionId?: string;
  anonymousSessionId: string;
  userId?: string;
  toolType: ToolType;
  deterministicPayload: TPayload;
  probabilisticPayload?: TAI;  // stored as JSONB, null when unavailable
  createdAt: string;           // ISO 8601
}
```

Per-tool payload Zod schemas are defined in Section 4. All schemas must be implemented and passing contract tests before Phase 2 tool workers start (Phase 2.0 gate).

### Phase 1: Foundation & Identity Shell

- **Scope:** Next.js scaffolding, Supabase project setup, database migration (Section 3 schema), Supabase Auth setup, UI shell routing (Facilitator vs. Attendee), Anonymous -> Magic Link conversion flow, facilitator password auth.
- **Gate / Definition of Done:**
  - User can load the app and receive an anonymous ID stored in `anonymous_sessions`
  - User can click "Save Results", enter email, complete magic link, and see their anonymous session claimed into their `userId`
  - Facilitator can log in with password at `/facilitator`
  - Anonymous data without conversion is queryable for deletion
  - Database schema matches Section 3 exactly

### Phase 2: The 5 Tools (Deterministic First)

- **Phase 2.0 Pre-Gate:** Zod schemas from Section 4 implemented as shared TypeScript modules. Fixture tests pass for all 5 tools. No tool worker starts until this gate passes.
- **Scope:** Build the UI and deterministic logic for all 5 tools per Section 4. Mock the LLM responses using hardcoded delays and static strings. Implement Service Worker caching for Festival seed data and rate table. Seed `festival_policies` with 12 records from Section 4.
- **Gate / Definition of Done:**
  - All 5 tools run end-to-end on a mobile viewport with deterministic output and mock probabilistic output
  - All Zod schemas validate real tool output (not just fixtures)
  - Risk Scanner produces identical scores for the fixture input
  - Festival and rate data cached via Service Worker
  - Tools display cached data and show "AI recommendation temporarily unavailable" when network is offline
  - Mock mode works without any API keys configured

### Phase 3: Realtime Engine & Facilitator View

- **Scope:** Implement Supabase Realtime channels per Section 5. Build Facilitator dashboard. Wire up all 6 message types. Implement Q&A persisted state with idempotency. Run automated load test.
- **Gate / Definition of Done (automated verification):**
  - Automated workshop simulation creates 30 attendee sessions, each submitting:
    - 1 poll response
    - 1 risk scanner aggregate score
    - 1 word cloud phrase
    - 1 confidence slider value
    - 1 Q&A question + 1 upvote on another question
  - Pass criteria:
    - Facilitator receives at least 99% of expected events
    - p95 visible update latency under 1500ms
    - Reconnecting an attendee does not duplicate votes or Q&A upvotes
    - Attendee UI does not crash when realtime disconnects
    - Facilitator UI shows "Waiting for more responses" when fewer than 5 responses exist
    - Facilitator UI shows fallback/stale state when realtime disconnects
  - Note: this is a low-volume functional simulation (30 clients, max 2 req/sec to Vercel APIs). Realtime traffic goes directly to Supabase, not through Vercel Functions.

### Phase 4: Probabilistic AI, Payments & Lifecycle

- **Scope:** Replace mock LLM calls with Anthropic API routes (Haiku 4.5 / Sonnet 4.6). Implement Square sandbox checkout link flow + admin activation route (Section 7). Wire up Resend for 3 lifecycle emails with `email_jobs` table and daily cron (Section 8). Implement rate limiting (Section 9).
- **Gate / Definition of Done:**
  - Mock mode still works without Anthropic/Square/Resend keys
  - Anthropic API routes validate output shape with Zod (same schemas as mock mode)
  - Square sandbox checkout link opens correctly
  - Admin activation route sets `entitlement_status = 'active'`
  - Resend welcome email is idempotent (sending twice with same idempotency key does not duplicate)
  - Day 12 and Day 14 email jobs are created as pending on trial start
  - Cron endpoint processes pending jobs correctly
  - All API routes enforce rate limits per Section 9
  - End-to-end workflow: Anonymous tool use -> Magic Link signup -> Welcome email -> Square checkout link -> Admin activation -> Entitlement active

### Pre-Workshop Gate (Before May 30)

- Rerun Phase 3 load test on deployed Vercel environment (low-volume, realtime via Supabase).
- Facilitator flow walkthrough on actual venue projector setup.
- Manual fallback slides prepared in case realtime sync fails during live workshop.
- All 5 tools verified on iPhone Safari and Android Chrome.
- Square checkout in sandbox mode.

---

## 11. Swarm Execution Guardrails

Reference: `docs/solutions/2026-04-09-autopilot-swarm-orchestration.md`

### File Ownership

- Each phase gets its own shared interface spec (Phase 2.0 Zod schemas serve as the Phase 2 spec).
- Each worker agent gets an explicit file ownership list. No worker may edit files outside its assigned scope.
- Pre-merge ownership gate: `git diff --name-only` against each agent's declared file list. Any out-of-scope edit fails the gate.

### Phase Reports

Every phase writes a structured report under `docs/reports/`:
- `docs/reports/phase-1-foundation.md`
- `docs/reports/phase-2-tools.md`
- `docs/reports/phase-3-realtime.md`
- `docs/reports/phase-4-integration.md`

Each report includes: `STATUS: PASS/FAIL`, files created/modified, gate results, issues found.

### Gate Sequence (per phase)

1. Ownership gate -- verify no cross-agent file contamination
2. Contract check -- grep for spec names, validate Zod schemas
3. Smoke test -- start app, hit routes, verify status codes
4. Test suite -- run full test suite
5. If any gate fails: one assembly-fix attempt, then re-run gates
6. If second failure: stop for human review. Do not retry indefinitely.

### Bash Command Rules

Agents must follow these rules to avoid permission prompts:
- One command per Bash call (no `&&` chaining)
- Use `git -C <path>` instead of `cd <path> && git`
- Use full venv paths instead of `source activate`
- Use Write tool for multi-line scripts (no heredocs in Bash)

---

## 12. Environment Variables

```
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Anthropic
ANTHROPIC_API_KEY=

# Resend
RESEND_API_KEY=

# Square
SQUARE_ACCESS_TOKEN=
SQUARE_CHECKOUT_URL=

# App
NEXT_PUBLIC_APP_URL=
CRON_SECRET=
FACILITATOR_PASSWORD_HASH=
```

All keys are required in production. In development/mock mode, only `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_APP_URL` are required. All other missing keys trigger mock/fallback mode for their respective services.

---

## 13. Items Deferred to Post-Launch

These are explicitly out of scope for the May 30 build:

- Festival auto-scraping (v1 is human-curated; scraper infrastructure in `sandbox/venue-scraper/` adapts post-launch)
- Behavior-triggered email automation (v1 is 3 simple lifecycle emails only)
- $49 one-time Project Export (evaluate demand signals post-launch)
- Full Square subscription webhook automation (v1 is checkout links + manual activation)
- Public app name and branding
- Cross-origin attendee frontend
- Error monitoring beyond console/Vercel logs

---

## Swarm Agent Assignment

Each phase is a sequential swarm step. Agents within a phase run in parallel. No phase starts until the previous phase's gate passes. File paths are relative to the project root (`ethics-toolkit/`).

### Phase 1: Foundation & Identity Shell (4 agents)

#### Agent 1: `scaffold`

| | |
|---|---|
| **Spec sections** | 1 (Global Constraints), 6 (Locked Decisions), 12 (Environment Variables) |
| **Creates** | `package.json`, `tsconfig.json`, `tailwind.config.ts`, `postcss.config.js`, `next.config.ts`, `.env.example`, `.env.local` (gitignored), `.gitignore`, `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/globals.css`, `src/lib/constants.ts` |
| **Reads (no modify)** | None (first to run conceptually, but parallel -- no deps within phase) |

#### Agent 2: `database`

| | |
|---|---|
| **Spec sections** | 3 (Authoritative Database Schema), 3 RLS Rules |
| **Creates** | `supabase/migrations/001_initial_schema.sql` (all tables, indexes, constraints from Section 3), `supabase/migrations/002_rls_policies.sql` (all RLS rules from Section 3), `supabase/config.toml`, `src/lib/supabase/client.ts` (browser client), `src/lib/supabase/server.ts` (server client with service role), `src/types/database.ts` (TypeScript types matching Section 3 tables) |
| **Reads (no modify)** | `.env.example` (from scaffold, for env var names) |

#### Agent 3: `auth`

| | |
|---|---|
| **Spec sections** | 2 (Identity & Monetization Architecture -- Identity Flow, Facilitator Authentication) |
| **Creates** | `src/lib/auth/anonymous-session.ts` (generate/store anonymousSessionId in localStorage + anonymous_sessions table), `src/lib/auth/magic-link.ts` (Supabase Auth magic link trigger + session claiming logic), `src/lib/auth/facilitator.ts` (bcrypt compare + httpOnly cookie + JWT/HMAC signing), `src/app/api/auth/magic-link/route.ts`, `src/app/api/auth/facilitator-login/route.ts`, `src/app/api/auth/save-results/route.ts` (claim anonymous data into userId), `src/middleware.ts` (facilitator route protection) |
| **Reads (no modify)** | `src/lib/supabase/client.ts`, `src/lib/supabase/server.ts`, `src/types/database.ts` (from database agent) |

#### Agent 4: `ui-shell`

| | |
|---|---|
| **Spec sections** | 1 (Mobile-First Attendee UX), 2 (Identity Flow -- QR join) |
| **Creates** | `src/app/(attendee)/layout.tsx`, `src/app/(attendee)/page.tsx` (attendee home), `src/app/(attendee)/join/[code]/page.tsx` (QR join page -- validates session_code against workshop_sessions), `src/app/(attendee)/tools/layout.tsx`, `src/app/(attendee)/results/page.tsx`, `src/app/(attendee)/save/page.tsx` (save results / magic link prompt), `src/app/facilitator/layout.tsx`, `src/app/facilitator/page.tsx` (facilitator home -- behind auth), `src/app/facilitator/login/page.tsx`, `src/components/ui/nav.tsx`, `src/components/ui/mobile-action-bar.tsx` (bottom thumb zone actions) |
| **Reads (no modify)** | `src/app/layout.tsx`, `src/app/globals.css` (from scaffold), `src/middleware.ts` (from auth) |

**Phase 1 Gate:** Per Section 10 -- anonymous ID stored, magic link claims session, facilitator login works, schema matches Section 3.

---

### Phase 2: The 5 Tools -- Deterministic First (5 agents)

#### Agent 0 (pre-gate): `schemas`

> **Runs before Agents 1-3.** Phase 2 tool agents do NOT start until this agent's fixture tests pass (Phase 2.0 gate from Section 10).

| | |
|---|---|
| **Spec sections** | 4 (all 5 tool Zod schemas + fixtures), 10 (Shared Interface Specification -- ToolEvent) |
| **Creates** | `src/lib/schemas/tool-event.ts` (ToolEvent interface + ToolType), `src/lib/schemas/disclosure.ts` (DisclosureInput, DisclosureOutput, DisclosureAI), `src/lib/schemas/policy-lookup.ts` (PolicyLookupInput), `src/lib/schemas/risk-scanner.ts` (RiskScannerInput, RiskScannerOutput, RiskAI), `src/lib/schemas/provenance.ts` (ProvenanceInput, ProvenanceOutput), `src/lib/schemas/budget.ts` (BudgetInput, BudgetOutput, BudgetAI), `src/lib/schemas/index.ts` (barrel export), `tests/schemas/disclosure.test.ts`, `tests/schemas/risk-scanner.test.ts`, `tests/schemas/provenance.test.ts`, `tests/schemas/budget.test.ts`, `tests/schemas/policy-lookup.test.ts` |
| **Reads (no modify)** | `src/types/database.ts` (from Phase 1 database agent) |

#### Agent 1: `tool-disclosure-festival`

| | |
|---|---|
| **Spec sections** | 4 Tool 1 (AI Disclosure Generator -- deterministic checklist logic, satisfied rules, fixture), 4 Tool 2 (Festival Policy Lookup -- search, filters, seed data, pagination) |
| **Creates** | `src/lib/tools/disclosure.ts` (deterministic checklist + template generation), `src/lib/tools/disclosure-mock.ts` (mock AI response with hardcoded delay), `src/app/(attendee)/tools/disclosure/page.tsx` (Disclosure Generator UI -- form + checklist + template output), `src/app/api/tools/disclosure/route.ts` (POST -- validate, compute, persist ToolEvent, return deterministic + optional AI), `src/lib/tools/festival-lookup.ts` (search + filter logic), `src/app/(attendee)/tools/festival/page.tsx` (Festival Policy Lookup UI -- search bar, filter dropdowns, paginated results), `src/app/api/tools/festival/route.ts` (GET -- query festival_policies), `supabase/migrations/003_seed_festival_policies.sql` (12 seed records from Section 4) |
| **Reads (no modify)** | `src/lib/schemas/disclosure.ts`, `src/lib/schemas/policy-lookup.ts`, `src/lib/schemas/tool-event.ts` (from schemas agent), `src/lib/supabase/client.ts`, `src/lib/supabase/server.ts`, `src/lib/auth/anonymous-session.ts` (from Phase 1) |

#### Agent 2: `tool-risk-provenance`

| | |
|---|---|
| **Spec sections** | 4 Tool 3 (Risk Scanner -- all 7 scoring steps, fixture, department flags), 4 Tool 4 (Provenance Chain -- summary calc, duplicate detection, PDF export) |
| **Creates** | `src/lib/tools/risk-scanner.ts` (deterministic scoring engine -- Steps 1-7 exactly), `src/lib/tools/risk-scanner-mock.ts` (mock AI recommendations), `src/app/(attendee)/tools/risk/page.tsx` (Risk Scanner UI -- form + tier badge + department flags + dimension breakdown), `src/app/api/tools/risk/route.ts` (POST -- validate, score, persist ToolEvent), `src/lib/tools/provenance.ts` (deterministic summary + duplicate detection), `src/app/(attendee)/tools/provenance/page.tsx` (Provenance Chain UI -- entry form + chain view + summary stats), `src/app/api/tools/provenance/route.ts` (POST -- validate, compute, persist ToolEvent), `src/lib/tools/provenance-pdf.ts` (PDF export with @react-pdf/renderer) |
| **Reads (no modify)** | `src/lib/schemas/risk-scanner.ts`, `src/lib/schemas/provenance.ts`, `src/lib/schemas/tool-event.ts` (from schemas agent), `src/lib/supabase/client.ts`, `src/lib/supabase/server.ts`, `src/lib/auth/anonymous-session.ts` (from Phase 1) |

#### Agent 3: `tool-budget-sw`

| | |
|---|---|
| **Spec sections** | 4 Tool 5 (Budget Calculator -- RATE_TABLE, delta calc, fixture), 1 (Offline Degradation), 6 decision #9 (Service Worker) |
| **Creates** | `src/lib/tools/budget.ts` (RATE_TABLE constant + deterministic lookup + delta calc), `src/lib/tools/budget-mock.ts` (mock AI ethical analysis), `src/app/(attendee)/tools/budget/page.tsx` (Budget Calculator UI -- role/tier selectors + cost comparison + displacement badge + delta display), `src/app/api/tools/budget/route.ts` (POST -- validate, lookup, persist ToolEvent), `public/sw.js` (Service Worker -- caches app shell, festival seed JSON, rate table JSON), `src/lib/sw-register.ts` (register SW on app load), `public/offline.html` (minimal offline fallback page) |
| **Reads (no modify)** | `src/lib/schemas/budget.ts`, `src/lib/schemas/tool-event.ts` (from schemas agent), `src/lib/supabase/client.ts`, `src/lib/supabase/server.ts`, `src/lib/auth/anonymous-session.ts` (from Phase 1), `next.config.ts` (from Phase 1 scaffold -- may need SW headers) |

**Phase 2 Gate:** Per Section 10 -- all 5 tools run end-to-end on mobile viewport, Zod validates real output, Risk Scanner fixture matches, SW caches festival/rate data, mock mode works without API keys.

---

### Phase 3: Realtime Engine & Facilitator View (3 agents)

#### Agent 1: `realtime-engine`

| | |
|---|---|
| **Spec sections** | 5 (Realtime Sync -- channel contract, all 6 message types, idempotency rules), 3 (processed_events, workshop_risk_scores, qna_questions, qna_votes tables) |
| **Creates** | `src/lib/realtime/channel.ts` (Supabase Realtime channel setup -- `workshop:{workshopSessionId}`), `src/lib/realtime/types.ts` (TypeScript types for all 6 message payloads), `src/lib/realtime/broadcast.ts` (client-side broadcast helpers for poll, word cloud, confidence), `src/lib/realtime/idempotency.ts` (facilitator-side in-memory `Set<string>` for broadcast dedup), `src/app/api/workshop/risk-aggregate/route.ts` (POST -- persist to workshop_risk_scores + processed_events check + broadcast), `src/app/api/workshop/qna/question/route.ts` (POST -- persist to qna_questions + processed_events check + broadcast with assigned ID), `src/app/api/workshop/qna/upvote/route.ts` (POST -- persist to qna_votes + increment upvote_count + processed_events check + broadcast), `src/app/api/workshop/session/route.ts` (POST -- create workshop_sessions, facilitator-only) |
| **Reads (no modify)** | `src/lib/supabase/client.ts`, `src/lib/supabase/server.ts`, `src/types/database.ts` (from Phase 1), `src/middleware.ts` (from Phase 1 auth -- facilitator route check) |

#### Agent 2: `facilitator-dashboard`

| | |
|---|---|
| **Spec sections** | 5 (Facilitator UI descriptions for all 6 message types), 1 (Data Privacy -- 5-response minimum) |
| **Creates** | `src/app/facilitator/dashboard/page.tsx` (main facilitator dashboard -- layout with all widgets), `src/components/facilitator/poll-chart.tsx` (bar chart aggregate by optionId count), `src/components/facilitator/word-cloud.tsx` (word cloud sized by frequency), `src/components/facilitator/risk-breakdown.tsx` (percentage breakdown by tier -- low/medium/high/critical), `src/components/facilitator/confidence-delta.tsx` (before/after delta chart), `src/components/facilitator/qna-queue.tsx` (questions sorted by upvote_count, live-updating), `src/components/facilitator/min-response-guard.tsx` ("Waiting for more responses" when < 5), `src/app/facilitator/dashboard/layout.tsx` |
| **Reads (no modify)** | `src/lib/realtime/channel.ts`, `src/lib/realtime/types.ts`, `src/lib/realtime/idempotency.ts` (from realtime-engine agent), `src/lib/supabase/client.ts` (from Phase 1) |

#### Agent 3: `attendee-realtime`

| | |
|---|---|
| **Spec sections** | 5 (Attendee-side broadcast interactions -- poll, word cloud, confidence; authoritative interactions -- Q&A question, upvote), 1 (Mobile-First UX) |
| **Creates** | `src/components/attendee/poll-response.tsx` (single-tap option selection, broadcasts poll.response), `src/components/attendee/word-cloud-input.tsx` (text input max 50 chars, broadcasts word_cloud.submit), `src/components/attendee/confidence-slider.tsx` (1-10 slider with before/after phase, broadcasts confidence.submit), `src/components/attendee/qna-submit.tsx` (text input, POSTs to /api/workshop/qna/question), `src/components/attendee/qna-list.tsx` (view questions + upvote button, POSTs to /api/workshop/qna/upvote), `src/app/(attendee)/workshop/[sessionId]/page.tsx` (workshop live view -- renders all attendee realtime components) |
| **Reads (no modify)** | `src/lib/realtime/channel.ts`, `src/lib/realtime/types.ts`, `src/lib/realtime/broadcast.ts` (from realtime-engine agent), `src/lib/auth/anonymous-session.ts` (from Phase 1), `src/lib/supabase/client.ts` (from Phase 1) |

**Phase 3 Gate:** Per Section 10 -- automated 30-attendee simulation passes (99% event delivery, p95 < 1500ms, no duplicate votes on reconnect, < 5 shows guard message, disconnect shows fallback).

---

### Phase 4: Probabilistic AI, Payments & Lifecycle (3 agents)

#### Agent 1: `ai-routes`

| | |
|---|---|
| **Spec sections** | 4 (LLM schemas -- DisclosureAI, RiskAI, BudgetAI), 6 decision #8 (LLM Routing -- Haiku 4.5 for Tool 1, Sonnet 4.6 for Tools 3/5), 1 (Model Access Preflight, mock mode fallback) |
| **Creates** | `src/lib/ai/client.ts` (Anthropic SDK client + model access preflight check), `src/lib/ai/mock.ts` (mock response functions -- same shape as real, used when keys missing or API unreachable), `src/app/api/ai/disclosure/route.ts` (POST -- Haiku 4.5 call, Zod-validated output, fallback to mock), `src/app/api/ai/risk/route.ts` (POST -- Sonnet 4.6 call, Zod-validated output, fallback to mock), `src/app/api/ai/budget/route.ts` (POST -- Sonnet 4.6 call, Zod-validated output, fallback to mock), `src/lib/ai/preflight.ts` (startup check for Haiku 4.5 + Sonnet 4.6 reachability) |
| **Reads (no modify)** | `src/lib/schemas/disclosure.ts`, `src/lib/schemas/risk-scanner.ts`, `src/lib/schemas/budget.ts` (from Phase 2 schemas), `src/lib/tools/disclosure-mock.ts`, `src/lib/tools/risk-scanner-mock.ts`, `src/lib/tools/budget-mock.ts` (from Phase 2 -- for mock mode reference) |

#### Agent 2: `payments-email`

| | |
|---|---|
| **Spec sections** | 7 (Square Integration Contract -- checkout link flow, admin activation route), 8 (Email Lifecycle Contract -- 3 emails, idempotency, cron, unsubscribe), 2 (Monetization -- trial timing) |
| **Creates** | `src/app/api/payments/checkout/route.ts` (GET -- redirect to SQUARE_CHECKOUT_URL), `src/app/(attendee)/payments/pending/page.tsx` ("Payment processing" return page), `src/app/api/admin/activate/route.ts` (POST -- facilitator-authenticated, sets entitlement_status + creates square_entitlements row), `src/lib/email/resend-client.ts` (Resend SDK client), `src/lib/email/templates/welcome.tsx` (HTML + plain-text), `src/lib/email/templates/day12-warning.tsx`, `src/lib/email/templates/day14-downgrade.tsx`, `src/lib/email/send.ts` (send function with opt-out check + retry logic), `src/lib/email/schedule-trial-emails.ts` (creates 3 email_jobs rows on conversion), `src/app/api/cron/process-emails/route.ts` (Vercel Cron -- CRON_SECRET protected, processes pending jobs), `src/app/(attendee)/unsubscribe/page.tsx` (token-validated unsubscribe page), `vercel.json` (cron schedule config for daily email processing) |
| **Reads (no modify)** | `src/lib/supabase/server.ts`, `src/types/database.ts` (from Phase 1), `src/lib/auth/facilitator.ts`, `src/middleware.ts` (from Phase 1 auth -- facilitator validation for admin route) |

#### Agent 3: `rate-limiting`

| | |
|---|---|
| **Spec sections** | 9 (Rate Limiting -- all 4 route patterns, in-memory Map, 429 response shape) |
| **Creates** | `src/lib/rate-limit/limiter.ts` (in-memory `Map<string, { count: number; resetAt: number }>` with configurable window/limit), `src/lib/rate-limit/middleware.ts` (rate limit middleware function -- extracts IP, checks limits, returns 429 with retryAfter), `src/lib/rate-limit/config.ts` (rate limit configs for all 4 route patterns from Section 9), `src/app/api/ai/middleware.ts` (applies 10/hr + 30/day per Section 9 to all `/api/ai/*` routes), `tests/rate-limit/limiter.test.ts` (unit tests for Map-based limiter) |
| **Reads (no modify)** | `src/app/api/ai/disclosure/route.ts`, `src/app/api/ai/risk/route.ts`, `src/app/api/ai/budget/route.ts` (from ai-routes agent -- to wire rate limiting), `src/app/api/workshop/risk-aggregate/route.ts`, `src/app/api/workshop/qna/question/route.ts`, `src/app/api/workshop/qna/upvote/route.ts` (from Phase 3 -- to wire rate limiting), `src/app/api/auth/save-results/route.ts` (from Phase 1 -- to wire rate limiting) |

**Phase 4 Gate:** Per Section 10 -- mock mode works without keys, AI routes Zod-validate output, Square checkout opens, admin activation sets entitlement, welcome email is idempotent, day 12/14 jobs created on trial start, cron processes pending jobs, all routes enforce rate limits, full end-to-end workflow passes.

---

### Cross-Phase File Ownership Summary

| File/directory prefix | Owning agent | Phase |
|---|---|---|
| `package.json`, `tsconfig.json`, `tailwind.config.ts`, `postcss.config.js`, `next.config.ts`, `.env*`, `.gitignore` | scaffold | 1 |
| `supabase/migrations/001*`, `supabase/migrations/002*`, `supabase/config.toml`, `src/lib/supabase/*`, `src/types/database.ts` | database | 1 |
| `src/lib/auth/*`, `src/app/api/auth/*`, `src/middleware.ts` | auth | 1 |
| `src/app/(attendee)/*` (layout, page, join, save, results) | ui-shell | 1 |
| `src/app/facilitator/layout.tsx`, `src/app/facilitator/page.tsx`, `src/app/facilitator/login/*` | ui-shell | 1 |
| `src/components/ui/*` | ui-shell | 1 |
| `src/lib/schemas/*`, `tests/schemas/*` | schemas | 2 |
| `src/lib/tools/disclosure*`, `src/app/(attendee)/tools/disclosure/*`, `src/app/api/tools/disclosure/*` | tool-disclosure-festival | 2 |
| `src/lib/tools/festival*`, `src/app/(attendee)/tools/festival/*`, `src/app/api/tools/festival/*`, `supabase/migrations/003*` | tool-disclosure-festival | 2 |
| `src/lib/tools/risk*`, `src/app/(attendee)/tools/risk/*`, `src/app/api/tools/risk/*` | tool-risk-provenance | 2 |
| `src/lib/tools/provenance*`, `src/app/(attendee)/tools/provenance/*`, `src/app/api/tools/provenance/*` | tool-risk-provenance | 2 |
| `src/lib/tools/budget*`, `src/app/(attendee)/tools/budget/*`, `src/app/api/tools/budget/*` | tool-budget-sw | 2 |
| `public/sw.js`, `public/offline.html`, `src/lib/sw-register.ts` | tool-budget-sw | 2 |
| `src/lib/realtime/*`, `src/app/api/workshop/*` | realtime-engine | 3 |
| `src/app/facilitator/dashboard/*`, `src/components/facilitator/*` | facilitator-dashboard | 3 |
| `src/components/attendee/*`, `src/app/(attendee)/workshop/*` | attendee-realtime | 3 |
| `src/lib/ai/*`, `src/app/api/ai/*` | ai-routes | 4 |
| `src/lib/email/*`, `src/app/api/payments/*`, `src/app/api/admin/*`, `src/app/api/cron/*`, `src/app/(attendee)/payments/*`, `src/app/(attendee)/unsubscribe/*`, `vercel.json` | payments-email | 4 |
| `src/lib/rate-limit/*`, `tests/rate-limit/*` | rate-limiting | 4 |

### Conflict Resolution Rules

1. **No agent modifies files it does not own.** If an agent needs to integrate with another agent's file (e.g., rate-limiting needs to wrap AI routes), it creates its own middleware file and the integration is wired during the phase gate assembly step.
2. **Phase 2 schemas agent is a hard pre-gate.** Tool agents 1-3 in Phase 2 do NOT start until the schemas agent's fixture tests pass.
3. **Shared imports only.** Cross-agent dependencies are read-only imports. If Agent B needs a function from Agent A's file, it imports it -- it does not copy or redefine it.
4. **Assembly-fix agent** runs after each phase's parallel agents complete. It handles wiring (imports, route registrations, layout links) that require touching multiple agents' files. This is the ONLY agent allowed to edit across ownership boundaries, and only during the gate sequence.

---

## Feed-Forward

- **Hardest decision:** Keeping full scope (5 tools + dual-mode workshop + payments + email) against Codex's recommendation to cut. Simplified Square to checkout links + manual activation to reduce integration risk without cutting scope.
- **Rejected alternatives:** Reduced scope for May 30 (limits the autopilot stress test), Stripe over Square (consistency with existing workshop payments), required auth for workshop participation (kills the QR-scan-and-go experience), $49 Project Export in v1 (added complexity without validated demand), full Square webhook integration in v1 (too much API surface for a swarm to get right).
- **Least confident:** Autopilot swarm at platform complexity with cross-cutting concerns (auth/entitlements, realtime sync, LLM integration, payment flow, email lifecycle) across 5 tools. Phased swarms with integration gates mitigate this, but it's unproven territory. The Phase 2.0 Zod gate is critical -- if schemas aren't right, all downstream tools produce incompatible output.
