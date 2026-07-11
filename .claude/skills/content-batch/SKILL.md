---
name: content-batch
description: Turn one weekly topic into a ready-to-review Amplify content batch — 3 platform posts (Instagram / LinkedIn / Facebook) in Alex's voice + a 1:1.25 brand-graphic card JSON (rendered to PNG) + a single per-week batch.md at status:draft. Runs the voice-guardian gate. Max-covered Claude Code only; NEVER executes the credit-billed content_pipeline.py.
argument-hint: "\"<one-line weekly topic>\" [ISO-week e.g. 2026-W29]"
allowed-tools: Read Write Edit Bash Grep Glob Task WebSearch
---

# Content Batch (Amplify weekly copy-gen + graphic)

Turns ONE weekly topic into a reviewable batch Alex can upload by hand:

- **3 posts** — Instagram, LinkedIn, Facebook — in Alex's voice, one topic, three genuinely
  different posts (never the same post three ways).
- **1 brand-graphic card** — a `data.json` matching `content-engine/render.py`'s schema,
  rendered to a 1080×1350 PNG.
- **1 staging file** — `content-engine/staging/<ISO-week>/batch.md` at `status: draft`,
  holding everything (posts, self-check, voice verdict, card + PNG paths). Alex reviews,
  flips to `approved`, and uploads manually to Meta Business Suite (IG+FB) + LinkedIn native.

This is plan `docs/plans/2026-07-10-feat-amplify-content-engine-plan.md` **P3 + P4**.

---

## GUARDRAILS — read first, do not violate

