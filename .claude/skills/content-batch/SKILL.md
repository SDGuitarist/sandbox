---
name: content-batch
description: Turn one weekly theme into a full Amplify content week — 3 angles, each with an Instagram + LinkedIn + Facebook post in Alex's voice (9 posts) + a brand-graphic card per angle rendered in BOTH a 1:1 square (1080x1080, Instagram) and a 4:5 portrait (1080x1350, LinkedIn/Facebook) = 6 graphics — gated by voice-guardian and written to one per-week batch.md at status:draft. Max-covered Claude Code only; NEVER executes the credit-billed content_pipeline.py.
argument-hint: "\"<one-line weekly theme>\" [ISO-week e.g. 2026-W29]"
allowed-tools: Read Write Edit Bash Grep Glob Task WebSearch
---

# Content Batch (Amplify weekly copy-gen + graphics)

Turns ONE weekly theme into a full, reviewable week Alex uploads by hand:

- **3 angles** on the theme — three genuinely different takes (e.g. the problem, the
  framework, a real story), so a week of posting doesn't repeat itself.
- **9 posts** — for EACH angle, an Instagram + LinkedIn + Facebook post in Alex's voice.
  That is 3 posts per platform per week.
- **6 graphics** — for EACH angle, ONE brand-graphic card (a `data.json` matching
  `content-engine/render.py`'s schema) rendered in **both** formats:
  - **1:1 square, 1080×1080** → the Instagram graphic
  - **4:5 portrait, 1080×1350** → the LinkedIn + Facebook graphic
- **1 staging file** — `content-engine/staging/<ISO-week>/batch.md` at `status: draft`,
  holding all 9 posts + graphic paths + the voice verdict. Alex reviews, flips to
  `approved`, and uploads by hand to Meta Business Suite (IG+FB) + LinkedIn native.

This is plan `docs/plans/2026-07-10-feat-amplify-content-engine-plan.md` **P3 + P4**, expanded
to a 3-angle / 3-per-platform weekly cadence with a dual-format (1:1 + 4:5) graphic per angle.

---

## GUARDRAILS — read first, do not violate

1. **BILLING (the #1 rule).** Copy is generated **by you, Claude Code, on the Max
   subscription** — you reason out the posts yourself in this session. There is **NO API
   call**. You **NEVER** run `content_pipeline.py`, **NEVER** read or set `ANTHROPIC_API_KEY`,
   **NEVER** call `api.anthropic.com`. `content_pipeline.py` is a **voice-spec SOURCE you
   READ, not a program you RUN** (executing it bills usage credits — the suspected cause of the
   pipeline going dormant). If any step would spend usage credits, STOP and tell Alex.
2. **Voice spec is reused VERBATIM.** The banned-vocabulary list, em-dash ban, one-CTA rule,
   and per-platform rules come from `content_pipeline.py`'s `SYSTEM_PROMPT` **word for word**.
   Load them (Step 1) and obey them. Do not paraphrase or "improve" them.
3. **Nothing posts automatically.** The batch stops at `status: draft`. Alex is the only one
   who publishes. No scheduler, no Metricool, no API posting.
4. **No fabrication.** Never invent stats, testimonials, quotes, or seat counts. If a claim
   needs a number, either source it (Step 2 WebSearch, 2026 data only) or don't make it.

## Bash Command Rules (repo-wide)

One command per Bash call. No `&&`, `;`, `for` loops, `cd && command`, `source`, or
`python3 -c`. Write a `.py`/`.json` file with the Write tool, then run the file.

---

## Inputs

- **`$1` = the weekly theme** (one line). Required. e.g. `"Trusting AI answers"` or
  `"The five-layer prompt"`. This is the umbrella; you generate the 3 angles from it.
- **`$2` = ISO week** (optional). e.g. `2026-W29`. If omitted, compute the current one.

If no theme was passed, ask Alex for the one-line theme and stop until you have it.

---

## Steps

### 1. Load the voice spec VERBATIM (single source of truth)

Read `content_pipeline.py` lines **35–153** — the `SYSTEM_PROMPT` string literal. That text
is your governing instruction set for every post: Voice DNA, the Hard Rules (em-dash ban,
banned vocabulary, banned phrases/patterns, one-CTA, max-one-exclamation, no fabrication,
read-aloud test), and the Platform Rules ("**LinkedIn gets the data. Instagram gets the hook.
Facebook gets the story.**"). Reuse it verbatim — do not restate it in your own words.

Reading the file is allowed and required. **Executing it is forbidden** (guardrail 1). Skip the
stale live-seat-count / past-workshop details inside `SYSTEM_PROMPT` (date, price); the voice
DNA, hard rules, and platform rules are the load-bearing verbatim part.

### 2. (Optional) Fresh-fact research — Max-covered WebSearch only

Most Amplify themes are frameworks and need **no external stats** (the framework is the
substance). Only if an angle genuinely needs a current fact, use the **WebSearch** tool
(Max-covered), 2026 data only, primary sources, recorded inline. Never fabricate. When in
doubt, skip research and let the idea carry the post.

### 3. Set up the week + pick 3 angles

- ISO week: if `$2` given, use it. Else run `date +%G-W%V` (one Bash call).
- Staging dir: `content-engine/staging/<ISO-week>/`. Create it (`mkdir -p`, one Bash call).
- **Pick 3 distinct angles** on the theme. Make them genuinely different lenses so the week
  has variety, not one idea three times. A reliable spread:
  1. **The problem / why it matters** (what goes wrong without this).
  2. **The framework** (the core how-to — usually the cleanest list card).
  3. **The application / a real story / common mistakes** (putting it to work).
  Each angle must be **framework-shaped enough to make a short list card** (Step 5) — a titled
  set of 3–5 short items. If an angle can't be a clean short list, reshape it until it can.
- For each angle, make a slug: lowercase, `a-z0-9`, spaces/punctuation → `-`, trim, ~40 chars.
  e.g. `angle-1-why-ai-sounds-sure`, `angle-2-the-3-question-test`, `angle-3-when-it-burned-me`.

### 4. Write the 9 posts (you, in Alex's voice)

For **each of the 3 angles**, write an Instagram, a LinkedIn, and a Facebook post on THAT
angle, obeying the Step-1 spec exactly:

- **Instagram** — hook-first, ≤150 words, punchy short paragraphs, one strong idea, 15–20
  hashtags at the end (mix broad + `#SanDiego`-niche), one CTA ("Save this" / "link in bio").
- **LinkedIn** — thought-leadership, 200–300 words, lead with the wedge ("work deeper, not
  faster"), data/frameworks live here, 3–5 hashtags, no link in body ("link in first comment").
- **Facebook** — personal narrative, 150–200 words, open on a specific moment not a thesis,
  no hashtags, end with a share ask.

Nine genuinely different posts — different angle AND different platform register. Read each
aloud in your head: does it sound like Alex talking to a peer? Kill any em-dash, banned word,
second CTA, or fabricated number before moving on. Do NOT write the same post three ways within
an angle, and do NOT let the three angles blur into the same post.

### 5. Build one brand-graphic card per angle (3 cards)

For **each angle**, distill it into ONE framework card matching **`render.py`'s schema exactly**:

```json
{
  "eyebrow": "Human-Led AI",              // small kicker; optional
  "title":   "The 3-Question",             // headline, ink-colored; required
  "accent":  "Test",                       // optional trailing word, ember-colored
  "items": [                                // 3–5 rows (see cap below)
    {"label": "Source", "desc": "where did it get this"},
    {"label": "Stake",  "desc": "what if it's wrong"},
    {"label": "Sense",  "desc": "match what you know"}
  ]
  // "site"/"tagline" optional — default to amplifyai.to / Human-Led AI
}
```

Rules that keep BOTH formats rendering clean:
- **3–5 items.** The 1:1 square (Instagram) has less height than the 4:5 — **cap at 5 items**
  so the square version never crowds. 3–4 is the sweet spot. (4:5 can take 6, but match the two.)
- Keep `label` ~1–2 words and `desc` ~2–5 words. Short — the card is a glance.
- `title` + `accent` read as one short headline; keep it to ~one line at 1:1 (the square uses a
  slightly smaller headline, so a title that wraps to 2 lines on 4:5 is fine as long as it's short).
- The card echoes the SAME idea its angle's 3 posts teach, so graphic and copy match.

Write each to `content-engine/staging/<ISO-week>/<angle-slug>.json` (Write tool).

### 6. Render each card in BOTH formats (this also validates the JSON)

For **each** angle's card JSON, run TWO renders (two Bash calls each):

```
lead-scraper/.venv/bin/python content-engine/render.py content-engine/staging/<ISO-week>/<angle-slug>.json content-engine/staging/<ISO-week>/<angle-slug>-1x1.png 1x1
lead-scraper/.venv/bin/python content-engine/render.py content-engine/staging/<ISO-week>/<angle-slug>.json content-engine/staging/<ISO-week>/<angle-slug>-4x5.png 4x5
```

- `-1x1.png` (1080×1080) is the **Instagram** graphic; `-4x5.png` (1080×1350) is the
  **LinkedIn + Facebook** graphic.
- Then verify all six dims (one Bash call):
  `lead-scraper/.venv/bin/python content-engine/tests/check_render.py content-engine/staging/<ISO-week>/*.png`
  Expect `1080x1080 OK (1x1)` and `1080x1350 OK (4x5)` lines, no FAIL.
- If a render errors (bad JSON) or a label/headline overflows a card edge — **check the 1:1
  especially, it has the least room** — shorten the offending text and re-render. Never ship a
  clipped card.

### 7. Write the draft `batch.md`

Create `content-engine/staging/<ISO-week>/batch.md` using the **Batch File Contract** below:
all 9 posts organized under their 3 angles, each angle's graphic paths, the Self-Check,
`voice_verdict: PENDING`, and `status: draft`.

### 8. Voice-guardian gate (GO / FIX)

Invoke the **voice-guardian** subagent (Task tool, `subagent_type: voice-guardian`) pointed at
the batch file:

> Voice-check the nine posts in `content-engine/staging/<ISO-week>/batch.md` (3 angles ×
> IG/LI/FB). Return your GO/FIX verdict.

- **GO** → record the verdict verbatim under `## Voice-Guardian Verdict`, set
  `voice_verdict: GO`, keep `status: draft`. Done.
- **FIX** → rewrite the flagged posts addressing every hard fail, rewrite `batch.md`, re-run
  voice-guardian. Loop **at most 3 times**. If it still returns FIX after 3 passes, record the
  last verdict, set `voice_verdict: FIX (unresolved)`, keep `status: draft`, and flag the
  specific blockers for Alex at the top of `batch.md`. Never mark a batch clean that the gate
  rejected.

### 9. Final guards (prove the invariants)

Run these (one Bash call each) and confirm before reporting done:

- **Billing guard** — must return NO matches:
  `grep -rn "ANTHROPIC_API_KEY\|api.anthropic.com" content-engine/`
- **Voice grep** — em-dash / common banned words, must return NO matches anywhere in the file
  (keep the whole batch em-dash-free, scaffolding included — the brand bans em-dashes
  everywhere, so use `:`, `.`, `,`, or `·` in headings/meta, never `—`):
  `grep -nE "—|\bdelve\b|\bleverage\b|\bseamless\b|\butilize\b" content-engine/staging/<ISO-week>/batch.md`
  (If you NAME a banned word as an example inside a post, prefer one outside this grep set —
  e.g. `unlock`/`elevate`/`tapestry` — so this guard stays a clean pass.)
- **Post count** — must return `9` (3 angles × 3 platforms):
  `grep -c "^### \(Instagram\|LinkedIn\|Facebook\) Post" content-engine/staging/<ISO-week>/batch.md`
- **Angle count** — must return `3`:
  `grep -c "^## Angle " content-engine/staging/<ISO-week>/batch.md`
- **Graphic count** — must return `6` (1:1 + 4:5 per angle):
  `ls content-engine/staging/<ISO-week>/*.png | wc -l`

### 10. Report

Tell Alex: the staging path, the voice verdict, the counts (9 posts / 6 graphics / 3 angles),
and the one next action — "review `batch.md`, flip `status: draft` → `approved`, then upload:
Instagram takes the `-1x1` graphic, LinkedIn + Facebook take the `-4x5`." Do not post anything.

---

## Batch File Contract (`batch.md`)

One file per week holds all 9 posts. No other per-week state files. Posts are `###` headers
nested under `## Angle N` headers (the guards count on this exact shape).

```markdown
---
theme: "<the weekly theme>"
iso_week: <2026-W29>
template_version: v1
angles:
  - slug: <angle-1-slug>
    card_json: <angle-1-slug>.json
    ig_graphic: <angle-1-slug>-1x1.png     # 1080x1080
    li_fb_graphic: <angle-1-slug>-4x5.png  # 1080x1350
  - slug: <angle-2-slug>
    card_json: <angle-2-slug>.json
    ig_graphic: <angle-2-slug>-1x1.png
    li_fb_graphic: <angle-2-slug>-4x5.png
  - slug: <angle-3-slug>
    card_json: <angle-3-slug>.json
    ig_graphic: <angle-3-slug>-1x1.png
    li_fb_graphic: <angle-3-slug>-4x5.png
voice_verdict: <PENDING | GO | FIX (unresolved)>
status: draft            # draft → approved → posted (Alex flips these by hand)
generated_by: claude-code (Max, zero usage credits)
generated_on: <YYYY-MM-DD>
---

# Weekly Batch: <theme>

3 angles · 9 posts (3 IG / 3 LI / 3 FB) · 6 graphics (1:1 for IG, 4:5 for LI+FB).

## Angle 1: <short angle title>

**Graphic:** IG `<angle-1-slug>-1x1.png` (1080×1080) · LI/FB `<angle-1-slug>-4x5.png` (1080×1350) · data `<angle-1-slug>.json`

### Instagram Post
<post copy incl. hashtags>

### LinkedIn Post
<post copy — link goes in first comment, not body>

### Facebook Post
<post copy — no hashtags>

## Angle 2: <short angle title>

**Graphic:** IG `<angle-2-slug>-1x1.png` (1080×1080) · LI/FB `<angle-2-slug>-4x5.png` (1080×1350) · data `<angle-2-slug>.json`

### Instagram Post
<...>

### LinkedIn Post
<...>

### Facebook Post
<...>

## Angle 3: <short angle title>

**Graphic:** IG `<angle-3-slug>-1x1.png` (1080×1080) · LI/FB `<angle-3-slug>-4x5.png` (1080×1350) · data `<angle-3-slug>.json`

### Instagram Post
<...>

### LinkedIn Post
<...>

### Facebook Post
<...>

## Self-Check
- [ ] No em-dashes anywhere (bodies AND scaffolding)
- [ ] No banned vocabulary
- [ ] No banned structural patterns
- [ ] Each post has exactly one CTA
- [ ] Max one exclamation mark per post (zero is better)
- [ ] Read-aloud test: every post sounds like Alex, not a marketing department
- [ ] No fabricated stats / testimonials / seat counts
- [ ] 3 angles are genuinely different, not one idea reworded
- [ ] Each angle's card teaches the same idea as its 3 posts
- [ ] All 6 graphics render clean at their dims (1:1 has the least room — check it)

## Voice-Guardian Verdict
<paste the voice-guardian GO/FIX output verbatim>

## Review & Publish (Alex)
1. Read the 9 posts. Light tweaks are fine.
2. Eyeball the 6 graphics — on-brand, legible, nothing clipped (check the 1:1s especially).
3. Flip `status: draft` → `approved`.
4. Upload per angle: **Instagram** post + its `-1x1.png`; **LinkedIn** + **Facebook** post +
   the `-4x5.png`. Put each LinkedIn link in the first comment. Then set `status: posted`.
```

---

## Done when

`content-engine/staging/<ISO-week>/` holds ONE `batch.md` (9 posts under 3 angles + self-check +
voice verdict, `status: draft`) + 3 card JSONs + 6 PNGs (a `-1x1` and a `-4x5` per angle, all
passing `check_render.py`), the voice-guardian verdict is recorded, and all Step-9 guards pass.
Zero usage credits spent.
