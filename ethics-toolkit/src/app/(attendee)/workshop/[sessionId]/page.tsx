"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { createWorkshopChannel } from "@/lib/realtime/channel";
import { getAnonymousSessionId } from "@/lib/auth/anonymous-session";
import { PollResponse } from "@/components/attendee/poll-response";
import { WordCloudInput } from "@/components/attendee/word-cloud-input";
import { ConfidenceSlider } from "@/components/attendee/confidence-slider";
import { QnaSubmit } from "@/components/attendee/qna-submit";
import { QnaList } from "@/components/attendee/qna-list";
import type { RealtimeChannel } from "@supabase/supabase-js";

type ActiveInteraction =
  | {
      type: "poll";
      pollId: string;
      question: string;
      options: { id: string; label: string }[];
    }
  | {
      type: "word_cloud";
      promptId: string;
      prompt: string;
    }
  | {
      type: "confidence";
      phase: "before" | "after";
      prompt: string;
    }
  | {
      type: "qna";
    }
  | null;

export default function WorkshopLivePage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [channel, setChannel] = useState<RealtimeChannel | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isValidSession, setIsValidSession] = useState<boolean | null>(null);
  const [activeInteraction, setActiveInteraction] =
    useState<ActiveInteraction>(null);

  // Validate session and set up channel
  useEffect(() => {
    let mounted = true;
    let workshopChannel: RealtimeChannel | null = null;

    const setup = async () => {
      const supabase = createClient();

      // Validate the workshop session exists and is active
      const { data: session } = await supabase
        .from("workshop_sessions")
        .select("id, status")
        .eq("id", sessionId)
        .single();

      if (!mounted) return;

      if (!session || session.status !== "active") {
        setIsValidSession(false);
        return;
      }

      setIsValidSession(true);

      // Create realtime channel
      workshopChannel = createWorkshopChannel(supabase, sessionId);

      workshopChannel.subscribe((status) => {
        if (!mounted) return;
        setIsConnected(status === "SUBSCRIBED");
      });

      // Listen for facilitator-driven interaction changes
      workshopChannel.on(
        "broadcast",
        { event: "interaction" },
        (payload) => {
          if (!mounted) return;
          const data = payload.payload as ActiveInteraction;
          setActiveInteraction(data);
        }
      );

      setChannel(workshopChannel);
    };

    setup();

    return () => {
      mounted = false;
      if (workshopChannel) {
        workshopChannel.unsubscribe();
      }
    };
  }, [sessionId]);

  const handleQuestionSubmitted = useCallback(() => {
    // No-op callback -- QnaList auto-updates via realtime
  }, []);

  // Loading state while validating session
  if (isValidSession === null) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] px-4">
        <p className="text-base text-gray-400">Joining workshop...</p>
      </div>
    );
  }

  // Invalid or ended session
  if (!isValidSession) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 gap-4">
        <p className="text-lg font-semibold text-gray-900">
          Workshop Not Found
        </p>
        <p className="text-base text-gray-500 text-center">
          This workshop session has ended or does not exist.
        </p>
      </div>
    );
  }

  // Connection lost
  if (!isConnected && channel) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 gap-4">
        <p className="text-lg font-semibold text-gray-900">Reconnecting...</p>
        <p className="text-base text-gray-500 text-center">
          Your connection was interrupted. Trying to reconnect.
        </p>
      </div>
    );
  }

  // Waiting for facilitator to start an interaction
  if (!activeInteraction || !channel) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 gap-4">
        <p className="text-lg font-semibold text-gray-900">You are in!</p>
        <p className="text-base text-gray-500 text-center">
          Waiting for the facilitator to start an activity...
        </p>
        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
      </div>
    );
  }

  // Render the active interaction
  return (
    <div className="min-h-[60vh] pt-4">
      {activeInteraction.type === "poll" && (
        <PollResponse
          channel={channel}
          workshopSessionId={sessionId}
          pollId={activeInteraction.pollId}
          question={activeInteraction.question}
          options={activeInteraction.options}
        />
      )}

      {activeInteraction.type === "word_cloud" && (
        <WordCloudInput
          channel={channel}
          workshopSessionId={sessionId}
          promptId={activeInteraction.promptId}
          prompt={activeInteraction.prompt}
        />
      )}

      {activeInteraction.type === "confidence" && (
        <ConfidenceSlider
          channel={channel}
          workshopSessionId={sessionId}
          phase={activeInteraction.phase}
          prompt={activeInteraction.prompt}
        />
      )}

      {activeInteraction.type === "qna" && (
        <div className="flex flex-col gap-6">
          <QnaSubmit
            workshopSessionId={sessionId}
            onQuestionSubmitted={handleQuestionSubmitted}
          />
          <QnaList channel={channel} workshopSessionId={sessionId} />
        </div>
      )}
    </div>
  );
}
