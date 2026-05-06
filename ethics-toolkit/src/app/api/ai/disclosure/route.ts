import { DisclosureInput, DisclosureAI } from '@/lib/schemas/disclosure';
import { MODELS } from '@/lib/ai/client';
import { getMockDisclosureAI } from '@/lib/ai/mock';
import { createAiRouteHandler } from '@/lib/ai/route-factory';

export const POST = createAiRouteHandler({
  inputSchema: DisclosureInput,
  outputSchema: DisclosureAI,
  model: MODELS.HAIKU,
  maxTokens: 1024,
  routeLabel: '/api/ai/disclosure',
  systemPrompt:
    'You are an AI filmmaking ethics disclosure writer. ' +
    'Given the project details below, write a clear, professional disclosure statement ' +
    'that a filmmaker can include with their festival submission or distribution materials. ' +
    'The statement should cover: which departments used AI, what tools were used, ' +
    'whether usage was assistive or generative, human oversight details, and any ' +
    'relevant consent or compensation notes. Keep the tone transparent and constructive. ' +
    'Return ONLY a JSON object with a single key "disclosureText" containing the statement as a string. ' +
    'The disclosureText must be between 50 and 2000 characters.',
  buildUserMessage: (input) => JSON.stringify(input),
  getMock: getMockDisclosureAI,
});
