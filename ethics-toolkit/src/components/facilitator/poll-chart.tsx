"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { createIdempotencySet } from "@/lib/realtime/idempotency";
import type { PollResponsePayload } from "@/lib/realtime/types";
import { MinResponseGuard } from "./min-response-guard";

/**
 * PollChart
 *
 * Subscribes to the workshop realtime channel and aggregates poll.response
 * messages into a bar chart grouped by optionId.
 *
 * - Uses in-memory Set for facilitator-side dedup (Section 5).
 * - Shows MinResponseGuard when < 5 responses (Section 1).
 */

interface PollChartProps {
  workshopSessionId: string;
  /** Labels to display for each optionId. Falls back to optionId string. */
  optionLabels?: Record<string, string>;
}

export function PollChart({ workshopSessionId, optionLabels }: PollChartProps) {
  const [tallies, setTallies] = useState<Record<string, number>>({});
  const [connected, setConnected] = useState(false);
  const seenRef = useRef(createIdempotencySet());

  const totalResponses = Object.values(tallies).reduce((s, n) => s + n, 0);

  const handlePollResponse = useCallback(
    (payload: PollResponsePayload) => {
      if (seenRef.current.has(payload.eventId)) return;
      seenRef.current.add(payload.eventId);

      setTallies((prev) => ({
        ...prev,
        [payload.optionId]: (prev[payload.optionId] ?? 0) + 1,
      }));
    },
    []
  );

  useEffect(() => {
    const supabase = createClient();

    const channel = supabase.channel(`workshop:${workshopSessionId}`);

    channel
      .on("broadcast", { event: "poll.response" }, (msg) => {
        const data = msg.payload as PollResponsePayload;
        handlePollResponse(data);
      })
      .subscribe((status) => {
        setConnected(status === "SUBSCRIBED");
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [workshopSessionId, handlePollResponse]);

  const maxCount = Math.max(1, ...Object.values(tallies));

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold">Poll Results</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            connected
              ? "bg-green-100 text-green-700"
              : "bg-yellow-100 text-yellow-700"
          }`}
        >
          {connected ? "Live" : "Connecting..."}
        </span>
      </div>

      <MinResponseGuard count={totalResponses} label="poll responses">
        {Object.keys(tallies).length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">
            No poll responses yet.
          </p>
        ) : (
          <div className="space-y-3">
            {Object.entries(tallies)
              .sort(([, a], [, b]) => b - a)
              .map(([optionId, count]) => {
                const widthPct = Math.round((count / maxCount) * 100);
                const label =
                  optionLabels?.[optionId] ?? optionId;

                return (
                  <div key={optionId}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="font-medium text-gray-700 truncate mr-2">
                        {label}
                      </span>
                      <span className="text-gray-500 tabular-nums">
                        {count}
                      </span>
                    </div>
                    <div className="h-5 w-full rounded bg-gray-100">
                      <div
                        className="h-5 rounded bg-blue-500 transition-all duration-300"
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            <p className="text-xs text-gray-400 mt-2 text-right">
              {totalResponses} total responses
            </p>
          </div>
        )}
      </MinResponseGuard>
    </section>
  );
}
