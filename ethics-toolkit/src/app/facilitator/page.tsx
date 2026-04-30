"use client";

import { useEffect, useState } from "react";
import { createBrowserClient } from "@/lib/supabase/client";

interface WorkshopSession {
  id: string;
  session_code: string;
  status: string;
  started_at: string;
  ended_at: string | null;
}

export default function FacilitatorPage() {
  const [sessions, setSessions] = useState<WorkshopSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  async function loadSessions() {
    try {
      const supabase = createBrowserClient();
      const { data } = await supabase
        .from("workshop_sessions")
        .select("id, session_code, status, started_at, ended_at")
        .order("started_at", { ascending: false });

      setSessions(data ?? []);
    } catch {
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSessions();
  }, []);

  async function handleCreateSession() {
    setCreating(true);
    try {
      const response = await fetch("/api/workshop/session", {
        method: "POST",
      });

      if (response.ok) {
        await loadSessions();
      }
    } catch {
      // Session creation failed
    } finally {
      setCreating(false);
    }
  }

  async function handleEndSession(sessionId: string) {
    try {
      const supabase = createBrowserClient();
      await supabase
        .from("workshop_sessions")
        .update({ status: "ended", ended_at: new Date().toISOString() })
        .eq("id", sessionId);

      await loadSessions();
    } catch {
      // End session failed
    }
  }

  if (loading) {
    return (
      <div className="px-4 py-6 max-w-lg mx-auto">
        <p className="text-base text-gray-600">Loading sessions...</p>
      </div>
    );
  }

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">Workshop Sessions</h1>
      <p className="text-base text-gray-600 mb-6">
        Create and manage workshop sessions.
      </p>

      <button
        onClick={handleCreateSession}
        disabled={creating}
        className="min-h-[2.75rem] min-w-[2.75rem] px-6 py-3 text-base font-medium rounded-lg bg-black text-white mb-6 disabled:opacity-50"
      >
        {creating ? "Creating..." : "Create New Session"}
      </button>

      {sessions.length === 0 ? (
        <p className="text-base text-gray-500">No sessions yet.</p>
      ) : (
        <ul className="space-y-3">
          {sessions.map((session) => (
            <li
              key={session.id}
              className="p-4 rounded-lg border border-gray-200 bg-white"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-base font-medium font-mono">
                  {session.session_code}
                </span>
                <span
                  className={`text-sm px-2 py-1 rounded ${
                    session.status === "active"
                      ? "bg-green-100 text-green-800"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {session.status}
                </span>
              </div>
              <p className="text-sm text-gray-500 mb-2">
                Started{" "}
                {new Date(session.started_at).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </p>
              {session.status === "active" && (
                <button
                  onClick={() => handleEndSession(session.id)}
                  className="min-h-[2.75rem] min-w-[2.75rem] px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 text-gray-700"
                >
                  End Session
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
