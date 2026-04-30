"use client";

/**
 * AI Provenance Chain Builder -- attendee tool page.
 *
 * Entry form for: department, task description, attribution, tool used,
 * human contributor, notes.
 *
 * Displays: chain view, summary stats, duplicate warnings.
 *
 * Spec reference: Section 4 Tool 4, Section 1 (Mobile-First UX)
 */

import { useState } from "react";
import { getAnonymousSessionId } from "@/lib/auth/anonymous-session";
import type { ProvenanceOutputType } from "@/lib/schemas/provenance";
import type { DuplicateWarning } from "@/lib/tools/provenance";
import { LEGAL_DISCLAIMER } from "@/lib/constants";

const ATTRIBUTION_OPTIONS = [
  { value: "human_made", label: "Human Made" },
  { value: "ai_assisted", label: "AI Assisted" },
  { value: "ai_generated", label: "AI Generated" },
] as const;

const ATTRIBUTION_COLORS: Record<string, string> = {
  human_made: "bg-green-100 text-green-800",
  ai_assisted: "bg-yellow-100 text-yellow-800",
  ai_generated: "bg-red-100 text-red-800",
};

interface EntryForm {
  department: string;
  taskDescription: string;
  attribution: string;
  toolUsed: string;
  humanContributor: string;
  notes: string;
}

const EMPTY_ENTRY: EntryForm = {
  department: "",
  taskDescription: "",
  attribution: "human_made",
  toolUsed: "",
  humanContributor: "",
  notes: "",
};

