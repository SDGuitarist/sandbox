import { RiskScannerInput, RiskAI } from '@/lib/schemas/risk-scanner';
import { MODELS } from '@/lib/ai/client';
import { getMockRiskAI } from '@/lib/ai/mock';
import { createAiRouteHandler } from '@/lib/ai/route-factory';

export const POST = createAiRouteHandler({
  inputSchema: RiskScannerInput,
  outputSchema: RiskAI,
  model: MODELS.SONNET,
  maxTokens: 2048,
  routeLabel: '/api/ai/risk',
  systemPrompt:
    'You are an AI filmmaking ethics risk advisor. ' +
    'Given the project risk profile below, provide actionable mitigation recommendations. ' +
    'Consider the project type, budget tier, department-level AI usage, distribution targets, ' +
    'and union affiliations. Each recommendation should be specific, practical, and directly ' +
    'address a risk dimension (legal, ethical, reputational, or union compliance). ' +
    'Return ONLY a JSON object with a single key "recommendations" containing an array of strings. ' +
    'Each recommendation must be between 10 and 500 characters. ' +
    'Provide between 1 and 10 recommendations, prioritized by risk severity.',
  buildUserMessage: (input) => JSON.stringify(input),
  getMock: getMockRiskAI,
});
