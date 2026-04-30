-- P0-4: Atomic upvote increment (prevents race condition with concurrent users)
CREATE OR REPLACE FUNCTION increment_upvote(p_question_id UUID)
RETURNS INTEGER AS $$
  UPDATE qna_questions
  SET upvote_count = upvote_count + 1
  WHERE id = p_question_id
  RETURNING upvote_count;
$$ LANGUAGE sql;

-- P0-2: Transactional session claiming (prevents partial claim data corruption)
CREATE OR REPLACE FUNCTION claim_anonymous_session(
  p_anonymous_session_id TEXT,
  p_user_id UUID
) RETURNS void AS $$
BEGIN
  UPDATE anonymous_sessions
  SET user_id = p_user_id, claimed_at = now()
  WHERE anonymous_session_id = p_anonymous_session_id
    AND user_id IS NULL;

  UPDATE tool_events
  SET user_id = p_user_id
  WHERE anonymous_session_id = p_anonymous_session_id
    AND user_id IS NULL;
END;
$$ LANGUAGE plpgsql;
