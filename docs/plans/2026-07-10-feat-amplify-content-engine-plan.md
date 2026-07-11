---
title: "Amplify Content Engine — Weekly Copy + Brand-Graphic Generator"
date: 2026-07-10
status: draft
type: solo-build          # NOT a swarm — small, human-gated, integration-light
brand: Amplify AI
namespace: content-engine/
traces_to: docs/brainstorms/2026-07-09-content-graphic-template-system.md
supersedes_assumption: "Metricool auto-scheduling (account lapsed, not resubscribing) + reviving credit-billed content_pipeline.py"
feed_forward:
  risk: "The loop dies again if the generated COPY isn't publishable-quality. The pipeline went dormant on production friction / copy quality, NOT on a missing tool. If Alex won't post what it writes, graphics and scheduling are irrelevant. Verify copy quality (Phase 0 Spike A) BEFORE building the loop."
  verify_first: true
---

# Amplify Content Engine — Plan

## Summary

A small solo build that produces, from one weekly topic input, a ready-to-post batch
of **3 posts (Instagram / LinkedIn / Facebook) in Alex's voice + 3 on-brand 1:1
graphics + a single review sheet**, so Alex can batch-schedule 3 posts/week into free
native tools (~10 min/week). The outcome is *posts actually going out* to stay visible
for the Amplify AI brand — not a production system.

