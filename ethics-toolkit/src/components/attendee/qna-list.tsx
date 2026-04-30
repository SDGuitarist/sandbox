"use client";

import { useState, useEffect, useCallback } from "react";
import { getAnonymousSessionId } from "@/lib/auth/anonymous-session";
import { createClient } from "@/lib/supabase/client";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface Question {
  id: string;
  question_text: string;
  upvote_count: number;
}

interface QnaListProps {
  channel: RealtimeChannel;
  workshopSessionId: string;
}

export function QnaList({ channel, workshopSessionId }: QnaListProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [votedQuestionIds, setVotedQuestionIds] = useState<Set<string>>(
    new Set()
  );
  const [votingInProgress, setVotingInProgress] = useState<Set<string>>(
    new Set()
  );
  const [isLoading, setIsLoading] = useState(true);

  // Load existing questions on mount
  useEffect(() => {
    const loadQuestions = async () => {
      const supabase = createClient();

      const { data } = await supabase
        .from("qna_questions")
        .select("id, question_text, upvote_count")
        .eq("workshop_session_id", workshopSessionId)
        .order("upvote_count", { ascending: false });

      if (data) {
        setQuestions(data);
      }

      // Load this user's existing votes
      const anonymousSessionId = getAnonymousSessionId();
      const { data: votes } = await supabase
        .from("qna_votes")
        .select("question_id")
        .eq("anonymous_session_id", anonymousSessionId);

      if (votes) {
        setVotedQuestionIds(new Set(votes.map((v) => v.question_id)));
      }

      setIsLoading(false);
    };

    loadQuestions();
  }, [workshopSessionId]);

  // Listen for new questions and upvote updates via realtime broadcast
  useEffect(() => {
    const handleBroadcast = (payload: { event: string; payload: Record<string, unknown> }) => {
      const data = payload.payload;

      if (data.type === "qna.question") {
        const newQuestion: Question = {
          id: data.questionId as string,
          question_text: data.questionText as string,
          upvote_count: 0,
        };
        setQuestions((prev) => {
          // Avoid duplicates
          if (prev.some((q) => q.id === newQuestion.id)) return prev;
          return [...prev, newQuestion];
        });
      }

      if (data.type === "qna.upvote") {
        const questionId = data.questionId as string;
        const newCount = data.upvoteCount as number;
        setQuestions((prev) =>
          prev
            .map((q) =>
              q.id === questionId ? { ...q, upvote_count: newCount } : q
            )
            .sort((a, b) => b.upvote_count - a.upvote_count)
        );
      }
    };

    channel.on("broadcast", { event: "workshop" }, handleBroadcast);

    // Do NOT unsubscribe here -- the parent component owns the channel lifecycle.
    // Unsubscribing here would kill the shared channel for all sibling components.
    return () => {};
  }, [channel]);

  const handleUpvote = useCallback(
    async (questionId: string) => {
      if (votedQuestionIds.has(questionId) || votingInProgress.has(questionId)) {
        return;
      }

      setVotingInProgress((prev) => new Set(prev).add(questionId));

      const anonymousSessionId = getAnonymousSessionId();

      try {
        const response = await fetch("/api/workshop/qna/upvote", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            eventId: crypto.randomUUID(),
            workshopSessionId,
            anonymousSessionId,
            questionId,
          }),
        });

        if (response.ok) {
          setVotedQuestionIds((prev) => new Set(prev).add(questionId));
          // Optimistic update -- real count comes via broadcast
          setQuestions((prev) =>
            prev
              .map((q) =>
                q.id === questionId
                  ? { ...q, upvote_count: q.upvote_count + 1 }
                  : q
              )
              .sort((a, b) => b.upvote_count - a.upvote_count)
          );
        }
        // Duplicate upvote returns silently (per spec), so we still mark as voted
        if (response.status === 200 || response.status === 409) {
          setVotedQuestionIds((prev) => new Set(prev).add(questionId));
        }
      } catch {
        // Network error -- do not mark as voted so user can retry
      } finally {
        setVotingInProgress((prev) => {
          const next = new Set(prev);
          next.delete(questionId);
          return next;
        });
      }
    },
    [workshopSessionId, votedQuestionIds, votingInProgress]
  );

  if (isLoading) {
    return (
      <div className="px-4 py-8 text-center text-gray-400">
        Loading questions...
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="px-4 py-8 text-center text-gray-400">
        No questions yet. Be the first to ask!
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 px-4 pb-24">
      <h2 className="text-lg font-semibold text-gray-900">Questions</h2>

      <ul className="flex flex-col gap-2" role="list">
        {questions.map((question) => {
          const hasVoted = votedQuestionIds.has(question.id);
          const isVoting = votingInProgress.has(question.id);

          return (
            <li
              key={question.id}
              className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-4"
            >
              <button
                type="button"
                onClick={() => handleUpvote(question.id)}
                disabled={hasVoted || isVoting}
                aria-label={
                  hasVoted
                    ? `You voted for this question (${question.upvote_count} votes)`
                    : `Upvote this question (${question.upvote_count} votes)`
                }
                className={`
                  flex flex-col items-center justify-center min-h-[2.75rem] min-w-[2.75rem]
                  px-2 py-1 rounded-lg border-2 text-sm font-medium shrink-0
                  ${
                    hasVoted
                      ? "border-black bg-black text-white cursor-default"
                      : isVoting
                        ? "border-gray-200 bg-gray-50 text-gray-400 cursor-wait"
                        : "border-gray-300 bg-white text-gray-700 active:bg-gray-100"
                  }
                `}
              >
                <span aria-hidden="true">&#9650;</span>
                <span>{question.upvote_count}</span>
              </button>

              <p className="text-base text-gray-900 pt-1">
                {question.question_text}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
