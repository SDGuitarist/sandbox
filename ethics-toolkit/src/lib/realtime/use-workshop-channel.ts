"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { RealtimeChannel } from "@supabase/supabase-js";

/**
 * Single shared Realtime channel for a workshop session.
 * Use this in the dashboard page and pass the channel + connected state
 * down to all facilitator widgets. This avoids 5 separate WebSocket
 * connections (one per widget).
 */
export function useWorkshopChannel(workshopSessionId: string | null) {
  const [connected, setConnected] = useState(false);
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    if (!workshopSessionId) return;

    const supabase = createClient();
    const channel = supabase.channel(`workshop:${workshopSessionId}`);
    channelRef.current = channel;

    channel.subscribe((status) => {
      setConnected(status === "SUBSCRIBED");
    });

    return () => {
      supabase.removeChannel(channel);
      channelRef.current = null;
      setConnected(false);
    };
  }, [workshopSessionId]);

  return { channel: channelRef.current, connected };
}
