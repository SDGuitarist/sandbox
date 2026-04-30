"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { PollChart } from "@/components/facilitator/poll-chart";
import { WordCloud } from "@/components/facilitator/word-cloud";
import { RiskBreakdown } from "@/components/facilitator/risk-breakdown";
import { ConfidenceDelta } from "@/components/facilitator/confidence-delta";
import { QnAQueue } from "@/components/facilitator/qna-queue";

/**
 * Facilitator Dashboard Page
 *
 * Main layout that renders all six realtime widgets for the active
 * workshop session. The facilitator selects (or is routed to) the
 * active session, and all widgets subscribe to the same
 * `workshop:{workshopSessionId}` channel.
 *
 * - All aggregated widgets use MinResponseGuard internally
 *   (< 5 responses = "Waiting for more responses").
 * - Live connection status shown per widget.
 */

interface WorkshopSession {
  id: string;
  session_code: string;
  status: string;
  started_at: string;
}

export default function FacilitatorDashboardPage() {
  const [sessions, setSessions] = useState<WorkshopSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadActiveSessions() {
      try {
        const supabase = createClient();
        const { data } = await supabase
          .from("workshop_sessions")
          .select("id, session_code, status, started_at")
          .eq("status", "active")
          .order("started_at", { ascending: false });

        const activeSessions = data ?? [];
        setSessions(activeSessions);

        // Auto-select the most recent active session
        if (activeSessions.length > 0 && !activeSessionId) {
          setActiveSessionId(activeSessions[0].id);
        }
      } catch {
        setSessions([]);
      } finally {
        setLoading(false);
      }
    }

    loadActiveSessions();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="py-12 text-center">
        <p className="text-base text-gray-500">Loading dashboard...</p>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="py-12 text-center">
        <h1 className="text-2xl font-bold mb-2">Facilitator Dashboard</h1>
        <p className="text-base text-gray-500">
          No active workshop sessions. Create one from the{" "}
          <a href="/facilitator" className="text-blue-600 underline">
            sessions page
          </a>
          .
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-2xl font-bold">Facilitator Dashboard</h1>

        {sessions.length > 1 && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-gray-600">Session:</span>
            <select
              value={activeSessionId ?? ""}
              onChange={(e) => setActiveSessionId(e.target.value)}
              className="rounded-md border border-gray-300 px-2 py-1 text-sm"
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.session_code}
                </option>
              ))}
            </select>
          </label>
        )}

        {sessions.length === 1 && (
          <span className="inline-flex items-center gap-1 text-sm text-gray-500">
            Session:{" "}
            <span className="font-mono font-medium">
              {sessions[0].session_code}
            </span>
          </span>
        )}
      </div>

      {/* Dashboard Grid */}
      {activeSessionId && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Row 1: Poll + Word Cloud */}
          <PollChart workshopSessionId={activeSessionId} />
          <WordCloud workshopSessionId={activeSessionId} />

          {/* Row 2: Risk + Confidence */}
          <RiskBreakdown workshopSessionId={activeSessionId} />
          <ConfidenceDelta workshopSessionId={activeSessionId} />

          {/* Row 3: Q&A (full width) */}
          <div className="md:col-span-2">
            <QnAQueue workshopSessionId={activeSessionId} />
          </div>
        </div>
      )}

      {/* Legal disclaimer required by Section 1 */}
      <p className="mt-6 text-xs text-gray-400 text-center">
        Guidance, not legal advice. Consult an entertainment attorney for legal
        counsel.
      </p>
    </div>
  );
}
