'use client';

/**
 * Festival Policy Lookup UI
 *
 * Search bar, filter dropdowns for aiPolicy and category, paginated results table.
 *
 * Spec reference: Section 4 Tool 2
 * No LLM. Fully free. No free/paid boundary. Not stored in ToolEvent.
 * Mobile-first: 16pt body, 44pt tap targets.
 */

import { useState } from 'react';

type AiPolicy = 'banned' | 'restricted' | 'disclosure_required' | 'allowed' | 'no_stated_policy';
type Category = 'writing' | 'music' | 'vfx' | 'voice' | 'full_ban' | 'no_policy';

interface FestivalPolicy {
  id: string;
  festival_name: string;
  year: number;
  ai_policy: AiPolicy;
  policy_details: string;
  source_url: string;
  last_reviewed_date: string;
  confidence_level: string;
  categories: string[];
}

interface SearchResult {
  data: FestivalPolicy[];
  page: number;
  pageSize: number;
  total: number;
  message?: string;
}

const AI_POLICY_OPTIONS: { value: AiPolicy | ''; label: string }[] = [
  { value: '', label: 'All Policies' },
  { value: 'banned', label: 'Banned' },
  { value: 'restricted', label: 'Restricted' },
  { value: 'disclosure_required', label: 'Disclosure Required' },
  { value: 'allowed', label: 'Allowed' },
  { value: 'no_stated_policy', label: 'No Stated Policy' },
];

const CATEGORY_OPTIONS: { value: Category | ''; label: string }[] = [
  { value: '', label: 'All Categories' },
  { value: 'writing', label: 'Writing' },
  { value: 'music', label: 'Music' },
  { value: 'vfx', label: 'VFX' },
  { value: 'voice', label: 'Voice' },
  { value: 'full_ban', label: 'Full Ban' },
  { value: 'no_policy', label: 'No Policy' },
];

const POLICY_BADGES: Record<string, { label: string; className: string }> = {
  banned: { label: 'Banned', className: 'bg-red-100 text-red-800' },
  restricted: { label: 'Restricted', className: 'bg-amber-100 text-amber-800' },
  disclosure_required: {
    label: 'Disclosure Required',
    className: 'bg-blue-100 text-blue-800',
  },
  allowed: { label: 'Allowed', className: 'bg-green-100 text-green-800' },
  no_stated_policy: {
    label: 'No Stated Policy',
    className: 'bg-gray-100 text-gray-800',
  },
};

const CONFIDENCE_BADGES: Record<string, { label: string; className: string }> = {
  verified: { label: 'Verified', className: 'bg-green-100 text-green-700' },
  inferred: { label: 'Inferred', className: 'bg-yellow-100 text-yellow-700' },
  unverified: { label: 'Unverified', className: 'bg-gray-100 text-gray-600' },
};

export default function FestivalPage() {
  const [query, setQuery] = useState('');
  const [aiPolicy, setAiPolicy] = useState('');
  const [category, setCategory] = useState('');
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  async function search(page: number = 1) {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('query', query.trim());
      if (aiPolicy) params.set('aiPolicy', aiPolicy);
      if (category) params.set('category', category);
      params.set('page', String(page));

      const res = await fetch(`/api/tools/festival?${params.toString()}`);
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Search failed');
      }

      const data: SearchResult = await res.json();
      setResult(data);
      setCurrentPage(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    search(1);
  }

  const totalPages = result ? Math.ceil(result.total / result.pageSize) : 0;

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">Festival Policy Lookup</h1>
      <p className="text-sm text-gray-500 mb-6">
        Search festival AI policies before you submit.
      </p>

      {/* Search + Filters */}
      <form onSubmit={handleSubmit} className="space-y-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Search
          </label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
            placeholder="Search by festival name or policy details"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm text-gray-600 mb-1">AI Policy</label>
            <select
              value={aiPolicy}
              onChange={(e) => setAiPolicy(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
            >
              {AI_POLICY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-600 mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base"
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="w-full bg-black text-white rounded-lg py-3 text-base font-medium active:bg-gray-800 disabled:bg-gray-400"
        >
          {loading ? 'Searching...' : 'Search Festivals'}
        </button>
      </form>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg p-3 mb-4">{error}</p>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {result.message && result.data.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-6">{result.message}</p>
          ) : (
            <>
              <p className="text-xs text-gray-400">
                {result.total} result{result.total !== 1 ? 's' : ''} found
              </p>

              {result.data.map((festival) => {
                const policyBadge = POLICY_BADGES[festival.ai_policy];
                const confBadge = CONFIDENCE_BADGES[festival.confidence_level];

                return (
                  <div
                    key={festival.id}
                    className="border border-gray-200 rounded-lg p-4 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-base font-medium">
                        {festival.festival_name}
                      </h3>
                      <span className="text-xs text-gray-400 whitespace-nowrap">
                        {festival.year}
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {policyBadge && (
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full ${policyBadge.className}`}
                        >
                          {policyBadge.label}
                        </span>
                      )}
                      {confBadge && (
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full ${confBadge.className}`}
                        >
                          {confBadge.label}
                        </span>
                      )}
                    </div>

                    <p className="text-sm text-gray-600">{festival.policy_details}</p>

                    {festival.categories.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {festival.categories.map((cat) => (
                          <span
                            key={cat}
                            className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"
                          >
                            {cat}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center justify-between">
                      <a
                        href={festival.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 underline"
                      >
                        Source
                      </a>
                      <span className="text-xs text-gray-400">
                        Reviewed: {festival.last_reviewed_date}
                      </span>
                    </div>
                  </div>
                );
              })}

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-4 py-4">
                  <button
                    onClick={() => search(currentPage - 1)}
                    disabled={currentPage <= 1 || loading}
                    className="px-4 py-2 border border-gray-300 rounded-lg text-sm disabled:opacity-50 active:bg-gray-50"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-gray-500">
                    Page {currentPage} of {totalPages}
                  </span>
                  <button
                    onClick={() => search(currentPage + 1)}
                    disabled={currentPage >= totalPages || loading}
                    className="px-4 py-2 border border-gray-300 rounded-lg text-sm disabled:opacity-50 active:bg-gray-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
