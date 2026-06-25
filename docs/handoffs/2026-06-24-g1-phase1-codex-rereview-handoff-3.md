# Codex Re-Review Handoff #3 — G1 Firebreak Phase 1 (post-convergence)

**Date:** 2026-06-24
**Repo:** `~/Projects/sandbox` · **Branch:** `feat/g1-risk-tiered-firebreak` (pushed)
**Range to review:** `ed54159..89e2439` (HEAD **`89e2439`**). The substantive change is the single commit `89e2439`.
**Prior state:** your last re-review covered through `ed54159` (8th pass). Since then: the **9th pass (F15)** and a **6-round adversarial red-team (F16)** that drove the classifier to a dry round.

## What changed since `ed54159`

### 9th pass — F15 (same-command assignment mechanisms)
`collect_assignments`/`expand_assigns` now resolve every statically-visible
same-command form beyond bare `VAR=`/`export`/`declare`: the here-string `read [opts]
VAR <<< .claude/hooks`, `printf -v VAR` (literal or `%s`-arg), the in-place default
`${D:=.claude/hooks}`/`${D:-…}`/`${D=…}`, and **flagged** keyword assignments
(`declare -g`, `local -r`, `export --`). An **opaque** same-command RHS
(`D=$(echo .claude/hooks)`) is **decided as residual #2** (not statically resolvable;
consistent with the already-accepted direct `rm -rf $(echo .claude/hooks)`) — **not**
mislabeled "inherited". See `docs/reviews/2026-06-24-g1-phase1-ninth-review.md`.

### Red-team convergence — F16 (rounds 1–6; ~15 subagents on the live classifier)
New-bypass find-rate per round: **21 → 15 → 12 → 9 → 1 → 0** (round 6 dry, ~90%
confidence). Fixed at the CLASS level, all test-locked. Full writeup:
`docs/reviews/2026-06-24-g1-phase1-redteam-convergence.md`. The fixes:

| Area | What to verify |
|------|----------------|
| **STRUCTURAL BACKSTOP** (the convergence move) | `bash_control_plane` tail: any **unrecognized** `argv0` (not in `READ_ONLY_VERBS` / `CP_WRITE_VERBS` / `DELETE_VERBS` / `DISPATCHERS` / `WRAPPERS` / `INTERPRETERS` / `find`) that names a control-plane path as a **positional OR flag-value OR `name=value`** (`_arg_path_candidates`) fails closed via `_cp_path_protected` (IS/inside the CP — **not** a mere ancestor like `.`/`~`). Catches `busybox rm`, `vim -es`, `patch`, `sponge`, `gio`, future tools. **Scrutinize:** is the `READ_ONLY_VERBS` allowlist safe (no writer hiding in it)? Does `_cp_path_protected` correctly EXCLUDE ancestors so `eslint .`/`pytest $F` stay GREEN? |
| **Path normalization** | `cp_normalize` decodes ANSI-C `$'\xNN'`/octal/`\uNNNN` (`_ansi_c_decode`), strips backslash-escapes + quotes; `is_control_plane`/`is_control_plane_dir` are **case-insensitive** (macOS FS). |
| **Concrete-prefix fail-closed** | `worker_cp_obfuscation_risk` — an unresolved `$VAR`/array `${a[0]}`/indirect `${!n}`/substring `${x:2}`/pattern-sub/`$(...)`/dot-glob in a delete/mutation target defers unless a **safe concrete worktree prefix** bounds it. `expand_assigns` keeps unhandled `${...}` operators OPAQUE (returns literal) so they fail closed. Verify `build/*`, `*.pyc`, `{build,dist}` stay GREEN. |
| **Wrapper verb-eating** | `WRAPPER_TAKES_ARG` trimmed (nice/ionice/stdbuf/watch/parallel removed), `WRAPPER_FLAG_VALUES` skips per-wrapper value-flags (`nice -n 5`), `_wrapper_value_ok` guards, `time` moved keyword→wrapper (`-p`), `env -S` recursed, `_xargs_risk`. |
| **Git working-tree destruction** | `git_local_category` — rm/clean/checkout/restore/switch/reset --hard/stash -u/mv/worktree/read-tree --reset/checkout-index/config core.hooksPath/apply/am, control-plane-scoped (trusted unaffected, F5). |
| **Write-dest flags** | `_write_dest_targets` — `dd of=`, `sort -o`, `tar -C`, `unzip -d` (glued), `rsync DEST` (ALWAYS, not only `--delete`), `ditto/cpio/pax`, **curl/wget `-o`/`-O`/`--output`** (all forms); `dest_targets` now also get the worktree-escape check. |
| **Redirects** | `redirection_targets` regex catches `>|`, `>&`, `1>|`, `2>|`, `&>|`. |
| **Command-carrying contexts** | `extract_nested_commands` classifies `trap '<cmd>' SIG` handlers and `PROMPT_COMMAND='<cmd>'`. |
| **Alias-to-hook** | `ln`/`cp --link`/`--symbolic-link` with a control-plane SOURCE (`cp_src` checked). |
| **Outward / deploy / package** | integer-encoded IP hosts (`_decode_int_ip`, loopback carve-out preserved), `nc` loopback carve-out, socat/dig/host/nslookup/rclone/mc/s3cmd/mail/glab, docker/podman push + run--mount, helm/pulumi/serverless/cdk/ansible/nomad/argocd/skaffold/flux/doctl, uv/pipx/cargo/gem/brew/apt uninstall, `yarn workspace … publish` (`_pm_effective_verb`), extended `MCP_MUTATING_TOKENS`. |
| **Gate markers** | `firebreak-gate.sh` got markers for the new denials (git clean/reset/hooksPath/checkout/…, helm/pulumi/serverless/socat/dig/docker/rclone/mail/busybox/vim/…). Superset proves 0 gaps. |

