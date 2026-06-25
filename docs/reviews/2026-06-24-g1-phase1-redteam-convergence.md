---
title: "G1 Phase 1 — adversarial red-team convergence (rounds 1–6): structural hardening to a dry round"
date: 2026-06-24
type: review
branch: feat/g1-risk-tiered-firebreak
verdict: GO-WITH-RESIDUALS (converged; 1 dry red-team round at ~90% confidence)
focus: "Multi-round parallel adversarial red-team of the classifier across every attack surface, fixing whole CLASSES not cases"
---

# G1 Phase 1 — Red-Team Convergence (Rounds 1–6)

After the 9th review (same-command assignment mechanisms), the question was: *is the
next Codex pass actually a GO?* The honest answer was no. Each prior NO-GO had the
same shape — a narrow fix to the cited case, leaving the adjacent bypass alive. So
instead of another narrow patch, I ran **six rounds of parallel adversarial
red-teaming** (≈15 subagents), each attacking a distinct surface and **executing
real probes against the live classifier**, fixing whole classes until a round came
back dry.

## Method

A shared probe harness (`/tmp/fbprobe.py`) runs the real classifier as an untrusted
worker. Each round fanned out independent red-teamers (variable resolution, path
obfuscation, verb/wrapper opacity, structural/git, redirects, outward/MCP, false
positives, backstop-defeat). Findings were verified, fixed at the **class** level,
test-locked into all four corpora, then the next round attacked the fixes.

## New-bypass find-rate per round (the convergence signal)

| Round | Confirmed NEW bypass classes | Theme |
|------:|------------------------------|-------|
| 1 | ~21 | var-expansion, path-obfuscation, wrapper-eating, git, redirects, outward/MCP |
| 2 | ~15 | ANSI-C hex/octal, wrapper value-flags, glued dest-flags, read-tree, FPs |
| 3 | ~12 | trap/PROMPT_COMMAND, ln hardlink, socat/dig/docker, rename, infra CLIs |
| 4 | ~9  | rsync-to-CP, busybox/vim/patch (→ **structural backstop**), exfil tools |
| 5 | 1   | curl `-o` output-path to CP via loopback (→ flag-value backstop) |
| 6 | **0** | **NONE FOUND — converged** |

## Class-level fixes (not an exhaustive case list)

- **Path normalization (`cp_normalize`)** — decode ANSI-C `$'\xNN'`/`\NNN`/`\uNNNN`,
  strip backslash-escapes + quotes, **case-insensitive** `.claude` match (macOS FS).
  Kills `.cla""ude/hooks`, `.claude/hoo\ks`, `$'\x2e\x63laude'`, `.Claude/hooks`.
- **Same-command variable resolution + concrete-prefix fail-closed** — arrays
  `${a[0]}`, indirect `${!n}`, substring `${x:2}`, pattern-sub `${x/a/b}`, `read -a`,
  `printf -v %s`, and any unresolved `$VAR`/`$(...)`/glob in a delete/mutation target
  fail closed unless a **concrete safe worktree prefix** bounds them. (Replaces the
  per-syntax whack-a-mole; `build/*`/`*.pyc`/`{build,dist}` stay GREEN.)
- **Wrapper verb-eating** — `nice/ionice/stdbuf/watch/parallel` no longer swallow the
  command word; per-wrapper value-flags (`nice -n 5`) are skipped; `time -p` handled;
  `env -S` recursed; `xargs <verb>` + CP literal / outward defers.
- **Git working-tree destruction** — `git rm/clean/checkout/restore/switch/reset
  --hard/stash -u/mv/worktree/read-tree/checkout-index/config core.hooksPath/apply/am`.
- **Write-destination flags** — `dd of=`, `sort -o`, `tar -C`, `unzip -d` (glued),
  `rsync DEST` (always, not only `--delete`), `ditto/cpio/pax`, and **curl/wget
  `-o`/`-O`/`--output`** output paths (control-plane AND worktree-escape).
