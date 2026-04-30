"use client";

import { useState, useCallback } from "react";
import { broadcastPollResponse } from "@/lib/realtime/broadcast";
import type { PollResponseMessage } from "@/lib/realtime/types";
import { getAnonymousSessionId } from "@/lib/auth/anonymous-session";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface PollOption {
  id: string;
  label: string;
}

interface PollResponseProps {
  channel: RealtimeChannel;
  workshopSessionId: string;
  pollId: string;
  question: string;
  options: PollOption[];
}

export function PollResponse({
  channel,
  workshopSessionId,
  pollId,
  question,
  options,
}: PollResponseProps) {
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

  const handleSelect = useCallback(
    async (optionId: string) => {
      if (selectedOptionId || isSending) return;

      setIsSending(true);
      setSelectedOptionId(optionId);

      const anonymousSessionId = getAnonymousSessionId();
      const message: PollResponseMessage = {
        eventId: crypto.randomUUID(),
        type: "poll.response",
        workshopSessionId,
        anonymousSessionId,
        pollId,
        optionId,
        createdAt: new Date().toISOString(),
      };

      try {
        await broadcastPollResponse(channel, message);
      } catch {
        // Broadcast is fire-and-forget for attendees.
        // Selection is still visually confirmed even if broadcast fails.
      } finally {
        setIsSending(false);
      }
    },
    [channel, workshopSessionId, pollId, selectedOptionId, isSending]
  );

  return (
    <div className="flex flex-col gap-4 px-4 pb-24">
      <h2 className="text-lg font-semibold text-gray-900">{question}</h2>

      <div className="flex flex-col gap-3">
        {options.map((option) => {
          const isSelected = selectedOptionId === option.id;
          const isDisabled = selectedOptionId !== null;

          return (
            <button
              key={option.id}
              type="button"
              onClick={() => handleSelect(option.id)}
              disabled={isDisabled}
              aria-pressed={isSelected}
              className={`
                min-h-[2.75rem] w-full px-4 py-4 text-base text-left rounded-lg
                border-2 transition-colors
                ${
                  isSelected
                    ? "border-black bg-black text-white"
                    : isDisabled
                      ? "border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed"
                      : "border-gray-300 bg-white text-gray-900 active:bg-gray-100"
                }
              `}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {selectedOptionId && (
        <p className="text-sm text-gray-500 text-center" aria-live="polite">
          Response submitted
        </p>
      )}
    </div>
  );
}