### False positives fixed (these run unattended — must NOT halt)
`cp`/`ln`/`install` read-SOURCES outside the worktree (only DEST is a write target,
`_cp_dest`); integer-encoded **loopback** IPs decoded+allowed; `nc -z localhost`;
`find . -name '*.pyc' -delete` (filtered ≠ whole-tree); the backstop uses
IS/inside-CP (not ancestor) so `eslint .`/`pytest $F`/`curl -o build/x` stay GREEN.

## Re-review focus (adversarial; P0/P1/P2 with exact file:line)

1. **Backstop correctness** — can a worker still mutate the control plane with an
   unrecognized verb? Probe a CP path delivered by a form `_arg_path_candidates`
   misses; a writer wrongly sitting in `READ_ONLY_VERBS`; a verb that's in
   `DISPATCHERS` (→ skips the backstop) but writes CP via an unmodeled flag.
2. **False positives** — the fail-closed posture is aggressive. Find a BENIGN
   unattended-build command now wrongly DENIED (beyond the by-design defers:
   inherited/opaque-var delete targets, `make`/`npm run` indirection, `git apply`).
3. **Residual honesty** — #1 interpreter escape; #2 inherited-OR-opaque-RHS **redirect**
   target (delete/mutation now fail closed); #3 unlisted OUTWARD binary exfiltrating a
   NON-control-plane file (the control-plane half is closed by the backstop);
   additive-new-file-inside-`.claude/hooks/` carve-out. Are these stated correctly?
4. **The `DISPATCHERS` watch-item** — adding a binary to `DISPATCHERS` removes it from
   backstop coverage. Is that an acceptable documented seam?
5. **Superset invariant** holds for every new denial (gate forwards it)?
6. Anything that should still **block activation** (global hook wiring + orchestrator
   integration), which remains OUT OF SCOPE for this review.

## Run the tests (baseline to confirm)

```
python3 .claude/hooks/test_firebreak_classify.py     # 203/203
python3 .claude/hooks/test_firebreak_gate.py         # 26/26
python3 .claude/hooks/test_firebreak_superset.py     # 274 cases, 0 gaps
python3 .claude/hooks/test_firebreak_soundness.py    # 270 RED + 94 GREEN
```

If clean, return GO (or GO-WITH-RESIDUALS naming the accepted residuals). Otherwise
return findings as P0/P1/P2 with exact file:line to change.
