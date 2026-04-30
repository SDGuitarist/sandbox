"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { createClient } from "@/lib/supabase/client";
import { createIdempotencySet } from "@/lib/realtime/idempotency";
import type { ConfidenceSubmitPayload } from "@/lib/realtime/types";
import { MinResponseGuard } from "./min-response-guard";

/**
 * ConfidenceDelta
 *
 * Subscribes to confidence.submit broadcasts and renders a before/after
 * delta chart showing the average shift in attendee confidence (1-10 scale).
 *
 * - Facilitator-side dedup via in-memory Set (Section 5).
 * - MinResponseGuard when < 5 responses (Section 1).
 */

interface ConfidenceDeltaProps {
  workshopSessionId: string;
}

export function ConfidenceDelta({ workshopSessionId }: ConfidenceDeltaProps) {
  const [beforeValues, setBeforeValues] = useState<number[]>([]);
  const [afterValues, setAfterValues] = useState<number[]>([]);
  const [connected, setConnected] = useState(false);
  const seenRef = useRef(createIdempotencySet());

  const handleConfidence = useCallback(
    (payload: ConfidenceSubmitPayload) => {
      if (seenRef.current.has(payload.eventId)) return;
      seenRef.current.add(payload.eventId);

      if (payload.phase === "before") {
        setBeforeValues((prev) => [...prev, payload.value]);
      } else if (payload.phase === "after") {
        setAfterValues((prev) => [...prev, payload.value]);
      }
    },
    []
  );

  useEffect(() => {
    const supabase = createClient();

    const channel = supabase.channel(`workshop:${workshopSessionId}`);

    channel
      .on("broadcast", { event: "confidence.submit" }, (msg) => {
        const data = msg.payload as ConfidenceSubmitPayload;
        handleConfidence(data);
      })
      .subscribe((status) => {
        setConnected(status === "SUBSCRIBED");
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [workshopSessionId, handleConfidence]);

  const avg = (values: number[]): number => {
    if (values.length === 0) return 0;
    return values.reduce((s, v) => s + v, 0) / values.length;
  };

  const beforeAvg = useMemo(() => avg(beforeValues), [beforeValues]);
  const afterAvg = useMemo(() => avg(afterValues), [afterValues]);
  const delta = afterValues.length > 0 ? afterAvg - beforeAvg : null;

  const totalResponses = beforeValues.length + afterValues.length;

  /** Render a horizontal bar at a position out of 10 */
  function renderBar(label: string, value: number, count: number, color: string) {
    const widthPct = Math.round((value / 10) * 100);
    return (
      <div>
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="font-medium text-gray-700">{label}</span>
          <span className="text-gray-500 tabular-nums">
            {value.toFixed(1)} avg ({count} responses)
          </span>
        </div>
        <div className="h-5 w-full rounded bg-gray-100">
          <div
            className={`h-5 rounded ${color} transition-all duration-300`}
            style={{ width: `${widthPct}%` }}
          />
        </div>
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold">Confidence Delta</h3>
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

      <MinResponseGuard count={totalResponses} label="confidence ratings">
        <div className="space-y-3">
          {renderBar("Before", beforeAvg, beforeValues.length, "bg-gray-400")}
          {renderBar("After", afterAvg, afterValues.length, "bg-blue-500")}

          {delta !== null && (
            <div className="mt-4 flex items-center justify-center gap-2 py-2 rounded-lg bg-gray-50">
              <span className="text-sm text-gray-500">Shift:</span>
              <span
                className={`text-lg font-bold tabular-nums ${
                  delta > 0
                    ? "text-green-600"
                    : delta < 0
                      ? "text-red-600"
                      : "text-gray-600"
                }`}
              >
                {delta > 0 ? "+" : ""}
                {delta.toFixed(1)}
              </span>
            </div>
          )}
        </div>
      </MinResponseGuard>
    </section>
  );
}
