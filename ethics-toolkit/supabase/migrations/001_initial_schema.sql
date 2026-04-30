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
