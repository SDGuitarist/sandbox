---
title: "API Key Rotation: Verify With a Real Auth Call, Not a String Match"
date: 2026-06-12
type: solution
tags: [security, api-keys, key-rotation, env-vars, dotenv, verification, anthropic-api]
project: cross-project
trigger: "Anthropic suspended Fable 5/Mythos 5 (govt directive); prompted a precautionary key rotation after an API key was exposed in a transcript"
severity: high
---

# API Key Rotation: Verify With a Real Auth Call, Not a String Match

## What Happened

After an `ANTHROPIC_API_KEY` was accidentally echoed into a Claude Code transcript (via `env | grep`), Alex did a full rotation: disabled + deleted all keys in the Anthropic console, created a new key, and updated `~/.zshrc`. We then propagated the new key into the 5 project `.env` files that read it at runtime (`sandbox`, `expert-pipeline`, `gigprep`, `lead-scraper`, `venue-scraper`).

The rotation **looked** complete and a string-comparison check **passed** — but the scripts would have failed. An actual API auth test (HTTP 401 vs 200) was the only thing that caught it.

## The Bug

1. The propagation one-liner copied the key from the **live shell env** (`$ANTHROPIC_API_KEY`).
2. That terminal still held the **old** key — `~/.zshrc` had been edited but not reloaded — so the now-deleted key got written into all 5 `.env` files.
3. The verification compared each `.env` value against `$ANTHROPIC_API_KEY` (also the old key in that frozen Claude Code session), so **every copy "matched"** — a false green.
4. Truth surfaced only on `curl` to `/v1/messages`: `~/.zshrc` = 200 (valid), session env = 401, every `.env` = 401.

Three compounding traps:
- **Stale shell env.** A Claude Code session freezes `$ANTHROPIC_API_KEY` at launch; it stays stale until restart. Never treat it as ground truth mid-rotation.
- **Match-check blindness.** Comparing two copies that are both wrong (same dead key) passes. Equality ≠ validity.
- **`load_dotenv(override=False)` shadowing.** A shell export shadows a project `.env`, so a stale `.env` can hide behind a good shell value until a cron/no-export context runs the script and 401s.

A fourth, smaller trap surfaced in the fix: `grep -v 'KEY=' file > tmp && printf ...` **aborts** when the file is a single key-only line — `grep -v` exits 1 when no lines survive, breaking the `&&` chain. `sandbox/.env` (one line) silently didn't update until rewritten as `{ grep -v ... || true; printf ...; } > tmp`.

## The Fix (and the durable pattern)

1. **Propagate from the verified source file, not the live env.** Read the key from `~/.zshrc` (confirmed valid) rather than `$ANTHROPIC_API_KEY`.
2. **Verify each location with a real auth call**, status-only, key never printed:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages \
     -H "x-api-key: $K" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
     -d '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}'
   # 200 = valid; 401 = rejected
   ```
3. **Rewrite key-only `.env` files defensively:** `{ grep -v '^ANTHROPIC_API_KEY=' "$f" || true; printf 'ANTHROPIC_API_KEY=%s\n' "$K"; } > "$f.tmp" && mv "$f.tmp" "$f"`.
4. **Restart the Claude Code session** to clear the stale frozen key from its env.

## Verification (final state)

All six locations returned HTTP 200: `~/.zshrc` + the 5 project `.env` files. No real key committed in any tracked file (all `sk-ant-` hits were placeholders/test fixtures). All `.env` files gitignored. Stray `.env.tmp` artifacts removed.

## Follow-Up: Deployed Secret Stores (the part local fixes miss)

Rotating local files is only half the job — the same dead key lives in every deploy target's secret store. Map them by intersecting "projects referencing the key" with "projects that have a deploy config" (`railway.*`, `vercel.json`, `.github/workflows`, `fly.toml`). For this account: amplify-workshop (GH Actions), writers-room-council + ai-literacy-game (Vercel), gig-lead-responder + gigprep + pf-intel (Railway). Each platform's "last updated" timestamp tells you if the secret predates the rotation (= stale/dead).

### Platform gotchas (each cost real time)

- **`vercel env add` silently stores EMPTY from piped/redirected stdin.** `printf '%s' "$K" | vercel env add NAME production`, `printf '%s\n' ...`, and `vercel env add ... < file` ALL stored a zero-length value (the CLI is interactive-first and ignores non-TTY input, printing a misleading `- vercel env ls` hint as if it succeeded). Verified empty three times via `vercel env pull` + length check. **Fix:** set Vercel env vars via the dashboard, or run `vercel env add` interactively in a real terminal and paste at the prompt. Then **redeploy** — Vercel env changes only take effect on the next deployment, not the running one.
- **`gh secret set` from piped stdin IS reliable** (purpose-built for CI), but GitHub never lets you read a secret back — so it can't be curl-verified. The only real verification is running the workflow (`gh workflow run`), which may have side effects (e.g. weekly-intel sends a live email + commits). Weigh that against confidence in the write.
- **Railway CLI OAuth tokens expire silently** (`invalid_grant`). `railway login` is required before `railway variables` works; can't be done unattended.
- **Verify each store the same way as local:** for Vercel, `vercel env pull` then curl the value (HTTP 200). This is what caught the empty-store bug. The lesson from the local phase (verify with a real auth call) applies doubly to remote stores, because their failure modes are sneakier.

## Feed-Forward

- **Hardest decision:** Whether to handle the secret at all vs. hand the user a self-serve command. Resolved by always reading the key from a file and never echoing it — the value never entered the transcript on any fix step.
- **Rejected alternatives:** Running the scripts end-to-end to "prove" they work — rejected because `lead-scraper`/`venue-scraper` touch real data (production-DB safety rule). A minimal `/v1/messages` auth call tests the only thing that was broken (the key) without side effects.
- **Least confident → resolved:** The original "do deployed secret stores still hold the old key?" was audited (see Follow-Up). amplify-workshop GH secret (stale, fixed) and writers-room-council Vercel (stale, handed off — CLI couldn't set it) confirmed dead; Railway services unreachable (expired token, deferred to user). New least-confident item: whether the `gh secret set` write to amplify-workshop actually landed (unverifiable without running the workflow) — high confidence, but only Monday's scheduled run proves it.
