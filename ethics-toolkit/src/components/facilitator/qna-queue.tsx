"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { createIdempotencySet } from "@/lib/realtime/idempotency";
import type {
  QnAQuestionPayload,
  QnAUpvotePayload,
} from "@/lib/realtime/types";
import { MinResponseGuard } from "./min-response-guard";

/**
 * QnAQueue
 *
 * Subscribes to qna.question and qna.upvote broadcasts on the workshop
 * channel. Renders questions sorted by upvote_count descending, with
 * live-updating counts.
 *
 * - Facilitator-side dedup via in-memory Set (Section 5).
 * - MinResponseGuard when < 5 questions (Section 1).
 */

interface Question {
  questionId: string;
  questionText: string;
  upvoteCount: number;
  createdAt: string;
}

interface QnAQueueProps {
  workshopSessionId: string;
}

export function QnAQueue({ workshopSessionId }: QnAQueueProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [connected, setConnected] = useState(false);
  const seenRef = useRef(createIdempotencySet());

  const handleQuestion = useCallback(
    (payload: QnAQuestionPayload) => {
      if (seenRef.current.has(payload.eventId)) return;
      seenRef.current.add(payload.eventId);

      setQuestions((prev) => {
        // Avoid adding a question with the same questionId twice
        if (prev.some((q) => q.questionId === payload.questionId)) {
          return prev;
        }
        return [
          ...prev,
          {
            questionId: payload.questionId,
            questionText: payload.questionText,
            upvoteCount: 0,
            createdAt: payload.createdAt,
          },
        ];
      });
    },
    []
  );

  const handleUpvote = useCallback(
    (payload: QnAUpvotePayload) => {
      if (seenRef.current.has(payload.eventId)) return;
      seenRef.current.add(payload.eventId);

      setQuestions((prev) =>
        prev.map((q) =>
          q.questionId === payload.questionId
            ? { ...q, upvoteCount: payload.upvoteCount }
            : q
        )
      );
    },
    []
  );

  useEffect(() => {
    const supabase = createClient();

    const channel = supabase.channel(`workshop:${workshopSessionId}`);

    channel
      .on("broadcast", { event: "qna.question" }, (msg) => {
        const data = msg.payload as QnAQuestionPayload;
        handleQuestion(data);
      })
      .on("broadcast", { event: "qna.upvote" }, (msg) => {
        const data = msg.payload as QnAUpvotePayload;
        handleUpvote(data);
      })
      .subscribe((status) => {
        setConnected(status === "SUBSCRIBED");
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [workshopSessionId, handleQuestion, handleUpvote]);

  // Sort by upvote_count descending, then by createdAt ascending (oldest first for ties)
  const sorted = [...questions].sort((a, b) => {
    if (b.upvoteCount !== a.upvoteCount) return b.upvoteCount - a.upvoteCount;
    return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
  });

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold">Q&A Queue</h3>
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

      <MinResponseGuard count={questions.length} label="questions">
        {sorted.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">
            No questions yet.
          </p>
        ) : (
          <ul className="space-y-2 max-h-96 overflow-y-auto">
            {sorted.map((q) => (
              <li
                key={q.questionId}
                className="flex items-start gap-3 p-3 rounded-lg bg-gray-50"
              >
                <div className="flex flex-col items-center min-w-[2.5rem]">
                  <span className="text-lg font-bold text-blue-600 tabular-nums">
                    {q.upvoteCount}
                  </span>
                  <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                    votes
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 break-words">
                    {q.questionText}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(q.createdAt).toLocaleTimeString(undefined, {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </MinResponseGuard>
    </section>
  );
}
