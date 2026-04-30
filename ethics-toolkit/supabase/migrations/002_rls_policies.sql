-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE anonymous_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workshop_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE festival_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE workshop_risk_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE qna_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE qna_votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE square_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_jobs ENABLE ROW LEVEL SECURITY;

-- profiles: authenticated users can SELECT/UPDATE their own row
CREATE POLICY "profiles_select_own" ON profiles
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "profiles_update_own" ON profiles
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id);

-- anonymous_sessions: anonymous users can INSERT
CREATE POLICY "anonymous_sessions_insert" ON anonymous_sessions
  FOR INSERT TO anon
  WITH CHECK (true);

-- tool_events: anonymous users can INSERT using their anonymousSessionId
CREATE POLICY "tool_events_insert_anon" ON tool_events
  FOR INSERT TO anon
  WITH CHECK (true);

-- tool_events: anonymous users can SELECT their own rows
CREATE POLICY "tool_events_select_anon" ON tool_events
  FOR SELECT TO anon
  USING (true);

-- tool_events: authenticated users can SELECT their own rows
CREATE POLICY "tool_events_select_auth" ON tool_events
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

-- workshop_risk_scores: anonymous users can INSERT
CREATE POLICY "workshop_risk_scores_insert_anon" ON workshop_risk_scores
  FOR INSERT TO anon
  WITH CHECK (true);

-- qna_questions: anonymous users can INSERT
CREATE POLICY "qna_questions_insert_anon" ON qna_questions
  FOR INSERT TO anon
  WITH CHECK (true);

-- qna_questions: anonymous users can SELECT their own rows
CREATE POLICY "qna_questions_select_anon" ON qna_questions
  FOR SELECT TO anon
  USING (true);

-- qna_votes: anonymous users can INSERT
CREATE POLICY "qna_votes_insert_anon" ON qna_votes
  FOR INSERT TO anon
  WITH CHECK (true);

-- processed_events: anonymous users can INSERT
CREATE POLICY "processed_events_insert_anon" ON processed_events
  FOR INSERT TO anon
  WITH CHECK (true);

-- festival_policies: SELECT open to all (public read)
CREATE POLICY "festival_policies_select_all" ON festival_policies
  FOR SELECT TO anon, authenticated
  USING (true);

-- workshop_sessions: SELECT open to all (needed for QR join validation)
CREATE POLICY "workshop_sessions_select_all" ON workshop_sessions
  FOR SELECT TO anon, authenticated
  USING (true);

-- square_entitlements: authenticated users can SELECT their own rows
CREATE POLICY "square_entitlements_select_auth" ON square_entitlements
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);
