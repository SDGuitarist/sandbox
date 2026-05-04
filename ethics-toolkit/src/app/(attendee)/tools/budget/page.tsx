"use client";

/**
 * Budget vs. Ethics Calculator UI
 *
 * Role selector, budget tier selector, project scope text,
 * optional current budget input, cost comparison display,
 * displacement risk badge, and delta display (negative = under market rate).
 *
 * Spec reference: Section 4 Tool 5, Section 1 (Mobile-First, Legal Disclaimer)
 */

import { useState } from "react";
import { ensureAnonymousSession } from "@/lib/auth/anonymous-session";
import { LEGAL_DISCLAIMER } from "@/lib/constants";

const ROLES = [
  { value: "composer", label: "Composer" },
  { value: "vfx_artist", label: "VFX Artist" },
  { value: "storyboard_artist", label: "Storyboard Artist" },
  { value: "screenwriter", label: "Screenwriter" },
  { value: "voice_actor", label: "Voice Actor" },
  { value: "editor", label: "Editor" },
  { value: "sound_designer", label: "Sound Designer" },
  { value: "colorist", label: "Colorist" },
] as const;

const BUDGET_TIERS = [
  { value: "student", label: "Student" },
  { value: "indie", label: "Indie" },
  { value: "professional", label: "Professional" },
  { value: "studio", label: "Studio" },
] as const;

interface BudgetResult {
  eventId: string;
  deterministicPayload: {
    roleName: string;
    budgetTier: string;
    humanCostRange: { low: number; high: number };
    unionMinimum: number | null;
    displacementRisk: "high" | "medium" | "low";
    userBudgetDelta: { low: number; high: number } | null;
  };
  probabilisticPayload: {
    ethicalAnalysis: string;
  } | null;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function DisplacementBadge({
  risk,
}: {
  risk: "high" | "medium" | "low";
}) {
  const colors = {
    high: "bg-red-100 text-red-800 border-red-200",
    medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
    low: "bg-green-100 text-green-800 border-green-200",
  };

  return (
    <span
      className={`inline-block px-3 py-1 text-sm font-medium rounded-full border ${colors[risk]}`}
    >
      {risk.charAt(0).toUpperCase() + risk.slice(1)} Displacement Risk
    </span>
  );
}

export default function BudgetCalculatorPage() {
  const [role, setRole] = useState("");
  const [budgetTier, setBudgetTier] = useState("");
  const [projectScope, setProjectScope] = useState("");
  const [currentBudget, setCurrentBudget] = useState("");
  const [result, setResult] = useState<BudgetResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);

    try {
      let anonymousSessionId: string | null = null;
      try {
        anonymousSessionId = await ensureAnonymousSession();
      } catch {
        // Not in browser or no session yet -- proceed without persistence
      }

      const payload: Record<string, unknown> = {
        role,
        budgetTier,
        projectScope,
        eventId: crypto.randomUUID(),
      };

      if (currentBudget !== "") {
        payload.currentBudgetForRole = Number(currentBudget);
      }

      if (anonymousSessionId) {
        payload.anonymousSessionId = anonymousSessionId;
      }

      const res = await fetch("/api/tools/budget", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Something went wrong.");
      }

      const data: BudgetResult = await res.json();
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">Budget vs. Ethics Calculator</h1>
      <p className="text-sm text-gray-500 mb-6">
        Compare your budget against market rates and understand the displacement
        risk of using AI for this role.
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Role Selector */}
        <div>
          <label
            htmlFor="role"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Role
          </label>
          <select
            id="role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
          >
            <option value="" disabled>
              Select a role...
            </option>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        {/* Budget Tier Selector */}
        <div>
          <label
            htmlFor="budgetTier"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Budget Tier
          </label>
          <select
            id="budgetTier"
            value={budgetTier}
            onChange={(e) => setBudgetTier(e.target.value)}
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
          >
            <option value="" disabled>
              Select a tier...
            </option>
            {BUDGET_TIERS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Project Scope */}
        <div>
          <label
            htmlFor="projectScope"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Project Scope
          </label>
          <textarea
            id="projectScope"
            value={projectScope}
            onChange={(e) => setProjectScope(e.target.value)}
            required
            maxLength={500}
            rows={3}
            placeholder="e.g., 10-minute short film score, 3 themes"
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base resize-none"
          />
          <p className="text-xs text-gray-400 mt-1">
            {projectScope.length}/500 characters
          </p>
        </div>

