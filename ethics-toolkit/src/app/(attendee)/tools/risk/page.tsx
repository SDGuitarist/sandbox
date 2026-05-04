"use client";

/**
 * Project Risk Scanner -- attendee tool page.
 *
 * Form for: project type, budget tier, departments (role + aiUsageLevel),
 * distribution type, union affiliation.
 *
 * Displays: tier badge, department flags, dimension breakdown.
 *
 * Spec reference: Section 4 Tool 3, Section 1 (Mobile-First UX)
 */

import { useState } from "react";
import { ensureAnonymousSession } from "@/lib/auth/anonymous-session";
import type { RiskScannerOutputType } from "@/lib/schemas/risk-scanner";
import type { RiskAIType } from "@/lib/schemas/risk-scanner";
import { LEGAL_DISCLAIMER } from "@/lib/constants";

const PROJECT_TYPES = [
  { value: "feature", label: "Feature Film" },
  { value: "short", label: "Short Film" },
  { value: "documentary", label: "Documentary" },
  { value: "commercial", label: "Commercial" },
  { value: "music_video", label: "Music Video" },
  { value: "web_series", label: "Web Series" },
] as const;

const BUDGET_TIERS = [
  { value: "student", label: "Student" },
  { value: "indie", label: "Indie" },
  { value: "professional", label: "Professional" },
  { value: "studio", label: "Studio" },
] as const;

const ROLES = [
  { value: "screenwriter", label: "Screenwriter" },
  { value: "composer", label: "Composer" },
  { value: "vfx_artist", label: "VFX Artist" },
  { value: "voice_actor", label: "Voice Actor" },
  { value: "editor", label: "Editor" },
  { value: "sound_designer", label: "Sound Designer" },
  { value: "colorist", label: "Colorist" },
  { value: "storyboard_artist", label: "Storyboard Artist" },
  { value: "director", label: "Director" },
] as const;

const AI_USAGE_LEVELS = [
  { value: "none", label: "None" },
  { value: "assisted", label: "Assisted" },
  { value: "generated", label: "Generated" },
] as const;

const DISTRIBUTION_TYPES = [
  { value: "none", label: "None" },
  { value: "online", label: "Online" },
  { value: "indie_festival", label: "Indie Festival" },
  { value: "major_festival", label: "Major Festival" },
  { value: "broadcast_theatrical", label: "Broadcast / Theatrical" },
] as const;

const UNION_AFFILIATIONS = [
  { value: "sag_aftra", label: "SAG-AFTRA" },
  { value: "wga", label: "WGA" },
  { value: "iatse", label: "IATSE" },
  { value: "non_union", label: "Non-Union" },
  { value: "mixed", label: "Mixed" },
] as const;

interface DepartmentEntry {
  role: string;
  aiUsageLevel: string;
  description: string;
}

const TIER_COLORS: Record<string, string> = {
  low: "bg-green-100 text-green-800 border-green-300",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
  high: "bg-orange-100 text-orange-800 border-orange-300",
  critical: "bg-red-100 text-red-800 border-red-300",
};

const FLAG_COLORS: Record<string, string> = {
  safe: "bg-green-50 text-green-700",
  caution: "bg-yellow-50 text-yellow-700",
  warning: "bg-orange-50 text-orange-700",
  critical: "bg-red-50 text-red-700",
};

