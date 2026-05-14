---
project: writers-room-council
feature: screenplay-ingestion-layer
date: 2026-05-13
status: ready
swarm: false
feed_forward:
  risk: "Fountain parser edge cases (dual dialogue, forced elements, lyrics) — custom parser may miss spec subtleties"
  verify_first: true
brainstorm: docs/brainstorms/2026-05-13-screenplay-ingestion-layer-brainstorm.md
spec: ~/Downloads/Screenplay_Ingestion_Implementation_Spec (2).md
---

# Plan: Screenplay Ingestion Layer

## What exactly is changing?

Adding a screenplay ingestion layer to the Writers Room Council. This layer sits between file upload and council evaluation. It normalizes 7 input formats to Fountain canonical text, produces structured metadata (parsed_screenplay JSON), scores parse confidence across 3 dimensions, and surfaces limitations to both the writer and the council voices.

New files (~12):
- `src/lib/ingestion/` — parser modules, confidence engine, report generator
- `src/lib/schemas/ingestion.ts` — Zod schemas (re-exported from barrel)
- `src/lib/prompts/ingestion.ts` — prompt-builder context assembly
- `src/app/api/ingestion/ingest/route.ts` — POST endpoint

## What must not change?

- Existing council flow (Phase 0, Seed Council, Standard Council, RWP, Editor, Signature)
- Existing schema barrel exports (only additions, no modifications)
- Existing prompt files (council.ts, seed.ts, phase0.ts, editor.ts, shared-rules.ts)
- Existing API routes
- The writer's submitted script (never rewritten, never cleaned up)

## How will we know it worked?

### Acceptance Tests

#### Happy Path
- WHEN a writer uploads a valid .fdx file THE SYSTEM SHALL return parse_status "success" with support_tier "native_structured" and parse_confidence >= 0.90
- WHEN a writer uploads a valid .fountain file THE SYSTEM SHALL return parse_status "success" with support_tier "native_structured" and raw_text matching the input content
- WHEN a writer uploads a modern Celtx desktop export (.celtx zip+XML) THE SYSTEM SHALL return parse_status "success" with support_tier "native_structured"
- WHEN a writer uploads a text-selectable PDF with screenplay formatting THE SYSTEM SHALL return support_tier "heuristic_structured" and parse_confidence between 0.70 and 0.95
- WHEN a writer uploads a DOCX with screenplay paragraph styles THE SYSTEM SHALL return support_tier "heuristic_structured"
- WHEN a writer pastes text with INT/EXT scene headings THE SYSTEM SHALL detect screenplay structure and return support_tier "heuristic_structured"
- WHEN a writer submits with prose_mode=true THE SYSTEM SHALL return support_tier "plain_text" with parsed_screenplay null and prose_mode true in council_context

#### Error Cases
- WHEN a writer uploads a file with a disallowed extension (.exe, .sh) THE SYSTEM SHALL return 400 with specific error message
- WHEN a writer uploads an old Celtx format THE SYSTEM SHALL return parse_status "failed" with guidance to export to FDX/Fountain/PDF
- WHEN a writer uploads a scanned PDF with no extractable text THE SYSTEM SHALL return parse_status "failed" with guidance to use text-selectable PDF
- WHEN a writer uploads a corrupt file THE SYSTEM SHALL return parse_status "failed" with specific guidance; never a generic error
- WHEN parse_confidence falls below 0.50 THE SYSTEM SHALL set parse_status to "failed" and council shall not run
- WHEN parse_confidence is between 0.50 and 0.89 THE SYSTEM SHALL set parse_status to "partial" with dimensional breakdown in council_context

#### Voice Calibration
- WHEN structural_detection is below 0.85 THE SYSTEM SHALL include a calibration directive for Story Architect to caveat scene boundaries
- WHEN ingestion_warnings is non-empty THE SYSTEM SHALL include a calibration directive for Contrarian to read warnings as candidate question sites
- WHEN prose_mode is true THE SYSTEM SHALL include directives limiting Story Architect and Audience Proxy scope

#### Verification Commands
- `npm test` — all tests pass
- `npx tsc --noEmit` — TypeScript clean
- `curl -X POST http://localhost:3000/api/ingestion/ingest -F "file=@test.fountain"` — returns valid ingestion result

