"use client";

import { useState, useCallback } from "react";
import { getAnonymousSessionId } from "@/lib/auth/anonymous-session";

interface QnaSubmitProps {
  workshopSessionId: string;
  onQuestionSubmitted?: () => void;
}

export function QnaSubmit({
  workshopSessionId,
  onQuestionSubmitted,
}: QnaSubmitProps) {
  const [questionText, setQuestionText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    const trimmed = questionText.trim();
    if (!trimmed || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    const anonymousSessionId = getAnonymousSessionId();

    try {
      const response = await fetch("/api/workshop/qna/question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          eventId: crypto.randomUUID(),
          workshopSessionId,
          anonymousSessionId,
          questionText: trimmed,
        }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || "Failed to submit question");
      }

      setIsSubmitted(true);
      setQuestionText("");
      onQuestionSubmitted?.();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong. Try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  }, [questionText, isSubmitting, workshopSessionId, onQuestionSubmitted]);

  if (isSubmitted) {
    return (
      <div className="flex flex-col items-center gap-4 px-4 pb-24">
        <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-6 w-full text-center">
          <p className="text-base text-gray-900 font-medium">
            Question submitted
          </p>
          <button
            type="button"
            onClick={() => setIsSubmitted(false)}
            className="mt-3 text-sm text-gray-500 underline"
          >
            Ask another question
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 px-4 pb-24">
      <h2 className="text-lg font-semibold text-gray-900">Ask a Question</h2>

      <textarea
        value={questionText}
        onChange={(e) => setQuestionText(e.target.value)}
        placeholder="Type your question..."
        aria-label="Question text"
        rows={3}
        className="w-full px-4 py-3 text-base border-2 border-gray-300 rounded-lg
          resize-none focus:border-black focus:outline-none"
      />

      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3 z-50">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!questionText.trim() || isSubmitting}
          className={`
            min-h-[2.75rem] w-full px-6 py-3 text-base font-medium rounded-lg text-center
            ${
              questionText.trim() && !isSubmitting
                ? "bg-black text-white"
                : "bg-gray-200 text-gray-400 cursor-not-allowed"
            }
          `}
        >
          {isSubmitting ? "Submitting..." : "Submit Question"}
        </button>
      </div>
    </div>
  );
}