export default function ProvenancePage() {
  const [projectTitle, setProjectTitle] = useState("");
  const [entries, setEntries] = useState<EntryForm[]>([{ ...EMPTY_ENTRY }]);

  const [result, setResult] = useState<ProvenanceOutputType | null>(null);
  const [duplicateWarnings, setDuplicateWarnings] = useState<DuplicateWarning[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addEntry() {
    setEntries((prev) => [...prev, { ...EMPTY_ENTRY }]);
  }

  function removeEntry(index: number) {
    setEntries((prev) => prev.filter((_, i) => i !== index));
  }

  function updateEntry(
    index: number,
    field: keyof EntryForm,
    value: string
  ) {
    setEntries((prev) =>
      prev.map((e, i) => (i === index ? { ...e, [field]: value } : e))
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setDuplicateWarnings([]);

    try {
      const anonymousSessionId = getAnonymousSessionId();
      const eventId = crypto.randomUUID();

      const input = {
        projectTitle,
        entries: entries.map((entry) => ({
          department: entry.department,
          taskDescription: entry.taskDescription,
          attribution: entry.attribution,
          ...(entry.toolUsed ? { toolUsed: entry.toolUsed } : {}),
          ...(entry.humanContributor
            ? { humanContributor: entry.humanContributor }
            : {}),
          ...(entry.notes ? { notes: entry.notes } : {}),
        })),
      };

      const response = await fetch("/api/tools/provenance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input, anonymousSessionId, eventId }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.details || data.message || "Failed to build provenance chain");
      }

      const data = await response.json();
      setResult(data.deterministicPayload);
      if (data.duplicateWarnings && data.duplicateWarnings.length > 0) {
        setDuplicateWarnings(data.duplicateWarnings);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">AI Provenance Chain</h1>
      <p className="text-sm text-gray-500 mb-6">
        Document the origin and attribution of every creative element in your
        project.
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Project Title */}
        <div>
          <label className="block text-sm font-medium mb-1">
            Project Title
          </label>
          <input
            type="text"
            value={projectTitle}
            onChange={(e) => setProjectTitle(e.target.value)}
            placeholder="e.g. Midnight Signal"
            maxLength={200}
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
          />
        </div>

        {/* Entries */}
        <div>
          <label className="block text-sm font-medium mb-2">
            Provenance Entries
          </label>
          {entries.map((entry, index) => (
            <div
              key={index}
              className="border border-gray-200 rounded-lg p-3 mb-3 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-600">
                  Entry {index + 1}
                </span>
                {entries.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeEntry(index)}
                    className="text-sm text-red-500 underline"
                  >
                    Remove
                  </button>
                )}
              </div>

              <input
                type="text"
                placeholder="Department (e.g. Music, Editing)"
                value={entry.department}
                onChange={(e) =>
                  updateEntry(index, "department", e.target.value)
                }
                maxLength={100}
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
              />

              <input
                type="text"
                placeholder="Task Description"
                value={entry.taskDescription}
                onChange={(e) =>
                  updateEntry(index, "taskDescription", e.target.value)
                }
                maxLength={500}
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
              />

              <select
                value={entry.attribution}
                onChange={(e) =>
                  updateEntry(index, "attribution", e.target.value)
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
              >
                {ATTRIBUTION_OPTIONS.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>

              <input
                type="text"
                placeholder="Tool Used (optional, e.g. Suno v4)"
                value={entry.toolUsed}
                onChange={(e) =>
                  updateEntry(index, "toolUsed", e.target.value)
                }
                maxLength={200}
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
              />

              <input
                type="text"
                placeholder="Human Contributor (optional)"
                value={entry.humanContributor}
                onChange={(e) =>
                  updateEntry(index, "humanContributor", e.target.value)
                }
                maxLength={200}
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base"
              />

              <textarea
                placeholder="Notes (optional)"
                value={entry.notes}
                onChange={(e) => updateEntry(index, "notes", e.target.value)}
                maxLength={500}
                rows={2}
                className="w-full border border-gray-300 rounded-lg px-3 py-3 text-base resize-none"
              />
            </div>
          ))}
          <button
            type="button"
            onClick={addEntry}
            className="w-full border-2 border-dashed border-gray-300 rounded-lg py-3 text-sm text-gray-500 hover:border-gray-400 hover:text-gray-600"
          >
            + Add Entry
          </button>
        </div>

        {/* Submit */}
        <div className="thumb-zone bg-white border-t border-gray-100">
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black text-white rounded-lg py-4 text-base font-medium disabled:opacity-50"
          >
            {loading ? "Building Chain..." : "Build Provenance Chain"}
          </button>
        </div>
      </form>

      {/* Error */}
      {error && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Duplicate Warnings */}
      {duplicateWarnings.length > 0 && (
        <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-sm font-medium text-amber-800 mb-2">
            Duplicate Entries Detected
          </p>
          {duplicateWarnings.map((warning, i) => (
            <p key={i} className="text-sm text-amber-700">
              &quot;{warning.department} - {warning.taskDescription}&quot; appears{" "}
              {warning.indices.length} times (entries{" "}
              {warning.indices.map((idx) => idx + 1).join(", ")})
            </p>
          ))}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="mt-6 space-y-6">
          {/* Summary Stats */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Summary</h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="border border-gray-200 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold">
                  {result.summary.totalEntries}
                </p>
                <p className="text-xs text-gray-500">Total Entries</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-green-600">
                  {result.summary.percentageHuman}%
                </p>
                <p className="text-xs text-gray-500">Human Made</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-green-600">
                  {result.summary.humanMade}
                </p>
                <p className="text-xs text-gray-500">Human</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-yellow-600">
                  {result.summary.aiAssisted}
                </p>
                <p className="text-xs text-gray-500">AI Assisted</p>
              </div>
              <div className="border border-gray-200 rounded-lg p-3 text-center col-span-2">
                <p className="text-2xl font-bold text-red-600">
                  {result.summary.aiGenerated}
                </p>
                <p className="text-xs text-gray-500">AI Generated</p>
              </div>
            </div>
          </div>

          {/* Chain View */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Provenance Chain</h2>
            <div className="space-y-3">
              {result.entries.map((entry, i) => (
                <div
                  key={i}
                  className="border border-gray-200 rounded-lg p-4"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium">{entry.department}</p>
                      <p className="text-sm text-gray-600">
                        {entry.taskDescription}
                      </p>
                    </div>
                    <span
                      className={`text-xs px-2 py-1 rounded-full font-medium shrink-0 ml-2 ${
                        ATTRIBUTION_COLORS[entry.attribution]
                      }`}
                    >
                      {entry.attribution.replace(/_/g, " ")}
                    </span>
                  </div>
                  {entry.toolUsed && (
                    <p className="text-xs text-gray-400">
                      Tool: {entry.toolUsed}
                    </p>
                  )}
                  {entry.humanContributor && (
                    <p className="text-xs text-gray-400">
                      Human: {entry.humanContributor}
                    </p>
                  )}
                  {entry.notes && (
                    <p className="text-xs text-gray-400 mt-1">
                      {entry.notes}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Generated At */}
          <p className="text-xs text-gray-400 text-center">
            Generated: {new Date(result.generatedAt).toLocaleString()}
          </p>

          {/* Disclaimer */}
          <p className="text-xs text-gray-400 text-center">{LEGAL_DISCLAIMER}</p>
        </div>
      )}
    </div>
  );
}
