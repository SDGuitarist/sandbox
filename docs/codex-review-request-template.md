# Codex Review-Request Template (HARDENED)

Purpose: Codex is a *different* agent — it does not share this repo's CLAUDE.md,
memory, or handoff conventions, it degrades on long prose, and it stalls when the
ask is ambiguous. This template over-specifies the request so Codex has no room to
misbehave, and it forces Codex's OUTPUT into a fixed, machine-checkable shape.

How to use: copy the skeleton below, fill every `[BRACKET]`, delete the guidance
comments (the `> …` lines), and send. Then validate Codex's reply against the
"Return-acceptance checklist" at the bottom BEFORE acting on it. If the reply is
missing the `VERDICT:` line or any required table row, treat the review as INVALID
and re-send — do not act on a malformed review.

Global reuse: this lives in-repo (sandbox contract forbids me writing to
`~/.claude/`). To reuse across projects, copy it to `~/.claude/docs/` next to
`codex-handoff-templates.md` yourself.

Five rules this template encodes (from the 2026-07-22 Codex failures):
1. ONE review target, referenced as the branch TIP by name — never a second/pinned SHA.
2. A machine-checkable OUTPUT CONTRACT (VERDICT line + per-item table).
3. A DoD checklist grounded in COMMANDS Codex must run and paste, not opinions.
4. Self-contained context (Codex can't see CLAUDE.md) + short, structured, ask-first.
5. Dictate the format of Codex's RETURN handoff (so its output is paste-ready, not mush).

---

## SKELETON (copy from here)

```
Work in /Users/alejandroguillen/Projects/[REPO]
Branch: [BRANCH]
Review target: the current TIP of that branch. Run `git rev-parse [BRANCH]` and review
THAT exact commit. Do NOT ask me which commit — the tip is the single authoritative HEAD;
everything to review is on it. If your checkout shows a different tip, `git fetch` first.

ASK (one decision): [e.g. "GO / NO-GO on whether §1 is correctly implemented per the plan"].
This is a [PLAN | CODE] review. Do NOT write code. Do NOT ask for confirmation of the
commit, branch, or scope — everything you need is below.

READ THESE FILES FIRST (Codex has no other context):
  - HANDOFF.md
  - CLAUDE.md
  - AGENTS.md (if it exists)
  - [PLAN OR SPEC PATH]
  - [any other must-read]

WHAT THIS IS (3 lines max, self-contained):
  [plain-English: what the project/change is, and what "correct" looks like]

REVIEW THIS FOR (numbered, specific — not "is it good"):
  1. [gap check]  2. [wrong-assumption check]  3. [scope / must-not-change check]
  4. [the plan's Feed-Forward "least confident" item]  5. [security/regression if CODE]

GROUND-TRUTH FILES TO CROSS-CHECK (open them; do not trust this summary):
  - [file] — [what to verify in it]
  - [file] — [what to verify in it]

DEFINITION OF DONE — you MUST complete every item and show its result inline:
  [ ] 1. Ran `[TEST/GREP COMMAND]` — paste the last line.
  [ ] 2. Ran `[TEST/GREP COMMAND]` — paste the last line.
  [ ] 3. Confirmed [invariant, e.g. "single-wave path byte-for-byte unchanged"] — cite the diff hunk.
  [ ] 4. Checked each disclosed residual (below) — for each, state blocker? yes/no + why.
  [ ] 5. [any review-specific must-do]

DISCLOSED RESIDUALS (I already know about these — judge whether any is a NO-GO):
  - [residual 1]
  - [residual 2]

RETURN EXACTLY THIS FORMAT (nothing that stalls; no preamble):
  Line 1: `VERDICT: GO`  or  `VERDICT: NO-GO`
  Then a table — one row per review item / deliverable:
    | Item | OK? (RESOLVED/ISSUE) | File:section checked | One-sentence evidence |
  Then: `RESIDUALS: none block` or `RESIDUALS: <key> blocks because <reason>`.
  Then the DoD checklist above, each box checked with its pasted result.
  If NO-GO, ALSO append a ready-to-paste Claude Code fix handoff, EXACTLY:
    ----- CLAUDE CODE HANDOFF -----
    Work in /Users/alejandroguillen/Projects/[REPO]
    Branch: [BRANCH]
    Live HEAD: <the tip sha you reviewed>
    Fix these NO-GO findings in order (each: file, exact change, why):
      1. ...
      2. ...
    Definition of done: <what must be true + which test/grep proves each fix>.
    After fixing: run <commands>, then do a second self-review and report residual risks.
    -------------------------------

DO NOT:
  - ask which commit/branch/scope (it is the tip of [BRANCH]);
  - propose or write code unless the verdict is NO-GO (then only in the handoff block);
  - return prose without the VERDICT line and the table;
  - stall for input — if a file you expect is missing, name it and treat it as a NO-GO reason.
```

## (end skeleton)

---

## Return-acceptance checklist (validate Codex's reply BEFORE acting)

Reject the review and re-send if ANY is false:
- [ ] Line 1 is exactly `VERDICT: GO` or `VERDICT: NO-GO`.
- [ ] Every review item / deliverable has a table row with a File:section and evidence.
- [ ] The DoD boxes are all checked AND show pasted command output (not "looks fine").
- [ ] Each disclosed residual has an explicit blocker? yes/no + reason.
- [ ] If NO-GO, a `----- CLAUDE CODE HANDOFF -----` block is present, leads with
      `Work in …`, and lists ordered fixes with a definition of done.
