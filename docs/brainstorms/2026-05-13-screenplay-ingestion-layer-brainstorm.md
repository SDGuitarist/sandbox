---
project: writers-room-council
feature: screenplay-ingestion-layer
date: 2026-05-13
status: complete
spec: ~/Downloads/Screenplay_Ingestion_Implementation_Spec (2).md
handoff: ~/Downloads/Claude_Code_Handoff_Screenplay_Ingestion_Build.md
---

# Brainstorm: Screenplay Ingestion Layer

## App Brief

**Name:** Writers Room Council — Screenplay Ingestion Layer
**Target user:** Single writer (existing WRC app user submitting scripts for council review)
**Tech stack:** Next.js 15 + TypeScript + Supabase + Vitest (existing project, no stack changes)
**Core features:**
1. 7-format parser with tier routing (FDX, Fountain, .celtx, PDF, DOCX, paste-as-text, prose)
2. 3-dimensional confidence scoring (structural detection, content fidelity, metadata completeness)
3. Writer-facing report (single actionable string per §6.1)
4. Council-facing context JSON matching §6.2 shape exactly
5. Prompt-builder integration with §7 header block ordering + voice calibration directives

**Explicitly out of scope for MVP:**
- Highland, Trelby, Movie Magic Screenwriter native formats
- Multi-script ingestion per Phase 0 cycle
- Streaming ingestion, resumable parses
- Prose-to-screenplay conversion (permanently out of scope — violates never-rewrite)
- Style cleanup, auto-reformatting, convention enforcement (permanently out of scope)
- Draft comparison at ingestion layer
- Celtx web, cloud, and legacy desktop formats

## Roadmap

**Phase 1 (MVP — this build):**
- Format detection and tier routing for 7 formats
- Parser modules for FDX, Fountain, Celtx (modern desktop), PDF, DOCX, paste-as-text, prose
- Confidence scoring engine (3 dimensions + aggregate with tier-aware bands)
- Writer report generation and council context JSON assembly
- Prompt-builder integration with header block ordering and voice calibration

**Phase 2 (post-workshop, based on demand):**
- QA test matrix across reference library (1-2 scripts per format + borderline cases)
- Celtx web/cloud export support
- Additional native format support

**Phase 3 (if needed):**
- OCR for scanned PDFs (tesseract.js or external service)
- Multi-script ingestion per session
- Streaming ingestion for very large files

## Lessons Applied from Prior Builds

1. **Schema barrel for contracts** — All ingestion Zod schemas exported from `src/lib/schemas/index.ts`. Prevents naming divergence (FC1) and type drift (FC2). (from: WRC swarm build)
2. **Sanitize at parser output boundary** — Each format parser validates output through Zod before returning. No `as ParseResult` casts. (from: defensive-yaml-frontmatter-parsing, producer-brief-mvp-patterns)
3. **Three-way confidence gate** — Confidence tiers defined as a constant (`CONFIDENCE_BANDS`) imported everywhere. Prevents label drift across modules. (from: skeptic-enforcement-quality-gates)
4. **Score caps applied immediately before return** — Aggregate scoring covers all exit paths including error fallbacks. (from: relevance-source-quality-gates)
5. **Guard at API boundary** — Format validation → file size check → parse → confidence check → report. (from: express-handler-boundary-validation)
6. **Domain-agnostic internal language** — Parser internals use generic terms; domain language only in writer-facing output. (from: domain-agnostic-pipeline-design)
7. **Output fidelity for workshop demo** — Never invent structure, never pad confidence. Transparency is the product. (from: WRC live validation)
8. **Zod at every boundary** — Parser result, confidence dimensions, council context, writer report — all Zod-validated before leaving their module. (from: producer-brief-mvp-patterns)

---

## Key Design Decisions

### 1. Parser Architecture

**Decision:** Common `FormatParser` interface with 7 implementations. Single `ingest()` entry point dispatches to the correct parser based on format detection.

```typescript
interface ParseResult {
  input_format: InputFormat;
  support_tier: SupportTier;
  source_format_version: string | null;
  raw_text: string;          // Fountain canonical
  parsed_screenplay: ParsedScreenplay | null;
  parse_status: ParseStatus;
  parse_confidence: number;
  parse_confidence_dimensions: ConfidenceDimensions;
  ingestion_warnings: string[];
}
```