## What is the most likely way this plan is wrong?

The Fountain parser. It's a custom implementation of a text-based spec with many edge cases (forced elements, dual dialogue, centered text, lyrics, notes, synopses, sections). The most likely failure mode is: core syntax works, but edge cases produce incorrect element types or broken scene boundaries, causing structural_detection to be misleadingly high when it should flag ambiguity.

Mitigation: Verify Fountain parser against spec examples first. Flag edge cases in ingestion_warnings rather than silently misclassifying.

---

## Implementation Sections

### Section 1: Zod Schemas (`src/lib/schemas/ingestion.ts`)

All types defined here. No other file defines ingestion types.

```typescript
import { z } from 'zod';

// Enums
export const InputFormat = z.enum(['pdf', 'fdx', 'fountain', 'celtx', 'docx', 'paste', 'prose']);
export type InputFormatType = z.infer<typeof InputFormat>;

export const SupportTier = z.enum(['native_structured', 'heuristic_structured', 'plain_text']);
export type SupportTierType = z.infer<typeof SupportTier>;

export const ParseStatus = z.enum(['success', 'partial', 'failed']);
export type ParseStatusType = z.infer<typeof ParseStatus>;

// Confidence bands (§2 of spec)
export const CONFIDENCE_BANDS = {
  high: { min: 0.90, max: 1.00, label: 'high' as const },
  usable: { min: 0.70, max: 0.89, label: 'usable_with_caveats' as const },
  low: { min: 0.50, max: 0.69, label: 'low' as const },
  failure: { min: 0.00, max: 0.49, label: 'failure' as const },
} as const;

export const FAILURE_FLOOR = 0.50;

// Confidence dimensions (§5)
export const ConfidenceDimensions = z.object({
  structural_detection: z.number().min(0).max(1).nullable(),
  content_fidelity: z.number().min(0).max(1),
  metadata_completeness: z.number().min(0).max(1).nullable(),
});
export type ConfidenceDimensionsType = z.infer<typeof ConfidenceDimensions>;

// Scene element (§4)
export const SceneElement = z.object({
  type: z.enum(['action', 'dialogue', 'character', 'parenthetical', 'transition', 'dual_dialogue']),
  content: z.string(),
  character: z.string().optional(),
});

export const Scene = z.object({
  heading: z.string(),
  scene_number: z.string().nullable(),
  elements: z.array(SceneElement),
});

export const ParsedScreenplay = z.object({
  scenes: z.array(Scene),
  characters: z.array(z.string()),
  title_page: z.record(z.string()).nullable(),
});
export type ParsedScreenplayType = z.infer<typeof ParsedScreenplay>;

// Full parse result (internal)
export const ParseResult = z.object({
  input_format: InputFormat,
  support_tier: SupportTier,
  source_format_version: z.string().nullable(),
  raw_text: z.string(),
  parsed_screenplay: ParsedScreenplay.nullable(),
  parse_status: ParseStatus,
  parse_confidence: z.number().min(0).max(1),
  parse_confidence_dimensions: ConfidenceDimensions,
  ingestion_warnings: z.array(z.string()),
});
export type ParseResultType = z.infer<typeof ParseResult>;

// Council context (§6.2 — exact shape)
export const CouncilContext = z.object({
  input_format: InputFormat,
  support_tier: SupportTier,
  parse_status: ParseStatus,
  parse_confidence: z.number(),
  parse_confidence_dimensions: ConfidenceDimensions,
  scene_count: z.number(),
  character_list: z.array(z.string()),
  ingestion_warnings: z.array(z.string()),
  limitations_summary: z.string(),
  prose_mode: z.boolean(),
});
export type CouncilContextType = z.infer<typeof CouncilContext>;

// Full ingestion result (API response)
export const IngestionResult = ParseResult.extend({
  writer_report: z.string(),
  council_context: CouncilContext,
});
export type IngestionResultType = z.infer<typeof IngestionResult>;

// API request validation
export const IngestionRequest = z.object({
  format: InputFormat.optional(),
  prose_mode: z.boolean().optional().default(false),
});
```

