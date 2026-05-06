import { BudgetInput, BudgetAI } from '@/lib/schemas/budget';
import { MODELS } from '@/lib/ai/client';
import { getMockBudgetAI } from '@/lib/ai/mock';
import { createAiRouteHandler } from '@/lib/ai/route-factory';

export const POST = createAiRouteHandler({
  inputSchema: BudgetInput,
  outputSchema: BudgetAI,
  model: MODELS.SONNET,
  maxTokens: 1024,
  routeLabel: '/api/ai/budget',
  systemPrompt:
    'You are an AI filmmaking ethics budget advisor. ' +
    'Given the role, budget tier, and project scope below, provide a thoughtful ethical analysis ' +
    'of the trade-offs between using AI tools versus hiring human professionals for this role. ' +
    'Consider displacement risk, fair compensation, union standards, creative integrity, ' +
    'and the broader impact on the filmmaking community. ' +
    'Return ONLY a JSON object with a single key "ethicalAnalysis" containing the analysis as a string. ' +
    'The ethicalAnalysis must be between 50 and 2000 characters.',
  buildUserMessage: (input) => JSON.stringify(input),
  getMock: getMockBudgetAI,
});
