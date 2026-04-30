'use client';

/**
 * AI Disclosure Generator UI
 *
 * Form for project title, AI usage areas (with all fields from spec),
 * union status, distribution targets. Shows checklist output + template.
 *
 * Spec reference: Section 4 Tool 1
 * Mobile-first: 16pt body, 44pt tap targets, single-action per screen, bottom thumb zone.
 */

import { useState } from 'react';
import { ensureAnonymousSession } from '@/lib/auth/anonymous-session';

type Department =
  | 'writing'
  | 'music'
  | 'vfx'
  | 'voice'
  | 'storyboard'
  | 'editing'
  | 'sound_design'
  | 'colorist'
  | 'other';

type UsageLevel = 'assistive' | 'generative';
type UnionStatus = 'sag_aftra' | 'wga' | 'iatse' | 'non_union' | 'unknown';

interface AIUsageArea {
  department: Department;
  description: string;
  toolsUsed: string[];
  usageLevel: UsageLevel;
  humanSupervisor: string;
  trainingDataAcknowledged: boolean;
  consentDocumented: boolean;
  compensationNotes: string;
  unionComplianceChecked: boolean;
}

interface ChecklistItem {
  item: string;
  satisfied: boolean;
  requirement: string;
}

interface DisclosureResult {
  deterministic: {
    checklist: ChecklistItem[];
    disclosureFields: {
      projectTitle: string;
      departments: string[];
      toolsUsed: string[];
      unionStatus: string;
      generatedAt: string;
    };
    templateText: string;
  };
  probabilistic: {
    disclosureText: string;
  } | null;
}

const DEPARTMENT_OPTIONS: { value: Department; label: string }[] = [
  { value: 'writing', label: 'Writing' },
  { value: 'music', label: 'Music' },
  { value: 'vfx', label: 'VFX' },
  { value: 'voice', label: 'Voice' },
  { value: 'storyboard', label: 'Storyboard' },
  { value: 'editing', label: 'Editing' },
  { value: 'sound_design', label: 'Sound Design' },
  { value: 'colorist', label: 'Colorist' },
  { value: 'other', label: 'Other' },
];

const UNION_OPTIONS: { value: UnionStatus; label: string }[] = [
  { value: 'sag_aftra', label: 'SAG-AFTRA' },
  { value: 'wga', label: 'WGA' },
  { value: 'iatse', label: 'IATSE' },
  { value: 'non_union', label: 'Non-Union' },
  { value: 'unknown', label: 'Unknown' },
];

function createEmptyArea(): AIUsageArea {
  return {
    department: 'writing',
    description: '',
    toolsUsed: [''],
    usageLevel: 'assistive',
    humanSupervisor: '',
    trainingDataAcknowledged: false,
    consentDocumented: false,
    compensationNotes: '',
    unionComplianceChecked: false,
  };
}