export default function RiskScannerPage() {
  const [projectType, setProjectType] = useState("feature");
  const [budgetTier, setBudgetTier] = useState("indie");
  const [departments, setDepartments] = useState<DepartmentEntry[]>([
    { role: "screenwriter", aiUsageLevel: "none", description: "" },
  ]);
  const [distributionType, setDistributionType] = useState("none");
  const [unionAffiliation, setUnionAffiliation] = useState("non_union");

  const [result, setResult] = useState<RiskScannerOutputType | null>(null);
  const [aiResult, setAiResult] = useState<RiskAIType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addDepartment() {
    setDepartments((prev) => [
      ...prev,
      { role: "screenwriter", aiUsageLevel: "none", description: "" },
    ]);
  }

  function removeDepartment(index: number) {
    setDepartments((prev) => prev.filter((_, i) => i !== index));
  }

  function updateDepartment(
    index: number,
    field: keyof DepartmentEntry,
    value: string
  ) {
    setDepartments((prev) =>
      prev.map((d, i) => (i === index ? { ...d, [field]: value } : d))
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setAiResult(null);

    try {
      const anonymousSessionId = await ensureAnonymousSession();
      const eventId = crypto.randomUUID();

      const input = {
        projectType,
        budgetTier,
        departments: departments.map((d) => ({
          role: d.role,
          aiUsageLevel: d.aiUsageLevel,
          ...(d.description ? { description: d.description } : {}),
        })),
        distributionType,
        unionAffiliation,
      };

      const response = await fetch("/api/tools/risk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input, anonymousSessionId, eventId }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.details || data.message || "Failed to scan risk");
      }

      const data = await response.json();
      setResult(data.deterministicPayload);
      if (data.probabilisticPayload) {
        setAiResult(data.probabilisticPayload);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">Project Risk Scanner</h1>
      <p className="text-sm text-gray-500 mb-6">
        Assess ethical, legal, reputational, and union risks of AI usage in your
        production.
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Project Type */}
        <div>
          <label className="block text-sm font-medium mb-1">Project Type</label>
          <select
            value={projectType}
            onChange={(e) => setProjectType(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
          >
            {PROJECT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Budget Tier */}
        <div>
          <label className="block text-sm font-medium mb-1">Budget Tier</label>
          <select
            value={budgetTier}
            onChange={(e) => setBudgetTier(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
          >
            {BUDGET_TIERS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Departments */}
        <div>
          <label className="block text-sm font-medium mb-2">Departments</label>
          {departments.map((dept, index) => (
            <div
              key={index}
              className="border border-gray-200 rounded-lg p-3 mb-3 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600">
                  Department {index + 1}
                </span>
                {departments.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeDepartment(index)}
                    className="text-sm text-red-500 underline"
                  >
                    Remove
                  </button>
                )}
              </div>

              <select
                value={dept.role}
                onChange={(e) => updateDepartment(index, "role", e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>

              <select
                value={dept.aiUsageLevel}
                onChange={(e) =>
                  updateDepartment(index, "aiUsageLevel", e.target.value)
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
              >
                {AI_USAGE_LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>

              <input
                type="text"
                placeholder="Description (optional)"
                value={dept.description}
                onChange={(e) =>
                  updateDepartment(index, "description", e.target.value)
                }
                maxLength={500}
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
              />
            </div>
          ))}
          <button
            type="button"
            onClick={addDepartment}
            className="w-full border-2 border-dashed border-gray-300 rounded-lg py-3 text-sm text-gray-500 hover:border-gray-400 hover:text-gray-600"
          >
            + Add Department
          </button>
        </div>

        {/* Distribution Type */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Distribution Type
          </label>
          <select
            value={distributionType}
            onChange={(e) => setDistributionType(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
          >
            {DISTRIBUTION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Union Affiliation */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Union Affiliation
          </label>
          <select
            value={unionAffiliation}
            onChange={(e) => setUnionAffiliation(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
          >
            {UNION_AFFILIATIONS.map((u) => (
              <option key={u.value} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </div>

        {/* Submit */}
        <div className="thumb-zone bg-white border-t border-gray-100">
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black text-white rounded-lg py-4 text-base font-medium disabled:opacity-50"
          >
            {loading ? "Scanning..." : "Scan Risk"}
          </button>
        </div>
      </form>

      {/* Error */}
      {error && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="mt-6 space-y-6">
          {/* Tier Badge */}
          <div className="text-center">
            <span
              className={`inline-block px-6 py-3 rounded-full text-lg font-bold border ${
                TIER_COLORS[result.tier]
              }`}
            >
              {result.tier.toUpperCase()} RISK
            </span>
            <p className="mt-2 text-sm text-gray-500">
              Total Score: {result.totalScore} / 10
            </p>
          </div>

          {/* Department Flags */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Department Flags</h2>
            <div className="space-y-2">
              {result.departmentFlags.map((dept, i) => (
                <div
                  key={i}
                  className={`flex items-center justify-between px-4 py-3 rounded-lg ${
                    FLAG_COLORS[dept.flag]
                  }`}
                >
                  <span className="font-medium">
                    {dept.role.replace(/_/g, " ")}
                  </span>
                  <span className="text-sm">
                    {dept.flag.toUpperCase()} ({dept.score.toFixed(1)})
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Dimension Breakdown */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Dimension Breakdown</h2>
            <div className="grid grid-cols-2 gap-3">
              {(
                Object.entries(result.dimensions) as [
                  string,
                  { raw: number; multiplied: number; score: number }
                ][]
              ).map(([name, dim]) => (
                <div
                  key={name}
                  className="border border-gray-200 rounded-lg p-3"
                >
                  <p className="text-sm font-medium capitalize">{name}</p>
                  <p className="text-2xl font-bold">{dim.score}</p>
                  <p className="text-xs text-gray-400">
                    Raw: {dim.raw.toFixed(1)} | Mult: {dim.multiplied.toFixed(1)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* AI Recommendations */}
          {aiResult ? (
            <div>
              <h2 className="text-lg font-semibold mb-3">
                AI Recommendations
              </h2>
              <ul className="space-y-2">
                {aiResult.recommendations.map((rec, i) => (
                  <li
                    key={i}
                    className="flex gap-2 text-sm bg-blue-50 p-3 rounded-lg"
                  >
                    <span className="text-blue-500 font-bold shrink-0">
                      {i + 1}.
                    </span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic">
              AI recommendations temporarily unavailable.
            </p>
          )}

          {/* Disclaimer */}
          <p className="text-xs text-gray-400 text-center">{LEGAL_DISCLAIMER}</p>
        </div>
      )}
    </div>
  );
}
