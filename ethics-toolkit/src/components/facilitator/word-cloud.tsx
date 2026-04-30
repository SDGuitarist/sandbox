"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { createClient } from "@/lib/supabase/client";
import { createIdempotencySet } from "@/lib/realtime/idempotency";
import type { WordCloudSubmitPayload } from "@/lib/realtime/types";
import { MinResponseGuard } from "./min-response-guard";

/**
 * WordCloud
 *
 * Subscribes to word_cloud.submit broadcasts and renders phrases
 * sized proportionally by frequency. Pure CSS implementation -- no
 * external chart library required.
 *
 * - Facilitator-side dedup via in-memory Set (Section 5).
 * - MinResponseGuard when < 5 submissions (Section 1).
 */

interface WordCloudProps {
  workshopSessionId: string;
}

/** Map font size between min and max based on frequency */
function fontSize(count: number, maxCount: number): number {
  const MIN_SIZE = 14;
  const MAX_SIZE = 48;
  if (maxCount <= 1) return MIN_SIZE;
  return MIN_SIZE + ((count - 1) / (maxCount - 1)) * (MAX_SIZE - MIN_SIZE);
}

/** Deterministic colour based on string hash (keeps it visually varied) */
const COLORS = [
  "text-blue-600",
  "text-indigo-600",
  "text-purple-600",
  "text-pink-600",
  "text-teal-600",
  "text-emerald-600",
  "text-amber-600",
  "text-rose-600",
];

function colorForPhrase(phrase: string): string {
  let hash = 0;
  for (let i = 0; i < phrase.length; i++) {
    hash = (hash << 5) - hash + phrase.charCodeAt(i);
    hash |= 0;
  }
  return COLORS[Math.abs(hash) % COLORS.length];
}

export function WordCloud({ workshopSessionId }: WordCloudProps) {
  const [frequencies, setFrequencies] = useState<Record<string, number>>({});
  const [connected, setConnected] = useState(false);
  const seenRef = useRef(createIdempotencySet());

  const totalSubmissions = Object.values(frequencies).reduce(
    (s, n) => s + n,
    0
  );

  const handleSubmission = useCallback(
    (payload: WordCloudSubmitPayload) => {
      if (seenRef.current.has(payload.eventId)) return;
      seenRef.current.add(payload.eventId);

      // Normalise: lowercase, trimmed
      const normalised = payload.phrase.trim().toLowerCase();
      if (!normalised) return;

      setFrequencies((prev) => ({
        ...prev,
        [normalised]: (prev[normalised] ?? 0) + 1,
      }));
    },
    []
  );

  useEffect(() => {
    const supabase = createClient();

    const channel = supabase.channel(`workshop:${workshopSessionId}`);

    channel
      .on("broadcast", { event: "word_cloud.submit" }, (msg) => {
        const data = msg.payload as WordCloudSubmitPayload;
        handleSubmission(data);
      })
      .subscribe((status) => {
        setConnected(status === "SUBSCRIBED");
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [workshopSessionId, handleSubmission]);

  const sortedPhrases = useMemo(
    () =>
      Object.entries(frequencies).sort(([, a], [, b]) => b - a),
    [frequencies]
  );

  const maxCount = sortedPhrases.length > 0 ? sortedPhrases[0][1] : 1;

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold">Word Cloud</h3>
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

      <MinResponseGuard count={totalSubmissions} label="submissions">
        {sortedPhrases.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">
            No submissions yet.
          </p>
        ) : (
          <div
            className="flex flex-wrap items-center justify-center gap-3 py-4"
            role="img"
            aria-label="Word cloud of attendee submissions"
          >
            {sortedPhrases.map(([phrase, count]) => (
              <span
                key={phrase}
                className={`font-semibold leading-tight transition-all duration-300 ${colorForPhrase(phrase)}`}
                style={{ fontSize: `${fontSize(count, maxCount)}px` }}
                title={`${phrase} (${count})`}
              >
                {phrase}
              </span>
            ))}
          </div>
        )}
        <p className="text-xs text-gray-400 mt-2 text-right">
          {totalSubmissions} total submissions
        </p>
      </MinResponseGuard>
    </section>
  );
}