Each parser returns this shape. The orchestrator adds `writer_report` and `council_context` on top.

**Why not one big function?** Seven formats with different parsing strategies would create an unmaintainable switch statement. Separate modules let each parser be tested independently.

### 2. Library Choices

| Format | Library | Rationale |
|--------|---------|-----------|
| FDX | `fast-xml-parser` | Lightweight XML parsing, no DOM dependency, good for server-side |
| Fountain | Custom parser | Fountain spec is simple enough to implement directly; no well-maintained npm package |
| Celtx | `jszip` + `fast-xml-parser` | ZIP extraction + XML parsing for the internal structure |
| PDF | `pdf-parse` (wraps `pdfjs-dist`) | Widely used, extracts text from text-selectable PDFs |
| DOCX | `mammoth` | Extracts text + preserves paragraph style names for screenplay detection |
| Paste/Prose | No library | Text processing only |

**OCR decision for v1:** Scanned PDFs without text layers return `failed` with guidance to use a text-selectable PDF. Tesseract.js is too heavy for a serverless function (>10MB, slow). Defer to v2 if workshop feedback demands it.

### 3. Parsed Screenplay JSON Shape

```typescript
interface ParsedScreenplay {
  scenes: Scene[];
  characters: string[];
  title_page: Record<string, string> | null;
}

interface Scene {
  heading: string;
  scene_number: string | null;
  elements: SceneElement[];
}

interface SceneElement {
  type: 'action' | 'dialogue' | 'character' | 'parenthetical' | 'transition' | 'dual_dialogue';
  content: string;
  character?: string;  // populated for dialogue and parenthetical types
}
```

This covers the element set from §4: scene headings, character cues, dialogue, parentheticals, action, transitions, dual dialogue. Scene numbers captured when present. Title page as key-value pairs (title, author, contact, etc.).

### 4. Confidence Scoring

Three dimensions, each 0.0–1.0. Each parser computes its own scores.

**Structural detection:** Ratio of cleanly identified elements to total content blocks. For native-structured, this should be 0.95+. For heuristic, 0.70–0.85 is normal.

**Content fidelity:** Checks for encoding issues (replacement characters), dropped lines, line-break fidelity. PDF gets OCR confidence factored in (when applicable). Always scored.

**Metadata completeness:** Title page present? Scene numbers captured? Forced line breaks preserved? Returns null for plain-text tier.

**Aggregate:** Mean of non-null dimensions. Bands per §2:
- 0.90–1.00: high (no caveats)
- 0.70–0.89: usable with caveats
- 0.50–0.69: low (explicit warnings)
- Below 0.50: failed (council does not run)

### 5. API Route Design

Single endpoint: `POST /api/ingestion/ingest`

Request: `multipart/form-data` with:
- `file`: uploaded file (for FDX, Fountain, Celtx, PDF, DOCX)
- `text`: pasted text (for paste-as-text mode)
- `format`: explicit format declaration (optional — overrides detection)
- `prose_mode`: boolean (explicit prose declaration)

Response: Full ingestion result including `writer_report` and `council_context`.

Format detection order:
1. Explicit `format` field → use declared format
2. File extension mapping (.fdx → FDX, .fountain → Fountain, .celtx → Celtx, .pdf → PDF, .docx → DOCX)
3. Text input without file → paste-as-text (inspect for structure)
4. `prose_mode: true` → prose (skip structural parsing)

### 6. Prompt-Builder Integration

Extend existing prompt system at `src/lib/prompts/` with an `ingestion.ts` module.

Header block ordering per §7.1:
1. Structural-spine declaration
2. Genre declaration
3. Modifier declarations
4. Constraint declarations
5. Writer's creative fingerprint
6. Ingestion context (§6.2 JSON)
7. Canonical script text (raw_text)

Voice calibration directives per §7.3:
- Story Architect: if `structural_detection < 0.85`, preface pass with scene-boundary reliability caveat
- Contrarian: read `ingestion_warnings` as candidate question sites
- Other voices: receive context without specific directives

Prose mode per §7.4:
- Story Architect: thematic/macro-structural only
- Audience Proxy: prose pacing only
- Others: unchanged

### 7. File Structure

