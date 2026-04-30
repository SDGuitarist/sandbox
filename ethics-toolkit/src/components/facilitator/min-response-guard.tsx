"use client";

/**
 * MinResponseGuard
 *
 * Wraps any aggregate facilitator widget and shows a placeholder when
 * fewer than 5 responses have been received (Section 1 Data Privacy rule).
 *
 * Props:
 *  - count: current number of responses for this widget
 *  - label: optional contextual label (e.g. "poll responses")
 *  - children: the real widget, rendered only when count >= 5
 */

const MIN_RESPONSES = 5;

interface MinResponseGuardProps {
  count: number;
  label?: string;
  children: React.ReactNode;
}

export function MinResponseGuard({
  count,
  label,
  children,
}: MinResponseGuardProps) {
  if (count >= MIN_RESPONSES) {
    return <>{children}</>;
  }

  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      <div className="mb-3 text-3xl" aria-hidden="true">
        ...
      </div>
      <p className="text-base font-medium text-gray-500">
        Waiting for more responses
      </p>
      {label && (
        <p className="mt-1 text-sm text-gray-400">
          {count} of {MIN_RESPONSES} {label} needed
        </p>
      )}
    </div>
  );
}
