/**
 * Input validation test for Festival Policy Lookup (Tool 2).
 *
 * Spec reference: Section 4 Tool 2
 */

import { describe, it, expect } from 'vitest';
import { PolicyLookupInput } from '../../src/lib/schemas/policy-lookup';

describe('PolicyLookupInput schema', () => {
  it('validates a simple query', () => {
    const input = { query: 'Sundance' };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('validates query with aiPolicy filter', () => {
    const input = {
      query: 'festival',
      filters: { aiPolicy: 'banned' },
    };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('validates query with category filter', () => {
    const input = {
      query: 'festival',
      filters: { category: 'music' },
    };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('validates query with both filters', () => {
    const input = {
      query: 'festival',
      filters: { aiPolicy: 'disclosure_required', category: 'vfx' },
    };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('validates query with empty filters object', () => {
    const input = {
      query: 'festival',
      filters: {},
    };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('validates query without filters (optional)', () => {
    const input = { query: 'Cannes' };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(true);
  });

  it('rejects empty query', () => {
    const input = { query: '' };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects query over 500 characters', () => {
    const input = { query: 'A'.repeat(501) };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects invalid aiPolicy filter value', () => {
    const input = {
      query: 'festival',
      filters: { aiPolicy: 'invalid_policy' },
    };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('rejects invalid category filter value', () => {
    const input = {
      query: 'festival',
      filters: { category: 'invalid_category' },
    };
    const result = PolicyLookupInput.safeParse(input);
    expect(result.success).toBe(false);
  });

  it('accepts all valid aiPolicy values', () => {
    const policies = ['banned', 'restricted', 'disclosure_required', 'allowed', 'no_stated_policy'];
    for (const policy of policies) {
      const input = { query: 'test', filters: { aiPolicy: policy } };
      const result = PolicyLookupInput.safeParse(input);
      expect(result.success).toBe(true);
    }
  });

  it('accepts all valid category values', () => {
    const categories = ['writing', 'music', 'vfx', 'voice', 'full_ban', 'no_policy'];
    for (const category of categories) {
      const input = { query: 'test', filters: { category } };
      const result = PolicyLookupInput.safeParse(input);
      expect(result.success).toBe(true);
    }
  });
});