1. **BILLING (the #1 rule).** Copy is generated **by you, Claude Code, on the Max
   subscription**. You reason out the three posts yourself in this session. There is **NO
   API call**. You **NEVER** run `content_pipeline.py`, **NEVER** read or set
   `ANTHROPIC_API_KEY`, **NEVER** call `api.anthropic.com`. `content_pipeline.py` is a
   **voice-spec SOURCE you READ, not a program you RUN** (executing it bills usage credits
   — the suspected cause of the pipeline going dormant). If any step would spend usage
   credits, STOP and tell Alex.
2. **Voice spec is reused VERBATIM.** The banned-vocabulary list, em-dash ban, one-CTA rule,
   and per-platform rules come from `content_pipeline.py`'s `SYSTEM_PROMPT` **word for word**.
   You load them (Step 1) and obey them. Do not paraphrase or "improve" them.
3. **Nothing posts automatically.** The batch stops at `status: draft`. Alex is the only one
   who publishes. No scheduler, no Metricool, no API posting.
4. **No fabrication.** Never invent stats, testimonials, quotes, or seat counts. If a claim
   needs a number, either source it (Step 2 WebSearch, 2026 data only) or don't make it.

## Bash Command Rules (repo-wide)

One command per Bash call. No `&&`, `;`, `for` loops, `cd && command`, `source`, or
`python3 -c`. Write a `.py`/`.json` file with the Write tool, then run the file.

---

## Inputs

- **`$1` = the weekly topic** (one line). Required. e.g. `"The 4 tells that scream 'AI wrote this'"`.
- **`$2` = ISO week** (optional). e.g. `2026-W29`. If omitted, compute the current one.

If no topic was passed, ask Alex for the one-line topic and stop until you have it.

---

## Steps

### 1. Load the voice spec VERBATIM (single source of truth)

Read `content_pipeline.py` lines **35–153** — the `SYSTEM_PROMPT` string literal. That text
is your governing instruction set for the three posts: Voice DNA, the Hard Rules (em-dash ban,
banned vocabulary, banned phrases/patterns, one-CTA, max-one-exclamation, no fabrication,
read-aloud test), and the Platform Rules ("**LinkedIn gets the data. Instagram gets the hook.
Facebook gets the story.**"). Reuse it verbatim — do not restate it in your own words.

Reading the file is allowed and required. **Executing it is forbidden** (guardrail 1).

Skip the parts of `SYSTEM_PROMPT` that don't apply to a draft batch: the live seat-count /
workshop-registration messaging and the specific past-workshop details (date/price) are stale
reference, not voice rules. The **voice DNA, hard rules, and platform rules are the load-bearing,
verbatim part** — those you obey exactly.

### 2. (Optional) Fresh-fact research — Max-covered WebSearch only

Most Amplify topics are frameworks and need **no external stats** (the framework is the
substance — see `content-engine/spikes/2026-07-10-spike-a-five-layer-prompt.md`). Only if the
topic genuinely needs a current fact, use the **WebSearch** tool (Max-covered), 2026 data only,
primary sources, and record the source inline. Never fabricate. When in doubt, skip research and
let the idea carry the post.

### 3. Set up the week + slug

- ISO week: if `$2` given, use it. Else run `date +%G-W%V` (one Bash call) and use that.
- Slug: lowercase the topic, keep `a-z0-9`, replace spaces/punctuation with `-`, collapse
  repeats, trim, cap ~40 chars. e.g. `The 4 tells that scream "AI wrote this"` → `the-4-tells-ai-writing`.
- Staging dir: `content-engine/staging/<ISO-week>/`. Create it (`mkdir -p`, one Bash call).

### 4. Write the 3 posts (you, in Alex's voice)

Draft Instagram, LinkedIn, and Facebook posts on the topic, obeying the Step-1 spec exactly:

- **Instagram** — hook-first, ≤150 words, punchy short paragraphs, one strong idea, 15–20
  hashtags at the end (mix broad + `#SanDiego`-niche), one CTA ("Save this" / "link in bio").
- **LinkedIn** — thought-leadership, 200–300 words, lead with the wedge ("work deeper, not
  faster"), data/frameworks live here, 3–5 hashtags, no link in body ("link in first comment").
- **Facebook** — personal narrative, 150–200 words, open on a specific moment not a thesis,
  no hashtags, end with a share ask.

Three genuinely different posts. Read each aloud in your head: does it sound like Alex talking
to a peer? Kill any em-dash, banned word, second CTA, or fabricated number before moving on.

### 5. Build the brand-graphic card JSON

Distill the topic into ONE framework card matching **`render.py`'s schema exactly**:

```json
{
  "eyebrow": "Human-Led AI",              // small kicker; optional (e.g. "Amplify Framework")
  "title":   "The 4",                      // headline, ink-colored; required
  "accent":  "Tells",                      // optional trailing word, ember-colored
  "items": [                                // 3–6 rows (4:5 canvas fits ~6 comfortably)
    {"label": "Em-dashes",  "desc": "the AI comma"},
    {"label": "Buzzwords",  "desc": "delve, leverage, seamless"},
    {"label": "Symmetry",   "desc": "every sentence same length"},
    {"label": "Empty opens","desc": "in today's fast-paced world"}
  ]
  // "site"/"tagline" optional — default to amplifyai.to / Human-Led AI
}
```

Rules that keep it rendering clean:
- **3–6 items.** Fewer than 3 looks thin; more than 6 overflows the card.
- Keep `label` ~1–2 words and `desc` ~2–5 words (short — the card is a glance, not a paragraph).
- `title` + `accent` should read as one short headline ("The 4 · Tells").
- The card echoes the SAME framework the posts teach, so graphic and copy match.

Write it to `content-engine/staging/<ISO-week>/<slug>.json` (Write tool).

### 6. Render the card → PNG (this also validates the JSON)

One Bash call:

```
lead-scraper/.venv/bin/python content-engine/render.py content-engine/staging/<ISO-week>/<slug>.json content-engine/staging/<ISO-week>/<slug>.png
```

Then verify dimensions (one Bash call):

```
content-engine/tests/check_render.py wrapper OR: lead-scraper/.venv/bin/python content-engine/tests/check_render.py content-engine/staging/<ISO-week>/<slug>.png
```

Expect `... 1080x1350 OK`. If render errors (bad JSON) or dims are wrong, fix the JSON and
re-render before continuing. If a headline/label overflows the card edge, shorten it — never
ship a clipped card.

### 7. Write the draft `batch.md`

Create `content-engine/staging/<ISO-week>/batch.md` using the **Batch File Contract** below,
with the 3 posts, the Self-Check, the card/PNG paths, `voice_verdict: PENDING`, and
`status: draft`.

### 8. Voice-guardian gate (GO / FIX)

Invoke the **voice-guardian** subagent (Task tool, `subagent_type: voice-guardian`) and point it
at the batch file:

> Voice-check the three posts in `content-engine/staging/<ISO-week>/batch.md`. Return your
> GO/FIX verdict.

- **GO** → record the verdict block verbatim in `batch.md` under `## Voice-Guardian Verdict`,
  set `voice_verdict: GO`, keep `status: draft`. Done.
- **FIX** → rewrite the flagged posts addressing every hard fail, rewrite `batch.md`, and
  re-run voice-guardian. Loop **at most 3 times**. If it still returns FIX after 3 passes,
  record the last verdict, set `voice_verdict: FIX (unresolved)`, keep `status: draft`, and
  flag the specific blockers for Alex at the top of `batch.md`. Never mark a batch clean that
  the gate rejected.

### 9. Final guards (prove the invariants)

Run these (one Bash call each) and confirm before reporting done:

- **Billing guard** — must return NO matches:
  `grep -rn "ANTHROPIC_API_KEY\|api.anthropic.com" content-engine/`
- **Voice grep** — em-dash / common banned words, must return NO matches anywhere in the file
  (keep the whole batch em-dash-free, scaffolding included — the brand bans em-dashes
  everywhere, so use `:`, `.`, `,`, or `·` in headings/meta, never `—`):
  `grep -nE "—|\bdelve\b|\bleverage\b|\bseamless\b|\butilize\b" content-engine/staging/<ISO-week>/batch.md`
  (If you deliberately NAME a banned word as an example inside a post about AI writing, prefer an
  example outside this grep set, e.g. `unlock`/`elevate`/`tapestry`, so this guard stays a clean
  pass. The ban is on Alex USING the words, not naming them.)
- **Batch shape** — must return `3`:
  `grep -c "^## \(Instagram\|LinkedIn\|Facebook\) Post" content-engine/staging/<ISO-week>/batch.md`

### 10. Report

Tell Alex: the staging path, the voice verdict, the PNG path, and the one next action —
"review `batch.md`, flip `status: draft` → `approved`, upload the 3 posts + card to Meta
Business Suite (IG+FB) and LinkedIn." Do not post anything yourself.

---

## Batch File Contract (`batch.md`)

One file per week holds everything. No other per-week state files.

```markdown
---
topic: "<the weekly topic>"
iso_week: <2026-W29>
template_version: v1
card_json: <slug>.json
card_png: <slug>.png
voice_verdict: <PENDING | GO | FIX (unresolved)>
status: draft            # draft → approved → posted (Alex flips these by hand)
generated_by: claude-code (Max, zero usage credits)
generated_on: <YYYY-MM-DD>
---

# Weekly Batch: <topic>

**Graphic:** `<slug>.png` (1080×1350, template v1) · data `<slug>.json`

## Instagram Post

<post copy incl. hashtags>

## LinkedIn Post

<post copy — link goes in first comment, not body>

## Facebook Post

<post copy — no hashtags>

## Self-Check
- [ ] No em-dashes anywhere
- [ ] No banned vocabulary
- [ ] No banned structural patterns
- [ ] Each post has exactly one CTA
- [ ] Max one exclamation mark per post
- [ ] Read-aloud test: sounds like Alex, not a marketing department
- [ ] No fabricated stats / testimonials / seat counts
- [ ] Card graphic teaches the same framework as the posts

## Voice-Guardian Verdict
<paste the voice-guardian GO/FIX output verbatim>

## Review & Publish (Alex)
1. Read the 3 posts. Light tweaks are fine.
2. Eyeball `<slug>.png` — on-brand, legible, nothing clipped.
3. Flip `status: draft` → `approved`.
4. Upload: IG + FB via Meta Business Suite, LinkedIn native. Put the LinkedIn link in the
   first comment. Then set `status: posted`.
```

---

## Done when

`content-engine/staging/<ISO-week>/` holds ONE `batch.md` (3 posts + self-check + voice verdict,
`status: draft`) + `<slug>.json` + `<slug>.png` (1080×1350), the voice-guardian verdict is
recorded, and all three Step-9 guards pass. Zero usage credits spent.
