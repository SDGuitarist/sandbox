"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { createIdempotencySet } from "@/lib/realtime/idempotency";
import type { RiskAggregatePayload } from "@/lib/realtime/types";
import { MinResponseGuard } from "./min-response-guard";

/**
 * RiskBreakdown
 *
 * Listens for risk.aggregate broadcasts and shows a percentage breakdown
 * of attendees by tier: low / medium / high / critical.
 *
 * - Facilitator-side dedup via in-memory Set (Section 5).
 * - MinResponseGuard when < 5 responses (Section 1).
 */

type RiskTier = "low" | "medium" | "high" | "critical";

const TIER_ORDER: RiskTier[] = ["low", "medium", "high", "critical"];

const TIER_STYLES: Record<RiskTier, { bg: string; bar: string; text: string }> =
  {
    low: {
      bg: "bg-green-100",
      bar: "bg-green-500",
      text: "text-green-700",
    },
    medium: {
      bg: "bg-yellow-100",
      bar: "bg-yellow-500",
      text: "text-yellow-700",
    },
    high: {
      bg: "bg-orange-100",
      bar: "bg-orange-500",
      text: "text-orange-700",
    },
    critical: {
      bg: "bg-red-100",
      bar: "bg-red-500",
      text: "text-red-700",
    },
  };

interface RiskBreakdownProps {
  workshopSessionId: string;
}

export function RiskBreakdown({ workshopSessionId }: RiskBreakdownProps) {
  const [tierCounts, setTierCounts] = useState<Record<RiskTier, number>>({
    low: 0,
    medium: 0,
    high: 0,
    critical: 0,
  });
  const [connected, setConnected] = useState(false);
  const seenRef = useRef(createIdempotencySet());

  const totalResponses = Object.values(tierCounts).reduce(
    (s, n) => s + n,
    0
  );

  const handleRiskAggregate = useCallback(
    (payload: RiskAggregatePayload) => {
      if (seenRef.current.has(payload.eventId)) return;
      seenRef.current.add(payload.eventId);

      const tier = payload.riskTier as RiskTier;
      if (!TIER_ORDER.includes(tier)) return;

      setTierCounts((prev) => ({
        ...prev,
        [tier]: prev[tier] + 1,
      }));
    },
    []
  );

  useEffect(() => {
    const supabase = createClient();

    const channel = supabase.channel(`workshop:${workshopSessionId}`);

    channel
      .on("broadcast", { event: "risk.aggregate" }, (msg) => {
        const data = msg.payload as RiskAggregatePayload;
        handleRiskAggregate(data);
      })
      .subscribe((status) => {
        setConnected(status === "SUBSCRIBED");
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, [workshopSessionId, handleRiskAggregate]);

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold">Risk Breakdown</h3>
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

      <MinResponseGuard count={totalResponses} label="risk scans">
        <div className="space-y-3">
          {TIER_ORDER.map((tier) => {
            const count = tierCounts[tier];
            const pct =
              totalResponses > 0
                ? Math.round((count / totalResponses) * 100)
                : 0;
            const styles = TIER_STYLES[tier];

            return (
              <div key={tier}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className={`font-medium capitalize ${styles.text}`}>
                    {tier}
                  </span>
                  <span className="text-gray-500 tabular-nums">
                    {pct}% ({count})
                  </span>
                </div>
                <div className={`h-4 w-full rounded ${styles.bg}`}>
                  <div
                    className={`h-4 rounded ${styles.bar} transition-all duration-300`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
          <p className="text-xs text-gray-400 mt-2 text-right">
            {totalResponses} total risk scans
          </p>
        </div>
      </MinResponseGuard>
    </section>
  );
}
