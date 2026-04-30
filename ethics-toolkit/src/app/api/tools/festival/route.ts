/**
 * GET /api/tools/festival
 *
 * Query festival_policies from Supabase with search and filters.
 * Case-insensitive substring match on festival_name and policy_details.
 * Filter by ai_policy and category. Paginated at 20 per page.
 *
 * Spec reference: Section 4 Tool 2
 *
 * No LLM. Fully free. Not stored in ToolEvent. Read-only, stateless.
 */

import { NextRequest, NextResponse } from 'next/server';
import { PolicyLookupInput } from '@/lib/schemas/policy-lookup';
import { lookupFestivalPolicies } from '@/lib/tools/festival-lookup';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;

  const query = searchParams.get('query') || '';
  const aiPolicy = searchParams.get('aiPolicy') || undefined;
  const category = searchParams.get('category') || undefined;
  const page = parseInt(searchParams.get('page') || '1', 10);

  // Validate input with Zod
  const parsed = PolicyLookupInput.safeParse({
    query: query || undefined,
    filters: aiPolicy || category ? { aiPolicy, category } : undefined,
  });

  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Validation failed', details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  try {
    const result = await lookupFestivalPolicies({
      query: parsed.data.query,
      filters: parsed.data.filters,
      page: isNaN(page) || page < 1 ? 1 : page,
    });

    // Handle empty states per spec
    if (result.total === 0 && query) {
      return NextResponse.json({
        ...result,
        message: 'No matching festivals found.',
      });
    }

    if (result.total === 0 && !query) {
      return NextResponse.json({
        ...result,
        message: 'Festival data is loading.',
      });
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('Festival lookup error:', error);
    return NextResponse.json(
      { error: 'Festival lookup failed' },
      { status: 500 }
    );
  }
}