- **Redirect operators** — `>|`, `>&`, `1>|`, `2>|`, `&>|` (target hidden behind `|`/`&`).
- **Command-carrying contexts** — `trap '<cmd>' SIG` and `PROMPT_COMMAND='<cmd>'`
  are classified as the commands they execute.
- **Alias-to-hook** — `ln`/`cp --link`/`--symbolic-link` with a control-plane SOURCE.
- **Outward / deploy / package coverage** — integer-encoded IP hosts (loopback
  carve-out preserved), `nc` loopback carve-out, `socat`/`dig`/`host`/`nslookup`/
  `rclone`/`mc`/`s3cmd`/`mail`/`glab`; `docker/podman push` + `run --mount`; `helm/
  pulumi/serverless/cdk/ansible/nomad/argocd/skaffold/flux/doctl`; `uv`/`pipx`/`cargo`/
  `gem`/`brew`/`apt` uninstall, `yarn workspace … publish`; extended MCP mutating tokens.
- **STRUCTURAL BACKSTOP (the convergence move)** — any **UNRECOGNIZED** verb (not a
  known reader/write-verb/dispatcher/wrapper/interpreter) that names a control-plane
  path **as a positional OR flag-value OR `name=value`** fails closed. This is what
  ends the enumerate-every-binary game: `busybox rm`, `vim -es`, `patch`, `sponge`,
  `gio`, and *future* tools defer without being individually modeled. A genuine
  reader (`cat .claude/...`) is allowlisted (`READ_ONLY_VERBS`).

## False positives fixed (unattended builds must not halt)

`cp`/`ln`/`install` read-SOURCES outside the worktree (only the DEST is a write
target); integer-encoded **loopback** IPs decoded and allowed; `nc -z localhost`
loopback carve-out; `find . -name '*.pyc' -delete` (filtered, not whole-tree);
the backstop uses an IS/inside-CP check (not the ancestor check), so `eslint .` and
`pytest $F` stay GREEN; benign `rsync`/`dd`/`tar`/`curl -o` to worktree artifacts.

## Declared residuals (honest, bounded)

- **#1 interpreter escape** (`python -c`, allowlisted-test-runner body) — unchanged.
- **#2 not-statically-resolvable value** — a genuinely-inherited `$VAR` OR opaque
  `$(...)` **redirect** target (`> $out`) stays GREEN to preserve computed-artifact
  writes. (Delete/mutation targets now fail closed — no longer residual there.)
- **#3 enumerated dispatcher/outward** — an UNLISTED dispatcher or network/exfil
  binary with a literal `argv0` exfiltrating a NON-control-plane file. The backstop
  closes the control-plane half; arbitrary-secret exfil over an unmodeled net tool
  is the residual (analogous to the F13 set-enumeration leak).
- **Additive carve-out** — a NEW non-`firebreak-*` file created INSIDE `.claude/hooks/`
  (`rsync evil .claude/hooks/newfile`) is allowed; it cannot overwrite/disable a
  protected hook or the realpath-protected global `~/.claude/settings.json`.
- **Watch-item (round-6 note):** adding a binary to `DISPATCHERS` removes it from
  backstop coverage — dispatcher additions are the highest-leverage place a future
  regression could hide. Re-run the red-team after any `DISPATCHERS` change.

## Test totals (all green)

| Suite | 9th review | After convergence |
|-------|-----------|-------------------|
| classifier unit | 188/188 | **203/203** |
| gate | 26/26 | **26/26** |
| superset | 205 / 0-gaps | **274 / 0-gaps** |
| soundness | 162 RED + 58 GREEN | **270 RED + 94 GREEN** |

## Verdict

GO-WITH-RESIDUALS. Six adversarial rounds drove the new-bypass rate to zero; the
final round found nothing at ~90% confidence. The fixes are class-level and
test-locked; both invariants (superset, soundness) hold across the enlarged corpora;
benign unattended-build activity stays GREEN. No reviewer's verdict can be
*guaranteed*, but the surface Codex has been probing is now closed by construction
(the backstop), not by enumeration. Activation remains out of scope.

Test totals: classifier 203/203, gate 26/26, superset 274/0-gaps, soundness 270 RED + 94 GREEN.