```
src/lib/ingestion/
  index.ts              # ingest() entry point, format detection, dispatch
  types.ts              # TypeScript interfaces (not Zod — raw types)
  parsers/
    fountain.ts         # Native-structured: Fountain pass-through parse
    fdx.ts              # Native-structured: FDX XML parse
    celtx.ts            # Native-structured: Celtx zip+XML parse
    pdf.ts              # Heuristic-structured: PDF text extraction + structure detection
    docx.ts             # Heuristic-structured: DOCX style detection + text extraction
    paste.ts            # Heuristic/plain-text: paste-as-text structure inspection
    prose.ts            # Plain-text: text-only ingestion
  confidence.ts         # Confidence scoring engine (3 dimensions + aggregate)
  report.ts             # Writer report + council context generation
src/lib/schemas/
  ingestion.ts          # Zod schemas for all ingestion types
src/lib/prompts/
  ingestion.ts          # Prompt-builder ingestion context assembly
src/app/api/ingestion/
  ingest/route.ts       # POST endpoint
```

### 8. Solo vs Swarm Decision

**Recommendation: Solo build.**

Rationale:
- Parsers share a common interface and are tightly coupled to the confidence scoring engine
- The output shape (writer report, council context) depends on all parsers conforming exactly
- A swarm would create FC1/FC2/FC3 risks at parser boundaries with minimal parallelism benefit
- The spec is prescriptive enough that a single agent can implement cleanly
- Total file count is ~12 files — well within solo capacity

A swarm would make sense if parsers were truly independent services. Here they're modules within a single library, sharing types and constants. Solo eliminates cross-agent drift risk.

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| PDF parsing quality varies hugely | High | Return `failed` with guidance for unreadable PDFs. Don't over-promise. |
| Fountain spec edge cases (dual dialogue, forced elements) | Medium | Implement core syntax first. Edge cases documented in ingestion_warnings. |
| Celtx ZIP structure varies between versions | Medium | Only support modern desktop. Return failed + guidance for others. |
| DOCX screenplay style detection unreliable | Medium | Fall through to plain-text gracefully. Never invent structure. |
| NPM dependency weight for serverless | Low | pdf-parse + jszip + mammoth + fast-xml-parser are all lightweight. |
| Confidence scoring produces misleading numbers | Medium | Tier-aware interpretation per §5.5. QA with real scripts post-build. |

---

## Feed-Forward

- **Hardest decision:** Whether to include OCR in v1. Decided no — tesseract.js is too heavy for serverless, and the workshop audience likely uses text-selectable PDFs or Fountain/FDX. Scanned PDFs return `failed` with clear guidance.
- **Rejected alternatives:** Swarm build (7 agents, one per format) — rejected because parsers share types and confidence engine. Integration risk outweighs parallelism benefit. Also rejected: using LLM for format detection — heuristic detection is more reliable and cheaper.
- **Least confident:** Fountain parser implementation. The Fountain spec has many edge cases (forced elements with `!` and `.` prefixes, centered text with `>`, dual dialogue, lyrics). A custom parser must handle all of these correctly for the native-structured tier promise to hold. This is where the most bugs will likely surface.

---

## Refinement Findings (from brainstorm-refinement agent)

**STATUS: PASS** — 4 gaps found, all addressable in plan phase.

1. **Extension denylist + filename sanitization** — API route must reject non-screenplay extensions (.php, .sh, .exe) and apply NFKC normalization to filenames (null bytes, unicode homoglyphs). Add to route handler guard chain. (from: file-upload-service solution doc)

2. **XML sandboxing of user content in prompts** — raw_text and ingestion_warnings injected into council prompts must be wrapped in named XML tags (`<screenplay_text>`, `<ingestion_warnings>`) with injection defense. The WRC swarm build found 3 conflicting injection patterns when this wasn't specified. Highest risk for workshop demo. (from: WRC swarm build solution doc)

3. **Human spec verification (convergence loop)** — The external spec has not been through a human cross-section verification pass. Risk: shape mismatches between §4 parser output, §5 confidence dimensions, and §6.2 council context JSON that survive AI review. The plan must explicitly cross-reference these sections. (from: spec-convergence-loop solution doc)

4. **ID round-trip rule** — If ingestion results are persisted to Supabase, IDs must be generated once at the API route and propagated to all layers. The WRC editor hit a P0 when IDs were regenerated at the DB layer. Plan must decide: persist ingestion results to Supabase or not? If yes, prescribe ID flow. (from: editor-id-mismatch solution doc)
