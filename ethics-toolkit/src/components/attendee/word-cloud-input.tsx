"use client";

import { useState, useCallback } from "react";
import { broadcastWordCloudSubmit } from "@/lib/realtime/broadcast";
import type { WordCloudSubmitMessage } from "@/lib/realtime/types";
import { getAnonymousSessionId } from "@/lib/auth/anonymous-session";
import type { RealtimeChannel } from "@supabase/supabase-js";

const MAX_CHARS = 50;

interface WordCloudInputProps {
  channel: RealtimeChannel;
  workshopSessionId: string;
  promptId: string;
  prompt: string;
}

export function WordCloudInput({
  channel,
  workshopSessionId,
  promptId,
  prompt,
}: WordCloudInputProps) {
  const [phrase, setPhrase] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const charsRemaining = MAX_CHARS - phrase.length;

  const handleSubmit = useCallback(async () => {
    const trimmed = phrase.trim();
    if (!trimmed || isSending || isSubmitted) return;

    setIsSending(true);

    const anonymousSessionId = getAnonymousSessionId();
    const message: WordCloudSubmitMessage = {
      eventId: crypto.randomUUID(),
      type: "word_cloud.submit",
      workshopSessionId,
      anonymousSessionId,
      promptId,
      phrase: trimmed,
      createdAt: new Date().toISOString(),
    };

    try {
      await broadcastWordCloudSubmit(channel, message);
      setIsSubmitted(true);
    } catch {
      // Broadcast is fire-and-forget for attendees.
      setIsSubmitted(true);
    } finally {
      setIsSending(false);
    }
  }, [channel, workshopSessionId, promptId, phrase, isSending, isSubmitted]);

  if (isSubmitted) {
    return (
      <div className="flex flex-col items-center gap-4 px-4 pb-24">
        <h2 className="text-lg font-semibold text-gray-900">{prompt}</h2>
        <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-6 w-full text-center">
          <p className="text-base text-gray-900 font-medium">{phrase.trim()}</p>
          <p className="text-sm text-gray-500 mt-2" aria-live="polite">
            Submitted
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 px-4 pb-24">
      <h2 className="text-lg font-semibold text-gray-900">{prompt}</h2>

      <div className="relative">
        <input
          type="text"
          value={phrase}
          onChange={(e) => {
            if (e.target.value.length <= MAX_CHARS) {
              setPhrase(e.target.value);
            }
          }}
          maxLength={MAX_CHARS}
          placeholder="Type a word or short phrase..."
          aria-label="Word cloud phrase"
          className="w-full px-4 py-3 text-base border-2 border-gray-300 rounded-lg
            focus:border-black focus:outline-none"
        />
        <span
          className={`absolute right-3 top-1/2 -translate-y-1/2 text-sm ${
            charsRemaining <= 10 ? "text-orange-500" : "text-gray-400"
          }`}
          aria-label={`${charsRemaining} characters remaining`}
        >
          {charsRemaining}
        </span>
      </div>

      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3 z-50">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!phrase.trim() || isSending}
          className={`
            min-h-[2.75rem] w-full px-6 py-3 text-base font-medium rounded-lg text-center
            ${
              phrase.trim() && !isSending
                ? "bg-black text-white"
                : "bg-gray-200 text-gray-400 cursor-not-allowed"
            }
          `}
        >
          {isSending ? "Submitting..." : "Submit"}
        </button>
      </div>
    </div>
  );
}