**Barrel export:** Add to `src/lib/schemas/index.ts`:
```typescript
export {
  InputFormat, SupportTier, ParseStatus, ConfidenceDimensions,
  SceneElement, Scene, ParsedScreenplay, ParseResult,
  CouncilContext, IngestionResult, IngestionRequest,
  CONFIDENCE_BANDS, FAILURE_FLOOR,
} from './ingestion';
export type {
  InputFormatType, SupportTierType, ParseStatusType,
  ConfidenceDimensionsType, ParsedScreenplayType, ParseResultType,
  CouncilContextType, IngestionResultType,
} from './ingestion';
```

### Section 2: Parser Interface + Dispatch (`src/lib/ingestion/index.ts`)

```typescript
import type { ParseResultType, InputFormatType } from '../schemas/ingestion';

export interface FormatParser {
  parse(content: Buffer | string): Promise<ParseResultType>;
}

// Allowed file extensions
const ALLOWED_EXTENSIONS = new Set(['.fdx', '.fountain', '.celtx', '.pdf', '.docx']);
const BLOCKED_EXTENSIONS = new Set(['.exe', '.sh', '.bat', '.cmd', '.php', '.js', '.py', '.rb']);

export function detectFormat(
  filename: string | null,
  text: string | null,
  explicitFormat: InputFormatType | undefined,
  proseMode: boolean
): InputFormatType { ... }

export async function ingest(
  file: File | null,
  text: string | null,
  options: { format?: InputFormatType; prose_mode?: boolean }
): Promise<IngestionResultType> { ... }
```

Format detection order:
1. `prose_mode: true` → 'prose'
2. Explicit `format` → use it
3. File extension → map to format
4. Text without file → 'paste' (inspect for structure)
5. Unknown → return failed with guidance

### Section 3: Fountain Parser (`src/lib/ingestion/parsers/fountain.ts`)

Native-structured. Pass-through parse following fountain.io/syntax.

Key behaviors:
- Title page: key-value pairs before first blank line
- Scene headings: lines starting with INT, EXT, EST, INT./EXT, I/E (case-insensitive), or forced with `.`
- Character cues: ALL CAPS line preceded by empty line
- Dialogue: lines following character cue
- Parentheticals: `(text)` within dialogue blocks
- Action: everything else
- Transitions: lines ending with `TO:` or forced with `>`
- Notes: `[[...]]` → ingestion_warnings, not parsed_screenplay
- Dual dialogue: `^` after second character cue
- Sections/synopses: captured as metadata, not as screenplay elements

Confidence: structural_detection 0.95+ (native format), content_fidelity 1.0 (text passthrough), metadata_completeness depends on title page presence.

### Section 4: FDX Parser (`src/lib/ingestion/parsers/fdx.ts`)

Native-structured. XML parsing via `fast-xml-parser`.

Key behaviors:
- Check `<FinalDraft DocumentType="Script">` root element
- Extract `Version` attribute for `source_format_version`
- Map FDX paragraph types to SceneElement types:
  - `Scene Heading` → scene heading
  - `Character` → character cue
  - `Dialogue` → dialogue
  - `Parenthetical` → parenthetical
  - `Action` → action
  - `Transition` → transition
  - `(More)` / `(CONT'D)` → skip (presentation markers)
- Extract dual dialogue from `<DualDialogue>` containers
- Build Fountain canonical raw_text from parsed elements
- If schema version unrecognized: attempt parse, downgrade to heuristic_structured if structural_detection < 0.85

### Section 5: Celtx Parser (`src/lib/ingestion/parsers/celtx.ts`)

Native-structured. ZIP extraction via `jszip` + XML parsing via `fast-xml-parser`.

Key behaviors:
- Open .celtx as ZIP
- Find script XML inside (typically `script-N.html` or similar)
- Parse internal structure (similar element mapping to FDX)
- If ZIP extraction fails or expected structure not found → return failed with guidance:
  "The submitted .celtx file is in an older Celtx format not supported in v1. Open the file in Celtx and export to PDF, FDX, or Fountain, then resubmit."

### Section 6: PDF Parser (`src/lib/ingestion/parsers/pdf.ts`)

Heuristic-structured or plain-text. Text extraction via `pdf-parse`.

