/**
 * TypeScript types for all 6 realtime message payloads.
 * Matches Section 5 of the platform spec exactly.
 *
 * Broadcast-first (facilitator-side dedup only):
 *   - poll.response
 *   - word_cloud.submit
 *   - confidence.submit
 *
 * Authoritative-state (server-persisted via API, checked against processed_events):
 *   - risk.aggregate
 *   - qna.question
 *   - qna.upvote
 */

// ---------------------------------------------------------------------------
// Base fields shared by every realtime message
// ---------------------------------------------------------------------------
export interface RealtimeMessageBase {
  eventId: string; // UUID, client-generated
  workshopSessionId: string;
  anonymousSessionId: string;
  createdAt: string; // ISO 8601
}

// ---------------------------------------------------------------------------
// 1. Poll Response (broadcast-first)
// ---------------------------------------------------------------------------
export interface PollResponsePayload extends RealtimeMessageBase {
  type: 'poll.response';
  pollId: string;
  optionId: string;
}

// ---------------------------------------------------------------------------
// 2. Word Cloud Submission (broadcast-first)
// ---------------------------------------------------------------------------
export interface WordCloudSubmitPayload extends RealtimeMessageBase {
  type: 'word_cloud.submit';
  promptId: string;
  phrase: string; // max 50 chars
}

// ---------------------------------------------------------------------------
// 3. Confidence Slider (broadcast-first)
// ---------------------------------------------------------------------------
export interface ConfidenceSubmitPayload extends RealtimeMessageBase {
  type: 'confidence.submit';
  phase: 'before' | 'after';
  value: number; // integer 1-10
}

// ---------------------------------------------------------------------------
// 4. Risk Scanner Aggregate (authoritative-state)
// ---------------------------------------------------------------------------
export interface RiskAggregatePayload extends RealtimeMessageBase {
  type: 'risk.aggregate';
  riskTier: 'low' | 'medium' | 'high' | 'critical';
  topRiskDepartments: string[];
}

// ---------------------------------------------------------------------------
// 5. Q&A Question (authoritative-state)
// ---------------------------------------------------------------------------
export interface QnaQuestionPayload extends RealtimeMessageBase {
  type: 'qna.question';
  questionText: string;
}

/** Broadcast payload includes the server-assigned questionId. */
export interface QnaQuestionBroadcast extends QnaQuestionPayload {
  questionId: string;
}

// ---------------------------------------------------------------------------
// 6. Q&A Upvote (authoritative-state)
// ---------------------------------------------------------------------------
export interface QnaUpvotePayload extends RealtimeMessageBase {
  type: 'qna.upvote';
  questionId: string;
}

/** Broadcast payload includes the updated upvote count. */
export interface QnaUpvoteBroadcast extends QnaUpvotePayload {
  upvoteCount: number;
}

// ---------------------------------------------------------------------------
// Union type for all broadcast-first payloads
// ---------------------------------------------------------------------------
export type BroadcastFirstPayload =
  | PollResponsePayload
  | WordCloudSubmitPayload
  | ConfidenceSubmitPayload;

// ---------------------------------------------------------------------------
// Union type for all authoritative-state payloads
// ---------------------------------------------------------------------------
export type AuthoritativeStatePayload =
  | RiskAggregatePayload
  | QnaQuestionPayload
  | QnaUpvotePayload;

// ---------------------------------------------------------------------------
// Union of every realtime message type
// ---------------------------------------------------------------------------
export type RealtimePayload = BroadcastFirstPayload | AuthoritativeStatePayload;

// ---------------------------------------------------------------------------
// Message type literal union (useful for switch/case)
// ---------------------------------------------------------------------------
export type RealtimeMessageType =
  | 'poll.response'
  | 'word_cloud.submit'
  | 'confidence.submit'
  | 'risk.aggregate'
  | 'qna.question'
  | 'qna.upvote';