Two decisions (2026-07-10) narrowed the brainstorm's Option A:
- **Copy engine = Claude Code (Max-covered), NOT `content_pipeline.py`.** The existing
  script calls the raw Anthropic API (`ANTHROPIC_API_KEY`) = pay-as-you-go usage
  credits (Alex's #1 billing nono, and a likely cause of dormancy). Copy-gen is
  reimplemented as a Claude Code subagent/skill that **reuses the proven voice spec**
  from `content_pipeline.py`'s `SYSTEM_PROMPT` verbatim.
- **Scheduling = native free tools (Meta Business Suite for IG+FB, LinkedIn native),
  manual weekly upload.** Metricool is gone (lapsed, not resubscribing). This *removes*
  the brainstorm's #1 risk (unverified Metricool API) AND its hidden dependency
  (hosting each PNG at a public URL). Native tools accept a graphic uploaded from disk.

## Plan Quality Gate (the 4 questions)

**1. What exactly is changing?**
A new top-level `content-engine/` build is added with: a versioned HTML/CSS graphic
template (`v1`, 1:1 square), a pure `render_template(data) -> html` function separated
from a `render_to_png(html, path)` Playwright I/O function, a Claude Code copy-gen
step reusing the existing voice spec, a voice-guardian gate, and a single per-week
staging file (`batch.md`) + folder. One command produces a full weekly batch.

**2. What must NOT change?**
- **Alex's voice rules** — the banned-vocabulary list, em-dash ban, one-CTA rule, and
  per-platform rules from `content_pipeline.py`'s `SYSTEM_PROMPT` are reused **verbatim**,
  not paraphrased. (They are proven; "LinkedIn gets the data, Instagram gets the hook,
  Facebook gets the story" is load-bearing.)
- **Billing invariant** — copy-gen NEVER uses the raw Anthropic API / `ANTHROPIC_API_KEY`.
  Max-covered Claude Code only. No usage-credit path anywhere in the loop.
- **Outward-facing gate** — nothing is posted without Alex's review. The system stops at
  a `status: draft` staging sheet; Alex approves and uploads manually.
- **`content_pipeline.py` stays on disk** as reference (do NOT delete or "migrate" it).

**3. How will we know it worked?**
Near-term: a full weekly batch is produced in **< 30 min human time**, the copy is
publishable **without heavy editing**, and graphics render on-brand at exactly
1080×1080. See `## Acceptance Tests`. True success = **3 posts/week going out for 4
consecutive weeks** (the brainstorm's expansion trigger).

**4. What is the most likely way this plan is wrong?**
The generated **copy isn't good enough for Alex to actually publish** — the same
production-friction/quality failure that made `content_pipeline.py` dormant. Building
template + render + staging around copy Alex won't post rebuilds a dormant machine.
**Mitigation: Phase 0 Spike A is a hard human gate — generate one real week's copy and
have Alex answer "would I publish this as-is?" before any loop-building starts.**

## Architecture

```
weekly topic (manual, one line)
      │
      ▼
[copy-gen]  Claude Code subagent, reuses content_pipeline.py SYSTEM_PROMPT voice spec
      │      → 3 posts (IG/LI/FB) + a short graphic_headline per post
      ▼
[voice-guardian]  GO / FIX gate (existing subagent)   ── FIX ─▶ back to copy-gen
      │ GO
      ▼
[render]  render_template(data) -> html   (PURE, no I/O)
          render_to_png(html, path)        (Playwright I/O, isolated)
      │      → 3× 1080×1080 PNG
      ▼
[staging]  content-engine/staging/<ISO-week>/batch.md  (SINGLE file: topic, 3 posts,
           self-check, voice verdict, graphic paths, status: draft)  + the 3 PNGs
      │
      ▼
Alex reviews batch.md → approves → uploads to Meta Business Suite (IG+FB) + LinkedIn
```

Design invariants (from prior lessons, carried in the brainstorm):
- **Phase 0 fixture spikes before any loop-building.**
- **Pure `render_template(data)` separated from Playwright I/O** — render logic is unit-testable without a browser.
- **Versioned template** — `TEMPLATE_VERSION = 'v1'` stamped into `data` and the output filename, so slot/layout drift is detectable.
- **Single staging file** (`batch.md`) per week — no multi-file state to drift out of sync.

## Phase 0 — Verify-First Spikes (HARD GATES; no loop-building until both pass)

**Spike A — Copy quality (the kill test).** Using the voice spec, generate ONE real
week's 3 posts for a genuine Amplify topic. Alex reads them and answers a single
question: *"Would I publish these as-is (or with only light tweaks)?"*
- PASS → proceed. FAIL → fix the copy-gen prompt/approach and re-spike. **Do not build
  the loop on failing copy.** This directly tests the dormancy cause.
- *Executable in-session by Claude Code (Max-covered) — cheap, immediate.*
- ✅ **RESULT (2026-07-10): PASS.** Topic "five-layer prompt for beginners." Alex
  confirmed he'd publish as-is. Copy-gen ran on Max (zero credits), voice spec reused
  verbatim. Dormancy/copy-quality risk retired with evidence. Raw output:
  `content-engine/spikes/2026-07-10-spike-a-five-layer-prompt.md`.

**Spike B — Render fidelity.** Render a real headline through template `v1` to PNG
and eyeball: correct dims, legible fonts, and **text overflow** behavior.
- PASS → template contract is sound. FAIL → fix wrapping/truncation before wiring the loop.
- ✅ **RESULT (2026-07-11): PASS.** `content-engine/template/v1.html` renders via
  `tests/render_card.py` (Playwright + chromium in `lead-scraper/.venv`) to
  `content-engine/out/the-5-layer-prompt.png`, verified at exact pixel dims. **FORMAT
  CHANGED after design iteration: 4:5 portrait (1080×1350), NOT 1:1** — a five-item
  framework is text-forward and needs the extra height; 4:5 posts natively on IG/FB and
  works on LinkedIn. Final design: light warm theme, real logo asset
  (`assets/logo-amplify-ai.png`, trimmed transparent), sampled brand colors
  (#E8471C / #242424), Hanken Grotesk + Space Mono, amplifyai.to · Human-Led AI footer
  bottom-left. **Phase 0 COMPLETE** (both spikes green).

*(The Metricool API spike from the brainstorm is DELETED — native scheduling has no API.)*

## Build Phases (only after Phase 0 is green)

- **P1 — Template + render.** `content-engine/template/v1.html` + `.css` (brand tokens:
  color, logo, font). `render_template(data) -> html` (pure). `render_to_png(html, path)`
  (Playwright, headless, viewport 1080×1080). `data = {brand, headline, subline?,
  template_version, accent}`.
- **P2 — Staging contract.** `content-engine/staging/<ISO-week>/batch.md` writer. One
  file holds everything; PNGs live beside it. `status` field: `draft → approved → posted`.
- **P3 — Copy-gen + voice gate.** Claude Code copy-gen step (reuses the voice spec) →
  voice-guardian GO/FIX → writes posts + graphic_headlines into `batch.md`. Optional
  web-research via Claude Code WebSearch (Max-covered) when a topic needs a fresh fact.
- **P4 — Weekly glue + review gate.** One entrypoint produces the full batch for a given
  topic + ISO week, leaves it `status: draft`. Alex reviews, flips to `approved`,
  uploads to Meta Business Suite + LinkedIn manually. No auto-post.

## Acceptance Tests (EARS)

### Happy path
- WHEN given a weekly topic, THE SYSTEM SHALL write a `batch.md` containing exactly 3
  posts labeled `## Instagram Post`, `## LinkedIn Post`, `## Facebook Post`, each in
  Alex's voice.
- WHEN copy is generated, THE SYSTEM SHALL run a voice-guardian pass and record a GO
  verdict (or an itemized FIX list) in `batch.md` before any graphic is rendered.
- WHEN `render_template(data)` is called with a valid headline, THE SYSTEM SHALL emit a
  PNG of exactly 1080×1080 px at the staging path, filename stamped with `v1`.
- WHEN a weekly batch completes, THE SYSTEM SHALL leave ONE staging folder with 3 posts +
  3 PNGs + `batch.md` at `status: draft`.

### Error cases
- WHEN generated copy contains an em-dash or a banned-vocabulary word, THE SYSTEM SHALL
  mark the voice-guardian verdict FIX and SHALL NOT advance the batch to `draft`-ready.
- WHEN a headline exceeds the template's safe length, THE SYSTEM SHALL wrap or flag
  overflow (never silently clip past the card edge).
- WHEN the rendered image is not exactly 1080×1080, THE SYSTEM SHALL fail the render
  fixture check.
- WHEN copy-gen runs, THE SYSTEM SHALL NOT read `ANTHROPIC_API_KEY` or call
  `api.anthropic.com` (billing invariant — Max-covered Claude Code only).

### Verification commands
- Render fixture → dims check: `.venv/bin/python content-engine/tests/check_render.py`
  — prints `1080x1080 OK` for each fixture PNG (write to a file, run the file — no
  inline `python -c`, per repo Bash rules).
- Billing guard: `grep -rn "ANTHROPIC_API_KEY\|api.anthropic.com" content-engine/`
  — returns **no matches** (empty = pass).
- Voice check: `grep -nE "—|\bdelve\b|\bleverage\b|\bseamless\b" content-engine/staging/<week>/batch.md`
  — no matches in the post bodies.
- Batch shape: `grep -c "^## \(Instagram\|LinkedIn\|Facebook\) Post" content-engine/staging/<week>/batch.md`
  — returns `3`.

## Cost / Billing
Whole loop is **$0 recurring**: Claude Code copy-gen is Max-covered, Playwright is a
local dep already in the repo, native schedulers are free, no Metricool subscription.
No usage-credit path exists by design (enforced by the billing-guard acceptance test).

## Open decisions (small, for Alex — none block Phase 0)
- **Brand tokens for template v1:** Amplify color/logo/font. Provide assets or approve a
  simple default (accent + wordmark) — resolved during Spike B.
- **Graphic-per-post vs one shared graphic/week:** plan assumes one per post (each from
  that post's `graphic_headline`); can collapse to one shared card if you prefer less.
- **Topic input:** start manual (one line/week). Automate from a mind-dump file only if
  the manual step becomes the bottleneck.

## Feed-Forward
- **Hardest decision:** whether to keep any of `content_pipeline.py`. Chose to **reuse
  its voice spec verbatim but not its runtime** — the voice rules are the valuable,
  proven part; the raw-API runtime is the billing liability and a dormancy suspect.
- **Rejected alternatives:** reviving credit-billed `content_pipeline.py` (billing nono);
  Metricool/Buffer/self-hosted schedulers (subscription, API risk, or upkeep — all
  heavier than a 10-min manual native upload for 3 posts/week).
- **Least confident:** copy publishability. Dormancy was almost certainly a
  copy-quality/friction problem, and we are rebuilding the copy engine. Spike A is the
  cheap kill test; if it fails, the fix is the prompt, not more plumbing. (Second: render
  overflow/emoji fidelity — Spike B.)

## Codex Handoff Prompt
```
Review docs/plans/2026-07-10-feat-amplify-content-engine-plan.md (sandbox repo). It is a
SOLO build (not swarm) for a $0 weekly content generator: Claude Code copy-gen
(Max-covered, reusing content_pipeline.py's SYSTEM_PROMPT voice spec verbatim) →
voice-guardian gate → Playwright-rendered 1:1 brand graphic → single per-week staging
file (batch.md) → Alex manually uploads to Meta Business Suite + LinkedIn (no API, no
Metricool, no subscription).

Hunt for: (1) any place the design could reintroduce a raw-Anthropic-API / usage-credit
path (billing invariant must hold); (2) whether the pure render_template(data) vs
Playwright render_to_png(html, path) separation is clean enough to unit-test rendering
without a browser; (3) gaps in the Phase 0 gates — is Spike A (copy publishability) a
strong enough kill test, and is Spike B's overflow/emoji/dims check complete; (4) staging
single-file contract: any multi-file state that could drift; (5) EARS coverage — is every
invariant (billing guard, 1080x1080, voice bans, review-before-post) backed by a
verification command. Report P0 cross-section contradictions only. If none, say so —
that's the signal it's ready for the work phase.
```