Key behaviors:
- Extract text from PDF
- If no text extracted → return failed with OCR guidance
- Detect screenplay layout:
  - Scene headings: INT/EXT pattern, capitalized
  - Character cues: centered, ALL CAPS
  - Dialogue: indented under character cues
  - Action: left-aligned, sentence case
- If screenplay layout detected → heuristic_structured, build parsed_screenplay
- If not detected → plain_text, raw_text only
- Content fidelity: check for replacement characters, encoding issues

### Section 7: DOCX Parser (`src/lib/ingestion/parsers/docx.ts`)

Heuristic-structured or plain-text. Text extraction via `mammoth`.

Key behaviors:
- Extract text with paragraph style information
- Check for screenplay-style paragraph names (common templates use "Scene Heading", "Character", "Dialogue", etc.)
- If screenplay styles found → heuristic_structured, map styles to elements
- If not found → plain_text, raw text only
- Do not infer structure from generic formatting (bold, centered, etc.)

### Section 8: Paste + Prose Parsers (`src/lib/ingestion/parsers/paste.ts`, `prose.ts`)

**Paste:** Inspect pasted text for screenplay syntax patterns:
- Fountain-style markers (INT., EXT., character cues)
- FDX-extracted plain text patterns
- If structure detected → heuristic_structured
- If not → plain_text

**Prose:** Skip all structural parsing. Return plain_text tier with raw_text only. Set structural_detection and metadata_completeness to null.

### Section 9: Confidence Scoring (`src/lib/ingestion/confidence.ts`)

```typescript
export function computeConfidence(dimensions: ConfidenceDimensionsType): {
  aggregate: number;
  band: 'high' | 'usable_with_caveats' | 'low' | 'failure';
  status: ParseStatusType;
} { ... }
```

- Aggregate = mean of non-null dimensions
- Band assignment per §2 table
- Status: aggregate >= 0.90 → 'success', >= 0.50 → 'partial', < 0.50 → 'failed'

### Section 10: Report Generator (`src/lib/ingestion/report.ts`)

Two outputs from same parse result:

**Writer report** (`generateWriterReport`): Single actionable string following §6.1 examples:
- Names format, tier, confidence, scene count, warnings
- Failed parses: names specific issue + specific corrective action (§8.4)
- No generic "something went wrong"

**Council context** (`generateCouncilContext`): JSON matching §6.2 shape exactly. Validated through `CouncilContext` Zod schema before returning.

**Limitations summary** (`generateLimitationsSummary`): Human-readable string summarizing parse quality for the council voices.

### Section 11: Prompt-Builder Integration (`src/lib/prompts/ingestion.ts`)

```typescript
export function buildIngestionHeader(
  councilContext: CouncilContextType,
  rawText: string
): string { ... }

export function getStoryArchitectDirective(
  councilContext: CouncilContextType
): string | null { ... }

export function getContrarianDirective(
  councilContext: CouncilContextType
): string | null { ... }

export function getProseModeDirectives(
  councilContext: CouncilContextType
): Record<string, string> | null { ... }
```

Header block ordering per §7.1 (items 6-7 — ingestion context + canonical script text). Items 1-5 (Phase 0 declarations) already handled by existing prompt system.

XML sandboxing: raw_text wrapped in `<screenplay_text>` tags. Ingestion warnings wrapped in `<ingestion_context>` tags. Injection defense text references all tag names.

Voice calibration per §7.3:
- Story Architect: if structural_detection < 0.85, directive to caveat scene boundaries
- Contrarian: directive to read ingestion_warnings as candidate question sites
- Prose mode: Story Architect limited to thematic/macro-structural, Audience Proxy limited to prose pacing

### Section 12: API Route (`src/app/api/ingestion/ingest/route.ts`)

```typescript
export async function POST(request: NextRequest): Promise<NextResponse> { ... }
```

Guard chain:
1. Auth check (existing middleware)
2. Content-Type validation (must be multipart/form-data or application/json for text)
3. File extension validation (ALLOWED_EXTENSIONS, reject BLOCKED_EXTENSIONS)
4. Filename sanitization (NFKC normalization)
5. File size check (10MB limit)
6. Format detection
7. Parse via format-specific parser
8. Confidence scoring
9. Report generation (writer + council)
10. Zod validation of full IngestionResult before response

