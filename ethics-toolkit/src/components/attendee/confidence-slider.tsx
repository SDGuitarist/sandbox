"use client";

import { useState, useCallback } from "react";
import { broadcastConfidenceSubmit } from "@/lib/realtime/broadcast";
import type { ConfidenceSubmitMessage } from "@/lib/realtime/types";
import { getAnonymousSessionId } from "@/lib/auth/anonymous-session";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface ConfidenceSliderProps {
  channel: RealtimeChannel;
  workshopSessionId: string;
  phase: "before" | "after";
  prompt: string;
}

export function ConfidenceSlider({
  channel,
  workshopSessionId,
  phase,
  prompt,
}: ConfidenceSliderProps) {
  const [value, setValue] = useState(5);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (isSending || isSubmitted) return;

    setIsSending(true);

    const anonymousSessionId = getAnonymousSessionId();
    const message: ConfidenceSubmitMessage = {
      eventId: crypto.randomUUID(),
      type: "confidence.submit",
      workshopSessionId,
      anonymousSessionId,
      phase,
      value,
      createdAt: new Date().toISOString(),
    };

    try {
      await broadcastConfidenceSubmit(channel, message);
      setIsSubmitted(true);
    } catch {
      // Broadcast is fire-and-forget for attendees.
      setIsSubmitted(true);
    } finally {
      setIsSending(false);
    }
  }, [channel, workshopSessionId, phase, value, isSending, isSubmitted]);

  if (isSubmitted) {
    return (
      <div className="flex flex-col items-center gap-4 px-4 pb-24">
        <h2 className="text-lg font-semibold text-gray-900">{prompt}</h2>
        <div className="rounded-lg bg-gray-50 border border-gray-200 px-6 py-6 w-full text-center">
          <p className="text-4xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500 mt-2">
            {phase === "before" ? "Before" : "After"} -- submitted
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 px-4 pb-24">
      <h2 className="text-lg font-semibold text-gray-900">{prompt}</h2>

      <div className="flex flex-col items-center gap-4">
        <p className="text-sm text-gray-500 uppercase tracking-wide">
          {phase === "before" ? "Before" : "After"}
        </p>

        <p className="text-5xl font-bold text-gray-900" aria-live="polite">
          {value}
        </p>

        <div className="w-full flex items-center gap-3">
          <span className="text-sm text-gray-400 w-6 text-center">1</span>
          <input
            type="range"
            min={1}
            max={10}
            step={1}
            value={value}
            onChange={(e) => setValue(parseInt(e.target.value, 10))}
            aria-label={`Confidence level: ${value} out of 10`}
            className="flex-1 h-10 accent-black cursor-pointer"
          />
          <span className="text-sm text-gray-400 w-6 text-center">10</span>
        </div>

        <div className="flex justify-between w-full px-9 text-xs text-gray-400">
          <span>Not confident</span>
          <span>Very confident</span>
        </div>
      </div>

      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3 z-50">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isSending}
          className={`
            min-h-[2.75rem] w-full px-6 py-3 text-base font-medium rounded-lg text-center
            ${
              !isSending
                ? "bg-black text-white"
                : "bg-gray-200 text-gray-400 cursor-not-allowed"
            }
          `}
        >
          {isSending ? "Submitting..." : `Submit (${value}/10)`}
        </button>
      </div>
    </div>
  );
}
