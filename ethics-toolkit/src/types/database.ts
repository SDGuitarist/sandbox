export type EntitlementStatus = 'free' | 'trial' | 'active' | 'past_due' | 'cancelled' | 'expired';
export type AiPolicy = 'banned' | 'restricted' | 'disclosure_required' | 'allowed' | 'no_stated_policy';
export type ConfidenceLevel = 'verified' | 'inferred' | 'unverified';
export type RiskTier = 'low' | 'medium' | 'high' | 'critical';
export type ToolType = 'DISCLOSURE' | 'RISK' | 'PROVENANCE' | 'BUDGET';
export type WorkshopStatus = 'active' | 'ended';
export type EmailType = 'welcome' | 'day12_warning' | 'day14_downgrade';
export type EmailJobStatus = 'pending' | 'sent' | 'failed' | 'skipped';

export interface Profile {
  user_id: string;
  email: string;
  email_opt_out: boolean;
  trial_started_at: string | null;
  trial_ends_at: string | null;
  current_trial_id: string | null;
  entitlement_status: EntitlementStatus;
  created_at: string;
  updated_at: string;
}

export interface AnonymousSession {
  id: string;
  anonymous_session_id: string;
  user_id: string | null;
  created_at: string;
  claimed_at: string | null;
}

export interface WorkshopSession {
  id: string;
  session_code: string;
  facilitator_id: string | null;
  started_at: string;
  ended_at: string | null;
  status: WorkshopStatus;
}

export interface ToolEvent {
  id: string;
  event_id: string;
  schema_version: number;
  workshop_session_id: string | null;
  anonymous_session_id: string;
  user_id: string | null;
  tool_type: ToolType;
  deterministic_payload: Record<string, unknown>;
  probabilistic_payload: Record<string, unknown> | null;
  created_at: string;
}

export interface FestivalPolicy {
  id: string;
  festival_name: string;
  year: number;
  ai_policy: AiPolicy;
  policy_details: string;
  source_url: string;
  last_reviewed_date: string;
  confidence_level: ConfidenceLevel;
  categories: string[];
  created_at: string;
  updated_at: string;
}

export interface WorkshopRiskScore {
  id: string;
  event_id: string;
  workshop_session_id: string;
  anonymous_session_id: string;
  risk_tier: RiskTier;
  top_risk_departments: string[];
  created_at: string;
}

export interface QnaQuestion {
  id: string;
  event_id: string;
  workshop_session_id: string;
  anonymous_session_id: string;
  question_text: string;
  upvote_count: number;
  created_at: string;
}

export interface QnaVote {
  id: string;
  event_id: string;
  question_id: string;
  anonymous_session_id: string;
  created_at: string;
}

export interface ProcessedEvent {
  event_id: string;
  anonymous_session_id: string;
  created_at: string;
}

export interface SquareEntitlement {
  id: string;
  user_id: string;
  square_customer_id: string | null;
  square_subscription_id: string | null;
  square_payment_id: string | null;
  current_period_ends_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmailJob {
  id: string;
  user_id: string;
  email_type: EmailType;
  trial_id: string | null;
  scheduled_for: string;
  sent_at: string | null;
  status: EmailJobStatus;
  idempotency_key: string;
  created_at: string;
}

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: Profile;
        Insert: Omit<Profile, 'created_at' | 'updated_at'> & {
          email_opt_out?: boolean;
          entitlement_status?: EntitlementStatus;
          created_at?: string;
          updated_at?: string;
        };
        Update: Partial<Omit<Profile, 'user_id'>>;
      };
      anonymous_sessions: {
        Row: AnonymousSession;
        Insert: Omit<AnonymousSession, 'id' | 'created_at'> & {
          id?: string;
          created_at?: string;
        };
        Update: Partial<Omit<AnonymousSession, 'id'>>;
      };
      workshop_sessions: {
        Row: WorkshopSession;
        Insert: Omit<WorkshopSession, 'id' | 'started_at'> & {
          id?: string;
          status?: WorkshopStatus;
          started_at?: string;
        };
        Update: Partial<Omit<WorkshopSession, 'id'>>;
      };
      tool_events: {
        Row: ToolEvent;
        Insert: Omit<ToolEvent, 'id' | 'created_at'> & {
          id?: string;
          schema_version?: number;
          created_at?: string;
        };
        Update: Partial<Omit<ToolEvent, 'id'>>;
      };
      festival_policies: {
        Row: FestivalPolicy;
        Insert: Omit<FestivalPolicy, 'id' | 'created_at' | 'updated_at'> & {
          id?: string;
          created_at?: string;
          updated_at?: string;
        };
        Update: Partial<Omit<FestivalPolicy, 'id'>>;
      };
      workshop_risk_scores: {
        Row: WorkshopRiskScore;
        Insert: Omit<WorkshopRiskScore, 'id' | 'created_at'> & {
          id?: string;
          created_at?: string;
        };
        Update: Partial<Omit<WorkshopRiskScore, 'id'>>;
      };
      qna_questions: {
        Row: QnaQuestion;
        Insert: Omit<QnaQuestion, 'id' | 'created_at'> & {
          id?: string;
          upvote_count?: number;
          created_at?: string;
        };
        Update: Partial<Omit<QnaQuestion, 'id'>>;
      };
      qna_votes: {
        Row: QnaVote;
        Insert: Omit<QnaVote, 'id' | 'created_at'> & {
          id?: string;
          created_at?: string;
        };
        Update: Partial<Omit<QnaVote, 'id'>>;
      };
      processed_events: {
        Row: ProcessedEvent;
        Insert: Omit<ProcessedEvent, 'created_at'> & {
          created_at?: string;
        };
        Update: Partial<ProcessedEvent>;
      };
      square_entitlements: {
        Row: SquareEntitlement;
        Insert: Omit<SquareEntitlement, 'id' | 'created_at' | 'updated_at'> & {
          id?: string;
          created_at?: string;
          updated_at?: string;
        };
        Update: Partial<Omit<SquareEntitlement, 'id'>>;
      };
      email_jobs: {
        Row: EmailJob;
        Insert: Omit<EmailJob, 'id' | 'created_at'> & {
          id?: string;
          status?: EmailJobStatus;
          created_at?: string;
        };
        Update: Partial<Omit<EmailJob, 'id'>>;
      };
    };
  };
}