Error responses always include specific guidance. Never return generic 500.

---

## NPM Dependencies to Add

| Package | Purpose | Size |
|---------|---------|------|
| `fast-xml-parser` | FDX + Celtx XML parsing | ~60KB |
| `jszip` | Celtx ZIP extraction | ~95KB |
| `pdf-parse` | PDF text extraction | ~20KB (wraps pdfjs-dist) |
| `mammoth` | DOCX text + style extraction | ~150KB |

Total addition: ~325KB. All are well-maintained, widely used packages.

---

## Implementation Order

1. Schemas (Section 1) + barrel export — foundation for everything
2. Fountain parser (Section 3) — simplest native parser, test the interface
3. Confidence scoring (Section 9) — needed by all parsers
4. Report generator (Section 10) — needed by API route
5. FDX parser (Section 4) — install fast-xml-parser
6. Celtx parser (Section 5) — uses same XML parser + jszip
7. PDF parser (Section 6) — install pdf-parse
8. DOCX parser (Section 7) — install mammoth
9. Paste + Prose parsers (Section 8)
10. Dispatch entry point (Section 2) — wires all parsers together
11. Prompt-builder integration (Section 11)
12. API route (Section 12) — final wiring

Each section committed independently (~50-100 lines per commit).

---

## Supabase Persistence Decision

**Decision: No Supabase persistence for v1.**

Ingestion results are computed on-the-fly and passed to the prompt-builder in the same request cycle. The council API routes (`/api/council/standard`, `/api/council/seed`) already accept script text as input. The ingestion layer preprocesses that input before it reaches the council.

This eliminates the ID round-trip risk from the brainstorm refinement (Gap 4). Ingestion is a pure function: file in → result out → passed to council.

If persistence is needed later (for returning writer protocol, draft history), it can be added as a separate feature with explicit ID management.

---

## Cross-Section Verification (Convergence Loop)

Per brainstorm refinement Gap 3, verifying that the external spec's sections are internally consistent:

| §2 Field | §4 Parser Output | §5 Confidence | §6.2 Context | Status |
|----------|-----------------|---------------|--------------|--------|
| input_format | Each parser sets | — | Included | Consistent |
| support_tier | Each parser sets | — | Included | Consistent |
| raw_text | All parsers produce Fountain | — | Not in context (separate) | Consistent — context + raw_text are separate inputs to prompt-builder |
| parsed_screenplay | Native + heuristic produce, plain returns null | — | Not in context (accessed separately) | Consistent |
| parse_confidence | — | §5.4 aggregate | Included | Consistent |
| parse_confidence_dimensions | — | §5.1-5.3 three dimensions | Included | Consistent |
| scene_count | Derived from parsed_screenplay.scenes.length | — | Included | **New field** — not in ParseResult, computed in report.ts |
| character_list | Derived from parsed_screenplay.characters | — | Included | **New field** — derived in report.ts |
| limitations_summary | — | — | Included | **New field** — generated in report.ts |
| prose_mode | Derived from support_tier === 'plain_text' | — | Included | **New field** — derived in report.ts |

All fields accounted for. No cross-section contradictions found. The 4 "new fields" in council_context (scene_count, character_list, limitations_summary, prose_mode) are derived from ParseResult fields, not independently defined.

---

## Feed-Forward

- **Hardest decision:** No Supabase persistence for v1. The ingestion layer is a pure function, which dramatically simplifies the architecture. But this means no ingestion history, no draft comparison at the ingestion layer. If the Returning Writer Protocol needs ingestion history, it'll be added as a separate feature.
- **Rejected alternatives:** Swarm build (7 agents for 7 parsers) — rejected due to tight coupling between parsers and shared confidence/report infrastructure. Also rejected: using an existing Fountain npm package — `fountain-js` is unmaintained and doesn't handle the full spec. Custom parser gives us control over edge-case handling.
- **Least confident:** Fountain parser edge cases (dual dialogue, forced elements, lyrics, centered text). This is where the brainstorm flagged risk and it remains the highest-risk section. Plan mitigation: implement core syntax first, test against known Fountain examples, flag unhandled edge cases in ingestion_warnings.
