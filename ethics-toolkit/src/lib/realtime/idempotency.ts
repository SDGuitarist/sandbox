/**
 * Facilitator-side in-memory idempotency for broadcast-first interactions.
 *
 * Broadcast-first messages (poll.response, word_cloud.submit, confidence.submit)
 * do NOT hit the server. The facilitator client is responsible for deduplicating
 * messages using an in-memory Set<string> of received eventId values.
 *
 * This is NOT the processed_events table. That table is used only by the
 * authoritative-state API routes (risk.aggregate, qna.question, qna.upvote).
 *
 * One IdempotencyGuard instance should be created per workshop session on the
 * facilitator client. It is discarded when the session ends or the page unloads.
 */

export class IdempotencyGuard {
  private seen: Set<string>;

  constructor() {
    this.seen = new Set<string>();
  }

  /**
   * Check whether an eventId has already been processed.
   *
   * @param eventId - The UUID from the broadcast message.
   * @returns `true` if this is a NEW event (not seen before), `false` if duplicate.
   *
   * Usage:
   * ```ts
   * const guard = new IdempotencyGuard();
   *
   * function handleMessage(payload: RealtimePayload) {
   *   if (!guard.check(payload.eventId)) {
   *     // Duplicate -- ignore
   *     return;
   *   }
   *   // Process the message
   * }
   * ```
   */
  check(eventId: string): boolean {
    if (this.seen.has(eventId)) {
      return false;
    }
    this.seen.add(eventId);
    return true;
  }

  /**
   * Returns the number of unique events tracked so far.
   * Useful for debugging and monitoring.
   */
  get size(): number {
    return this.seen.size;
  }

  /**
   * Clear all tracked events. Call this when a workshop session ends
   * to free memory.
   */
  clear(): void {
    this.seen.clear();
  }
}

/**
 * Factory function that returns a plain Set<string> for facilitator-side
 * broadcast dedup. The facilitator components use .has() and .add() directly.
 *
 * This is the simplest possible idempotency mechanism as specified in the
 * spec: an in-memory Set<string> of received eventId values.
 */
export function createIdempotencySet(): Set<string> {
  return new Set<string>();
}
