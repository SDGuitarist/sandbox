/**
 * Supabase Realtime channel setup.
 *
 * Channel name format: `workshop:{workshopSessionId}`
 *
 * Provides helpers to create, subscribe to, and unsubscribe from a workshop
 * realtime channel. Used by both attendee (broadcast sender) and facilitator
 * (broadcast listener) clients.
 */

import { createClient } from '@/lib/supabase/client';
import type { RealtimeChannel } from '@supabase/supabase-js';
import type { RealtimePayload, RealtimeMessageType } from './types';

// ---------------------------------------------------------------------------
// Channel factory
// ---------------------------------------------------------------------------

/**
 * Create and subscribe to a Supabase Realtime channel for a workshop session.
 *
 * @param workshopSessionId - UUID of the active workshop session.
 * @param onMessage - Callback invoked for every broadcast message received.
 * @returns The subscribed RealtimeChannel (call `unsubscribe()` on cleanup).
 */
export function subscribeToWorkshop(
  workshopSessionId: string,
  onMessage: (payload: RealtimePayload) => void
): RealtimeChannel {
  const supabase = createClient();
  const channelName = `workshop:${workshopSessionId}`;

  const channel = supabase
    .channel(channelName)
    .on('broadcast', { event: 'message' }, (event) => {
      // event.payload is the RealtimePayload sent by attendees or the server
      const payload = event.payload as RealtimePayload;
      onMessage(payload);
    })
    .subscribe();

  return channel;
}

/**
 * Unsubscribe from a workshop channel and remove it from the Supabase client.
 *
 * Safe to call multiple times; ignores already-removed channels.
 */
export async function unsubscribeFromWorkshop(
  channel: RealtimeChannel
): Promise<void> {
  const supabase = createClient();
  await supabase.removeChannel(channel);
}

/**
 * Send a broadcast message to a workshop channel.
 *
 * Used internally by the broadcast helpers in `broadcast.ts` and by server
 * routes that need to broadcast after persisting authoritative state.
 *
 * @param channel - The subscribed RealtimeChannel.
 * @param payload - The message payload (must include `type` and `eventId`).
 */
export async function broadcastToChannel(
  channel: RealtimeChannel,
  payload: RealtimePayload
): Promise<void> {
  await channel.send({
    type: 'broadcast',
    event: 'message',
    payload,
  });
}

/**
 * Create a channel reference for server-side broadcasting (e.g., from API
 * routes that persist state and then broadcast the result).
 *
 * This uses the browser Supabase client. For server-side broadcasting from
 * API routes, the route should use the service client directly.
 *
 * @param workshopSessionId - UUID of the active workshop session.
 * @returns An unsubscribed RealtimeChannel that can be used with `send()`.
 */
export function getChannelForBroadcast(
  workshopSessionId: string
): RealtimeChannel {
  const supabase = createClient();
  const channelName = `workshop:${workshopSessionId}`;

  // Subscribe is needed for sending; Supabase requires the channel to be
  // subscribed before calling send().
  const channel = supabase.channel(channelName).subscribe();
  return channel;
}

/**
 * Create a RealtimeChannel for a workshop session from an existing Supabase
 * client instance. Used by attendee components that already have a client.
 *
 * @param supabase - An existing Supabase client (browser or server).
 * @param workshopSessionId - UUID of the active workshop session.
 * @returns A RealtimeChannel (caller is responsible for subscribing/unsubscribing).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- accepts any SupabaseClient generic
export function createWorkshopChannel(
  supabase: { channel: (name: string) => RealtimeChannel },
  workshopSessionId: string
): RealtimeChannel {
  const channelName = `workshop:${workshopSessionId}`;
  return supabase.channel(channelName);
}

// Re-export types for convenience
export type { RealtimePayload, RealtimeMessageType };
