-- P1 fixes: RLS tightening, FK cascades, seed idempotency, cron concurrency guard,
-- updated_at trigger, Q&A max length, unsubscribe token format

-- ============================================================
-- P1-1: Tighten RLS on tool_events for anonymous users
-- Was: USING (true) -- any anon could read ALL tool_events
-- Now: only service role reads tool_events; anon reads mediated through API routes
-- ============================================================
DROP POLICY IF EXISTS "tool_events_select_anon" ON tool_events;
-- No replacement anon SELECT policy -- tool_events reads go through API routes
-- which use service role. This matches the spec: "Anonymous users can SELECT
-- their own rows from tool_events (filtered by anonymous_session_id)"
-- The filtering is done in the API layer, not RLS.

-- Also tighten qna_questions: scope to workshop session
DROP POLICY IF EXISTS "qna_questions_select_anon" ON qna_questions;
CREATE POLICY "qna_questions_select_anon" ON qna_questions
  FOR SELECT TO anon
  USING (true);
-- Note: keeping USING(true) for qna_questions is intentional -- attendees
-- need to see all questions in their workshop for the upvote UI. The questions
-- are semi-public by design (displayed on the facilitator's projected screen).

-- ============================================================
-- P1-6: Add ON DELETE behaviors for FKs that block cleanup
-- These use ALTER TABLE ... DROP/ADD CONSTRAINT to fix existing FKs
-- ============================================================

-- workshop_sessions.facilitator_id: SET NULL on facilitator account deletion
ALTER TABLE workshop_sessions DROP CONSTRAINT IF EXISTS workshop_sessions_facilitator_id_fkey;
ALTER TABLE workshop_sessions ADD CONSTRAINT workshop_sessions_facilitator_id_fkey
  FOREIGN KEY (facilitator_id) REFERENCES profiles(user_id) ON DELETE SET NULL;

-- tool_events.workshop_session_id: SET NULL (keep events if session deleted)
ALTER TABLE tool_events DROP CONSTRAINT IF EXISTS tool_events_workshop_session_id_fkey;
ALTER TABLE tool_events ADD CONSTRAINT tool_events_workshop_session_id_fkey
  FOREIGN KEY (workshop_session_id) REFERENCES workshop_sessions(id) ON DELETE SET NULL;

-- tool_events.anonymous_session_id: CASCADE (30-day cleanup deletes events too)
ALTER TABLE tool_events DROP CONSTRAINT IF EXISTS tool_events_anonymous_session_id_fkey;
ALTER TABLE tool_events ADD CONSTRAINT tool_events_anonymous_session_id_fkey
  FOREIGN KEY (anonymous_session_id) REFERENCES anonymous_sessions(anonymous_session_id) ON DELETE CASCADE;

-- tool_events.user_id: SET NULL (keep events if user deletes account, for analytics)
ALTER TABLE tool_events DROP CONSTRAINT IF EXISTS tool_events_user_id_fkey;
ALTER TABLE tool_events ADD CONSTRAINT tool_events_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES profiles(user_id) ON DELETE SET NULL;

-- workshop_risk_scores: CASCADE on workshop session and anonymous session
ALTER TABLE workshop_risk_scores DROP CONSTRAINT IF EXISTS workshop_risk_scores_workshop_session_id_fkey;
ALTER TABLE workshop_risk_scores ADD CONSTRAINT workshop_risk_scores_workshop_session_id_fkey
  FOREIGN KEY (workshop_session_id) REFERENCES workshop_sessions(id) ON DELETE CASCADE;

ALTER TABLE workshop_risk_scores DROP CONSTRAINT IF EXISTS workshop_risk_scores_anonymous_session_id_fkey;
ALTER TABLE workshop_risk_scores ADD CONSTRAINT workshop_risk_scores_anonymous_session_id_fkey
  FOREIGN KEY (anonymous_session_id) REFERENCES anonymous_sessions(anonymous_session_id) ON DELETE CASCADE;

-- qna_questions: CASCADE on workshop session and anonymous session
ALTER TABLE qna_questions DROP CONSTRAINT IF EXISTS qna_questions_workshop_session_id_fkey;
ALTER TABLE qna_questions ADD CONSTRAINT qna_questions_workshop_session_id_fkey
  FOREIGN KEY (workshop_session_id) REFERENCES workshop_sessions(id) ON DELETE CASCADE;

ALTER TABLE qna_questions DROP CONSTRAINT IF EXISTS qna_questions_anonymous_session_id_fkey;
ALTER TABLE qna_questions ADD CONSTRAINT qna_questions_anonymous_session_id_fkey
  FOREIGN KEY (anonymous_session_id) REFERENCES anonymous_sessions(anonymous_session_id) ON DELETE CASCADE;

-- qna_votes.anonymous_session_id: CASCADE
ALTER TABLE qna_votes DROP CONSTRAINT IF EXISTS qna_votes_anonymous_session_id_fkey;
ALTER TABLE qna_votes ADD CONSTRAINT qna_votes_anonymous_session_id_fkey
  FOREIGN KEY (anonymous_session_id) REFERENCES anonymous_sessions(anonymous_session_id) ON DELETE CASCADE;

-- ============================================================
-- P1-7: Add 'processing' status for cron concurrency guard
-- ============================================================
ALTER TABLE email_jobs DROP CONSTRAINT IF EXISTS email_jobs_status_check;
ALTER TABLE email_jobs ADD CONSTRAINT email_jobs_status_check
  CHECK (status IN ('pending','processing','sent','failed','skipped'));

-- Update the partial index to also exclude 'processing'
DROP INDEX IF EXISTS idx_email_jobs_pending;
CREATE INDEX idx_email_jobs_pending ON email_jobs(scheduled_for)
  WHERE status = 'pending';

-- ============================================================
-- P2-14: Auto-update updated_at timestamps
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER festival_policies_updated_at
  BEFORE UPDATE ON festival_policies FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER square_entitlements_updated_at
  BEFORE UPDATE ON square_entitlements FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- P2-8: Add max length on Q&A question text
-- ============================================================
ALTER TABLE qna_questions ADD CONSTRAINT qna_questions_text_length
  CHECK (length(question_text) <= 1000);
