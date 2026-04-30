/**
 * Festival Policy Lookup -- search + filter logic.
 *
 * Spec reference: Section 4 Tool 2
 *
 * Search: Case-insensitive substring match on festival_name and policy_details.
 * Filter by ai_policy and categories (array contains).
 * Paginated, 20 per page.
 *
 * No LLM. Fully free. No free/paid boundary. Not stored in ToolEvent.
 */

import { createServiceClient } from '@/lib/supabase/server';
import type { FestivalPolicy } from '@/types/database';

const PAGE_SIZE = 20;

interface FestivalLookupParams {
  query: string;
  filters?: {
    aiPolicy?: string;
    category?: string;
  };
  page?: number;
}

interface FestivalLookupResult {
  data: FestivalPolicy[];
  page: number;
  pageSize: number;
  total: number;
}

/**
 * Search festival policies with case-insensitive substring matching
 * on festival_name and policy_details. Supports optional filters for
 * ai_policy and category (array contains). Results are paginated at 20/page.
 */
export async function lookupFestivalPolicies(
  params: FestivalLookupParams
): Promise<FestivalLookupResult> {
  const supabase = createServiceClient();
  const page = params.page ?? 1;
  const offset = (page - 1) * PAGE_SIZE;

  // Build query -- case-insensitive substring match on festival_name and policy_details.
  // Supabase ilike supports case-insensitive pattern matching.
  const searchPattern = `%${params.query}%`;

  let query = supabase
    .from('festival_policies')
    .select('*', { count: 'exact' })
    .or(`festival_name.ilike.${searchPattern},policy_details.ilike.${searchPattern}`);

  // Apply ai_policy filter if provided
  if (params.filters?.aiPolicy) {
    query = query.eq('ai_policy', params.filters.aiPolicy);
  }

  // Apply category filter if provided (array contains)
  if (params.filters?.category) {
    query = query.contains('categories', [params.filters.category]);
  }

  // Apply pagination
  query = query
    .order('festival_name', { ascending: true })
    .range(offset, offset + PAGE_SIZE - 1);

  const { data, count, error } = await query;

  if (error) {
    throw new Error(`Festival lookup failed: ${error.message}`);
  }

  return {
    data: (data as FestivalPolicy[]) || [],
    page,
    pageSize: PAGE_SIZE,
    total: count ?? 0,
  };
}