        {/* Current Budget (optional) */}
        <div>
          <label
            htmlFor="currentBudget"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Your Current Budget for This Role (optional)
          </label>
          <input
            id="currentBudget"
            type="number"
            min={0}
            value={currentBudget}
            onChange={(e) => setCurrentBudget(e.target.value)}
            placeholder="e.g., 1500"
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
          />
          <p className="text-xs text-gray-400 mt-1">
            Enter your budget to see how it compares to market rates.
          </p>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={loading || !role || !budgetTier || !projectScope}
          className="w-full bg-gray-900 text-white rounded-lg py-3 px-4 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Calculating..." : "Calculate"}
        </button>
      </form>

      {/* Error */}
      {error && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="mt-6 space-y-4">
          <h2 className="text-xl font-semibold">Results</h2>

          {/* Displacement Risk Badge */}
          <div>
            <DisplacementBadge
              risk={result.deterministicPayload.displacementRisk}
            />
          </div>

          {/* Cost Comparison */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
            <h3 className="font-medium text-gray-900">
              Market Rate for{" "}
              {ROLES.find((r) => r.value === result.deterministicPayload.roleName)
                ?.label ?? result.deterministicPayload.roleName}{" "}
              ({BUDGET_TIERS.find(
                (t) => t.value === result.deterministicPayload.budgetTier
              )?.label ?? result.deterministicPayload.budgetTier}{" "}
              tier)
            </h3>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Low end</span>
              <span className="font-semibold">
                {formatCurrency(result.deterministicPayload.humanCostRange.low)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">High end</span>
              <span className="font-semibold">
                {formatCurrency(result.deterministicPayload.humanCostRange.high)}
              </span>
            </div>
            {result.deterministicPayload.unionMinimum !== null && (
              <div className="flex justify-between items-center border-t border-gray-200 pt-2">
                <span className="text-sm text-gray-600">Union minimum</span>
                <span className="font-semibold">
                  {formatCurrency(result.deterministicPayload.unionMinimum)}
                </span>
              </div>
            )}
          </div>

          {/* Delta Display */}
          {result.deterministicPayload.userBudgetDelta && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
              <h3 className="font-medium text-gray-900">
                Your Budget vs. Market Rate
              </h3>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">
                  vs. high end of market
                </span>
                <span
                  className={`font-semibold ${
                    result.deterministicPayload.userBudgetDelta.low < 0
                      ? "text-red-600"
                      : "text-green-600"
                  }`}
                >
                  {result.deterministicPayload.userBudgetDelta.low < 0
                    ? formatCurrency(
                        result.deterministicPayload.userBudgetDelta.low
                      )
                    : `+${formatCurrency(
                        result.deterministicPayload.userBudgetDelta.low
                      )}`}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">
                  vs. low end of market
                </span>
                <span
                  className={`font-semibold ${
                    result.deterministicPayload.userBudgetDelta.high < 0
                      ? "text-red-600"
                      : "text-green-600"
                  }`}
                >
                  {result.deterministicPayload.userBudgetDelta.high < 0
                    ? formatCurrency(
                        result.deterministicPayload.userBudgetDelta.high
                      )
                    : `+${formatCurrency(
                        result.deterministicPayload.userBudgetDelta.high
                      )}`}
                </span>
              </div>
              {result.deterministicPayload.userBudgetDelta.low < 0 && (
                <p className="text-sm text-red-600 mt-2">
                  Your budget is below market rate. Consider the ethical
                  implications of relying on AI to fill this gap.
                </p>
              )}
            </div>
          )}

          {/* AI Ethical Analysis (mock in Phase 2) */}
          {result.probabilisticPayload ? (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="font-medium text-gray-900 mb-2">
                Ethical Analysis
              </h3>
              <p className="text-sm text-gray-700">
                {result.probabilisticPayload.ethicalAnalysis}
              </p>
            </div>
          ) : (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-sm text-yellow-800">
                AI recommendation temporarily unavailable. Showing deterministic
                comparison only.
              </p>
            </div>
          )}

          {/* Legal Disclaimer */}
          <p className="text-xs text-gray-400 text-center mt-4">
            {LEGAL_DISCLAIMER}
          </p>
        </div>
      )}
    </div>
  );
}
