---
title: "G1 Phase 1 — ninth review: same-command assignment-mechanism sweep (F15) + opaque-RHS residual decision"
date: 2026-06-24
type: review
branch: feat/g1-risk-tiered-firebreak
verdict: GO-WITH-RESIDUALS (declared; residual #2 reworded — non-resolvable value)
focus: "F14 same-command resolution missed assignment mechanisms beyond VAR= / export / declare"
---

# G1 Phase 1 — Ninth Review

The 8th pass (F14) resolved same-command variable targets, but only for the
`VAR=value` / `export` / `declare` / `typeset` / `local` *bare* forms. Codex's
re-review #2 found that **other same-command mechanisms that produce a
statically-visible value still hid a control-plane target** — classified **allow**:

```
read D <<< .claude/hooks; rm -rf $D          printf -v D .claude/hooks; rm -rf $D
rm -rf ${D:=.claude/hooks}                   chmod 000 ${D:=.claude/hooks}
rmdir ${D:=.claude/hooks}                    unlink ${F:=.claude/hooks/firebreak-gate.sh}
shred ${F:=.claude/hooks/firebreak-gate.sh}  echo x > ${F:=$HOME/.claude/settings.json}
```

Self-review during this pass found two more (same root cause), also closed:

```
declare -g D=.claude/hooks; rm -rf $D        printf -v D %s .claude/hooks; rm -rf $D
local -r D=.claude/hooks; rm -rf $D          export -- D=.claude/hooks; rm -rf $D
```

## Fix (F15)

1. **`collect_assignments` — new mechanisms.** Besides the bare/`export`/`declare`
   forms it now records:
   - **here-string read** `read [opts] VAR <<< value` (single var only — a multi-var
     read splits on IFS and is not statically resolvable);
   - **`printf -v VAR FORMAT [ARG]`** — the literal FORMAT when it has no `%`
     conversion, or the single ARG when FORMAT is exactly `%s`;
   - **flagged keyword assignments** — `declare`/`export`/`typeset`/`local` now scan
     past their own flags (`declare -g`, `local -r`, `export --`) to the first
     `VAR=value` token, instead of requiring the assignment at a fixed position.
   A shared `record(name, raw)` helper dequotes, expands earlier same-command vars +
   `~`/`$HOME`, and **skips an opaque RHS** (so we never fabricate a value).
2. **`expand_assigns` — in-place default expansion.** `${VAR:=word}` / `${VAR:-word}`
   / `${VAR=word}` / `${VAR-word}` now resolve to the statically-visible default
   `word` when `VAR` is not a known same-command assign (a known value wins). So
   `rm -rf ${D:=.claude/hooks}` and `echo x > ${F:=$HOME/.claude/settings.json}`
   expose their literal target. A bare `${VAR}` or an alternate operator
   (`${VAR:+word}`, `${VAR#…}`, `${VAR/…}`) with an unknown `VAR` stays literal/opaque.

## The opaque-RHS decision (residual #2 reworded — NOT a new fail-closed)

Codex asked us to decide & document `D=$(echo .claude/hooks); rm -rf $D` — a
**same-command** assignment whose RHS is a command substitution. **Decision: it
stays GREEN as the declared residual #2**, on these grounds:

- It is **not statically resolvable.** A static classifier cannot execute
  `$(echo .claude/hooks)`; the value is genuinely invisible — the *same epistemic
  state* as a truly-inherited `$VAR`.
- It is the **same already-accepted residual** as the **direct** form
  `rm -rf $(echo .claude/hooks)`, which is **GREEN today** and was **not** on
  Codex's must-fix list. Resolving the variable-wrapped form while leaving the
  direct form GREEN would be **inconsistent**, not safer.
- The control plane is **already** disableable by a worker via residual #1 (an
  allowlisted interpreter runs arbitrary code: `python -c "shutil.rmtree('.claude/hooks')"`).
  Closing only the command-substitution path buys nothing against a determined worker.

What this review **refuses to do** is repeat the 7th-pass error of calling it
"inherited." It is a **same-command opaque RHS**, explicitly named as such.

**Residual #2 reworded:** "a target/redirect whose value is **NOT statically
resolvable** — a **genuinely-inherited** `$VAR` (no assignment in this command) OR
an **opaque same-command RHS** (`$(…)`/backtick)." Statically-resolvable
same-command assignments are resolved and checked. Residuals #1 (interpreter
escape) and #3 (unlisted dispatcher/wrapper) unchanged.

| Form | Example | Disposition |
|------|---------|-------------|
| read here-string | `read D <<< .claude/hooks; rm -rf $D` | **DENY** (F15) |
| printf -v (literal / `%s`) | `printf -v D .claude/hooks; rm -rf $D` | **DENY** (F15) |
| default expansion | `rm -rf ${D:=.claude/hooks}` | **DENY** (F15) |
| default expansion redirect | `echo x > ${F:=$HOME/.claude/settings.json}` | **DENY** (F15) |
| flagged keyword | `declare -g D=.claude/hooks; rm -rf $D` | **DENY** (F15) |
| opaque same-cmd RHS | `D=$(echo .claude/hooks); rm -rf $D` | **GREEN — residual #2** |
| direct `$(…)` target | `rm -rf $(echo .claude/hooks)` | **GREEN — residual #2** |
| genuinely inherited | `rm -rf $INHERITED_CP_VAR` | **GREEN — residual #2** |

## Over-defer guard (no false positives)

Benign forms stay GREEN: `read D <<< build; rm -rf $D`, `printf -v D %s build; rm
-rf $D`, `rm -rf ${D:=build}`, `echo hi > ${O:=out.txt}`, `rm -rf
${D:=.claude/worktrees/x}`, `declare -g D=build; rm -rf $D`, `local -r D=dist;
rmdir $D`. (A `${D:=build}` with `D` already same-command-assigned uses the known
value, not the default.)

## Remaining not-yet-resolved same-command forms (declared, within residual #2)

Treated opaque (left GREEN) and named honestly: multi-var `read A B <<<`,
`mapfile`/`readarray`, rich `printf` `%`-formats (beyond `%s`), and alternate
parameter operators (`${VAR:+word}`, `${VAR#…}`, `${VAR/…}`). None is statically
resolvable without a fuller shell evaluator; they share residual #2's epistemic
limit.

## Superset invariant

Every new denial carries the literal control-plane string (`.claude` /
`settings.json`) in the command — that's *why* the value is statically resolvable —
so the gate's existing markers forward each one. Superset test confirms 0 gaps.

## Test-count reconciliation

| Suite | 8th review | 9th review (this pass) |
|-------|-----------|------------------------|
| classifier unit | 175/175 | **188/188** |
| gate | 26/26 | **26/26** |
| superset | 197 / 0-gaps | **205 / 0-gaps** |
| soundness | 147 RED + 58 GREEN | **162 RED + 68 GREEN** |

## Verdict

GO-WITH-RESIDUALS. All statically-resolvable same-command assignment mechanisms
(here-string read, printf -v incl. `%s`, `${VAR:=default}` in-place, flagged
keyword assignments) now defer for workers; the opaque same-command RHS is decided
and documented as the same (non-resolvable-value) residual #2 as the direct `$(…)`
form — **not** mislabeled inherited; benign variants stay GREEN; both invariants
hold across the enlarged corpora. Activation remains out of scope.

Test totals: classifier 188/188, gate 26/26, superset 205/0-gaps, soundness 162 RED + 68 GREEN.