export default function DisclosurePage() {
  const [projectTitle, setProjectTitle] = useState('');
  const [aiUsageAreas, setAiUsageAreas] = useState<AIUsageArea[]>([createEmptyArea()]);
  const [unionStatus, setUnionStatus] = useState<UnionStatus>('non_union');
  const [distributionTargets, setDistributionTargets] = useState('');
  const [result, setResult] = useState<DisclosureResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateArea(index: number, updates: Partial<AIUsageArea>) {
    setAiUsageAreas((prev) =>
      prev.map((area, i) => (i === index ? { ...area, ...updates } : area))
    );
  }

  function addArea() {
    setAiUsageAreas((prev) => [...prev, createEmptyArea()]);
  }

  function removeArea(index: number) {
    if (aiUsageAreas.length <= 1) return;
    setAiUsageAreas((prev) => prev.filter((_, i) => i !== index));
  }

  function updateTool(areaIndex: number, toolIndex: number, value: string) {
    setAiUsageAreas((prev) =>
      prev.map((area, i) => {
        if (i !== areaIndex) return area;
        const newTools = [...area.toolsUsed];
        newTools[toolIndex] = value;
        return { ...area, toolsUsed: newTools };
      })
    );
  }

  function addTool(areaIndex: number) {
    setAiUsageAreas((prev) =>
      prev.map((area, i) => {
        if (i !== areaIndex) return area;
        return { ...area, toolsUsed: [...area.toolsUsed, ''] };
      })
    );
  }

  function removeTool(areaIndex: number, toolIndex: number) {
    setAiUsageAreas((prev) =>
      prev.map((area, i) => {
        if (i !== areaIndex) return area;
        if (area.toolsUsed.length <= 1) return area;
        return { ...area, toolsUsed: area.toolsUsed.filter((_, ti) => ti !== toolIndex) };
      })
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const anonymousSessionId = await ensureAnonymousSession();
      const eventId = crypto.randomUUID();

      // Build the request body
      const targets = distributionTargets
        .split(',')
        .map((t) => t.trim())
        .filter((t) => t.length > 0);

      const body = {
        eventId,
        anonymousSessionId,
        projectTitle,
        aiUsageAreas: aiUsageAreas.map((area) => ({
          ...area,
          toolsUsed: area.toolsUsed.filter((t) => t.trim().length > 0),
          humanSupervisor: area.humanSupervisor || undefined,
          compensationNotes: area.compensationNotes || undefined,
        })),
        unionStatus,
        distributionTargets: targets.length > 0 ? targets : undefined,
      };

      const res = await fetch('/api/tools/disclosure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Failed to generate disclosure');
      }

      const data: DisclosureResult = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">AI Disclosure Generator</h1>
      <p className="text-sm text-gray-500 mb-6">
        Build a transparent AI usage disclosure for your project.
      </p>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Project Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Project Title
            </label>
            <input
              type="text"
              required
              maxLength={200}
              value={projectTitle}
              onChange={(e) => setProjectTitle(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
              placeholder="e.g., Midnight Signal"
            />
          </div>

          {/* AI Usage Areas */}
          {aiUsageAreas.map((area, areaIndex) => (
            <div
              key={areaIndex}
              className="border border-gray-200 rounded-lg p-4 space-y-4"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">
                  AI Usage Area {areaIndex + 1}
                </span>
                {aiUsageAreas.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeArea(areaIndex)}
                    className="text-sm text-red-500"
                  >
                    Remove
                  </button>
                )}
              </div>

              {/* Department */}
              <div>
                <label className="block text-sm text-gray-600 mb-1">Department</label>
                <select
                  value={area.department}
                  onChange={(e) =>
                    updateArea(areaIndex, { department: e.target.value as Department })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
                >
                  {DEPARTMENT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm text-gray-600 mb-1">Description</label>
                <textarea
                  required
                  maxLength={500}
                  value={area.description}
                  onChange={(e) => updateArea(areaIndex, { description: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
                  rows={2}
                  placeholder="How was AI used in this department?"
                />
              </div>

              {/* Tools Used */}
              <div>
                <label className="block text-sm text-gray-600 mb-1">Tools Used</label>
                {area.toolsUsed.map((tool, toolIndex) => (
                  <div key={toolIndex} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      required
                      value={tool}
                      onChange={(e) => updateTool(areaIndex, toolIndex, e.target.value)}
                      className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-base"
                      placeholder="e.g., Suno v4"
                    />
                    {area.toolsUsed.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeTool(areaIndex, toolIndex)}
                        className="text-sm text-red-500 min-w-[44px]"
                      >
                        X
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => addTool(areaIndex)}
                  className="text-sm text-blue-600"
                >
                  + Add tool
                </button>
              </div>

              {/* Usage Level */}
              <div>
                <label className="block text-sm text-gray-600 mb-1">Usage Level</label>
                <select
                  value={area.usageLevel}
                  onChange={(e) =>
                    updateArea(areaIndex, { usageLevel: e.target.value as UsageLevel })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
                >
                  <option value="assistive">Assistive</option>
                  <option value="generative">Generative</option>
                </select>
              </div>

              {/* Human Supervisor */}
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Human Supervisor (optional)
                </label>
                <input
                  type="text"
                  maxLength={200}
                  value={area.humanSupervisor}
                  onChange={(e) => updateArea(areaIndex, { humanSupervisor: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
                  placeholder="Name of person who supervised AI output"
                />
              </div>

              {/* Training Data Acknowledged */}
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={area.trainingDataAcknowledged}
                  onChange={(e) =>
                    updateArea(areaIndex, { trainingDataAcknowledged: e.target.checked })
                  }
                  className="mt-1 w-5 h-5"
                />
                <span className="text-sm text-gray-600">
                  Training data acknowledged (AI models may have been trained on copyrighted material)
                </span>
              </label>

              {/* Consent Documented (shown for voice department) */}
              {area.department === 'voice' && (
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={area.consentDocumented}
                    onChange={(e) =>
                      updateArea(areaIndex, { consentDocumented: e.target.checked })
                    }
                    className="mt-1 w-5 h-5"
                  />
                  <span className="text-sm text-gray-600">
                    Consent documented from all parties for voice/likeness AI
                  </span>
                </label>
              )}

              {/* Compensation Notes (shown for generative usage) */}
              {area.usageLevel === 'generative' && (
                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    Compensation Notes (optional)
                  </label>
                  <textarea
                    maxLength={500}
                    value={area.compensationNotes}
                    onChange={(e) =>
                      updateArea(areaIndex, { compensationNotes: e.target.value })
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
                    rows={2}
                    placeholder="Fair compensation considerations for replaced human roles"
                  />
                </div>
              )}

              {/* Union Compliance Checked */}
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={area.unionComplianceChecked}
                  onChange={(e) =>
                    updateArea(areaIndex, { unionComplianceChecked: e.target.checked })
                  }
                  className="mt-1 w-5 h-5"
                />
                <span className="text-sm text-gray-600">
                  Union compliance checked for this department
                </span>
              </label>
            </div>
          ))}

          <button
            type="button"
            onClick={addArea}
            className="w-full border border-dashed border-gray-300 rounded-lg py-3 text-sm text-gray-600 active:bg-gray-50"
          >
            + Add Another AI Usage Area
          </button>

          {/* Union Status */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Union Status
            </label>
            <select
              value={unionStatus}
              onChange={(e) => setUnionStatus(e.target.value as UnionStatus)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
            >
              {UNION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Distribution Targets */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Distribution Targets (optional)
            </label>
            <input
              type="text"
              value={distributionTargets}
              onChange={(e) => setDistributionTargets(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
              placeholder="e.g., Sundance, SXSW (comma-separated)"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg p-3">{error}</p>
          )}

          {/* Submit -- in thumb zone area */}
          <div className="pb-4">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-black text-white rounded-lg py-3 text-base font-medium active:bg-gray-800 disabled:bg-gray-400"
            >
              {loading ? 'Generating...' : 'Generate Disclosure'}
            </button>
          </div>
        </form>
      ) : (
        <div className="space-y-6">
          {/* Checklist */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Disclosure Checklist</h2>
            <ul className="space-y-2">
              {result.deterministic.checklist.map((item, i) => (
                <li
                  key={i}
                  className={`flex items-start gap-3 p-3 rounded-lg border ${
                    item.satisfied
                      ? 'border-green-200 bg-green-50'
                      : 'border-amber-200 bg-amber-50'
                  }`}
                >
                  <span className="text-lg mt-0.5">
                    {item.satisfied ? '\u2713' : '\u2717'}
                  </span>
                  <div>
                    <p className="text-sm font-medium">{item.item}</p>
                    <p className="text-xs text-gray-500">{item.requirement}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* Template Text */}
          <div>
            <h2 className="text-lg font-semibold mb-3">Disclosure Template</h2>
            <pre className="text-sm bg-gray-50 border border-gray-200 rounded-lg p-4 whitespace-pre-wrap overflow-x-auto">
              {result.deterministic.templateText}
            </pre>
          </div>

          {/* AI-Generated Text (mock in Phase 2) */}
          {result.probabilistic ? (
            <div>
              <h2 className="text-lg font-semibold mb-3">AI-Generated Disclosure</h2>
              <p className="text-sm text-gray-600 bg-blue-50 border border-blue-200 rounded-lg p-4">
                {result.probabilistic.disclosureText}
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">
              AI recommendation temporarily unavailable.
            </p>
          )}

          {/* Start over */}
          <button
            onClick={() => setResult(null)}
            className="w-full border border-gray-300 rounded-lg py-3 text-sm text-gray-600 active:bg-gray-50"
          >
            Generate Another Disclosure
          </button>
        </div>
      )}
    </div>
  );
}
