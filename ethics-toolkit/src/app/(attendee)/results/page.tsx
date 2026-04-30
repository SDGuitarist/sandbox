"use client";

import { useEffect, useState } from "react";
import { createBrowserClient } from "@/lib/supabase/client";
import { getOrCreateAnonymousSessionId } from "@/lib/auth/anonymous-session";
import Link from "next/link";

interface ToolEvent {
  id: string;
  tool_type: string;
  deterministic_payload: Record<string, unknown>;
  created_at: string;
}

const TOOL_LABELS: Record<string, string> = {
  DISCLOSURE: "AI Disclosure Generator",
  RISK: "Project Risk Scanner",
  PROVENANCE: "AI Provenance Chain",
  BUDGET: "Budget vs. Ethics Calculator",
};

const TOOL_LINKS: Record<string, string> = {
  DISCLOSURE: "/tools/disclosure",
  RISK: "/tools/risk",
  PROVENANCE: "/tools/provenance",
  BUDGET: "/tools/budget",
};

export default function ResultsPage() {
  const [events, setEvents] = useState<ToolEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadResults() {
      try {
        const anonymousSessionId = getOrCreateAnonymousSessionId();
        const supabase = createBrowserClient();

        const { data } = await supabase
          .from("tool_events")
          .select("id, tool_type, deterministic_payload, created_at")
          .eq("anonymous_session_id", anonymousSessionId)
          .order("created_at", { ascending: false });

        setEvents(data ?? []);
      } catch {
        setEvents([]);
      } finally {
        setLoading(false);
      }
    }

    loadResults();
  }, []);

  if (loading) {
    return (
      <div className="px-4 py-6 max-w-lg mx-auto">
        <p className="text-base text-gray-600">Loading results...</p>
      </div>
    );
  }

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">Your Results</h1>
      {events.length === 0 ? (
        <div>
          <p className="text-base text-gray-600 mb-4">
            No results yet. Use a tool to get started.
          </p>
          <Link
            href="/"
            className="min-h-[2.75rem] min-w-[2.75rem] inline-flex items-center justify-center px-6 py-3 text-base font-medium rounded-lg bg-black text-white"
          >
            Go to Tools
          </Link>
        </div>
      ) : (
        <ul className="space-y-3">
          {events.map((event) => (
            <li key={event.id}>
              <Link
                href={TOOL_LINKS[event.tool_type] ?? "/"}
                className="block min-h-[2.75rem] p-4 rounded-lg border border-gray-200 active:bg-gray-50"
              >
                <span className="text-base font-medium block">
                  {TOOL_LABELS[event.tool_type] ?? event.tool_type}
                </span>
                <span className="text-sm text-gray-500 block mt-1">
                  {new Date(event.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
