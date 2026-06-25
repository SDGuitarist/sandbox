# Codex Re-Review Handoff #3 — G1 Firebreak Phase 1 (post-convergence)

**Date:** 2026-06-24
**Repo:** `~/Projects/sandbox` · **Branch:** `feat/g1-risk-tiered-firebreak` (pushed)
**Range to review:** `ed54159..883f5cf` (HEAD **`883f5cf`**). Substantive code commits: `89e2439` (F15 + F16 red-team convergence), `959b03a` (**F16b dispatcher-skip fix**), and `883f5cf` (**F16b pre-activation hardening** — enumerated the adjacent install/build-dest flags + `git config -f`/`--file` + `git clone <CP-dir>`).
**Prior state:** your last re-review covered through `ed54159` (8th pass). Since then: the **9th pass (F15)**, a **6-round adversarial red-team (F16)** that drove the classifier to a dry round, **F16b** which closed the one structural seam the red-team's own watch-item had flagged, and a **pre-activation self-review** that enumerated the adjacent dispatcher output flags.

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

### F16b — dispatcher-skip fix (commit `959b03a`, closes the F16 watch-item's CP half)
The F16 structural backstop **exempts** listed `DISPATCHERS` (so a benign positional
like `git add .claude/hooks` — staging, not a write — stays GREEN). That exemption
left a hole: a listed dispatcher could still WRITE the control plane through a
**local-output flag/subcommand** that is neither outward (push/deploy, caught by
`bash_outward`) nor a `CP_WRITE` verb. A pre-fix probe found **8/10 vectors ALLOWED**:
`go build -o .claude/hooks/firebreak-classify.py`, `git archive --output=.claude/hooks/x`,
`git bundle create .claude/hooks/x`, `docker cp src .claude/hooks/x`, `npm pack
--pack-destination .claude/hooks`, `pip download -d .claude/hooks`.

**Fix:** a **dispatcher local-write backstop** in `bash_control_plane`, AFTER the
dispatcher-specific (git working-tree, `git_local_category`) handling. For a worker,
any control-plane path delivered through a conventional output flag
(`DISPATCHER_OUTPUT_FLAGS`: `-o`/`--output`/`--output-dir`/`-O`/`-d`/`--dest`/
`--pack-destination`/… incl. glued `-o<path>` and `--flag=`) or a known
positional-write subcommand (`DISPATCHER_POSITIONAL_WRITES`: `git bundle create`,
`docker|podman|nerdctl cp`) fails closed. Reuses `cp_normalize`+`expand_assigns`+
`_cp_path_protected`+`worker_cp_obfuscation_risk`, so ANSI-C/case-fold/`${VAR:=default}`/
`git -C`-normalized variants also defer.

**Scrutinize (P0/P1):** (a) over-defer — confirm worktree outputs (`go build -o
build/app`), benign flag uses (`docker build -t tag`, `docker run -t`, `kubectl get
-o yaml`, `git config -f .gitconfig.local`), and dispatcher READ positionals (`git
add`/`git log`/`git diff` of a `.claude` path) stay GREEN; (b) the residual.

**Pre-activation hardening (`883f5cf`) — the F16b watch-item seeds are now CLOSED.**
The self-review enumerated `DISPATCHER_OUTPUT_FLAGS += --root/--prefix/-w/--wheel-dir/
-out/-t/--target/--target-dir/--out-dir/--modules-folder/--cache/--cache-dir/
--cache-folder` (covers `cargo install --root`, `pip wheel -w/--wheel-dir`,
`terraform plan -out=`, `npm install --prefix`, `pip install --target/-t`, `cargo
build --target-dir`, `yarn --modules-folder`); added `git config -f`/`--file <CP>` to
`git_local_category`; and added `git clone <CP-dir>` to `DISPATCHER_POSITIONAL_WRITES`.
Already-covered (verify): `git checkout-index --prefix` (the `-a`/`-f` branch),
`terraform apply -state-out` (apply = deploy), `go test -o`, `docker save -o`.
Being liberal with the flag set is SAFE because a flag value defers ONLY when
`_cp_path_protected` says it IS a control-plane path.

**Remaining declared residual (rule on it):** a control-plane path embedded inside a
STRUCTURED flag value the extractor sees as one opaque token — notably the BuildKit
exporter `docker build -o type=local,dest=.claude/hooks` (the dest sits inside a
comma-list). Accept as a v1 watch-item, or split `dest=`/`output=` sub-keys now?

### False positives fixed (these run unattended — must NOT halt)
`cp`/`ln`/`install` read-SOURCES outside the worktree (only DEST is a write target,
`_cp_dest`); integer-encoded **loopback** IPs decoded+allowed; `nc -z localhost`;
`find . -name '*.pyc' -delete` (filtered ≠ whole-tree); the backstop uses
IS/inside-CP (not ancestor) so `eslint .`/`pytest $F`/`curl -o build/x` stay GREEN.

## Re-review focus (adversarial; P0/P1/P2 with exact file:line)

1. **Backstop correctness** — can a worker still mutate the control plane? Probe (a)
   an UNRECOGNIZED verb with a CP path delivered by a form `_arg_path_candidates`
   misses; (b) a writer wrongly sitting in `READ_ONLY_VERBS`; (c) a LISTED dispatcher
   (F16b) writing CP via an output flag NOT in `DISPATCHER_OUTPUT_FLAGS` or a
   positional-write subcommand NOT in `DISPATCHER_POSITIONAL_WRITES` — the seeds
   (cargo/pip/terraform/npm/yarn + `git config -f` + `git clone`) are now closed by
   `883f5cf`, so aim at what's left: a STRUCTURED flag value (`docker build -o
   type=local,dest=<CP>`) or a dispatcher output flag none of us has named yet.
2. **False positives** — the fail-closed posture is aggressive. Find a BENIGN
   unattended-build command now wrongly DENIED (beyond the by-design defers:
   inherited/opaque-var delete targets, `make`/`npm run` indirection, `git apply`).
3. **Residual honesty** — #1 interpreter escape; #2 inherited-OR-opaque-RHS **redirect**
   target (delete/mutation now fail closed); #3 unlisted OUTWARD binary exfiltrating a
   NON-control-plane file (the control-plane half is now closed for BOTH unrecognized
   verbs AND listed-dispatcher local-output writes — F16/F16b + `883f5cf` hardening);
   the one remaining dispatcher seam = a path in a STRUCTURED flag value (`docker
   build -o type=local,dest=<CP>`); additive-new-file-inside-`.claude/hooks/`
   carve-out. Are these stated correctly?
4. **The `DISPATCHERS` watch-item (narrowed by F16b + `883f5cf`)** — adding a binary
   to `DISPATCHERS` no longer silently removes CP coverage for its conventional
   local-output writes (the common install/build-dest flags are now enumerated); the
   remaining seam is a STRUCTURED-value-embedded path or a not-yet-named output flag.
   Acceptable documented residual for v1, or split `dest=`/`output=` sub-keys now?
5. **Superset invariant** holds for every new denial (gate forwards it)?
6. Anything that should still **block activation** (global hook wiring + orchestrator
   integration), which remains OUT OF SCOPE for this review.

## Run the tests (baseline to confirm)

```
python3 .claude/hooks/test_firebreak_classify.py     # 235/235
python3 .claude/hooks/test_firebreak_gate.py         # 26/26
python3 .claude/hooks/test_firebreak_superset.py     # 287 cases, 0 gaps
python3 .claude/hooks/test_firebreak_soundness.py    # 303 RED + 120 GREEN
```

If clean, return GO (or GO-WITH-RESIDUALS naming the accepted residuals). Otherwise
return findings as P0/P1/P2 with exact file:line to change.
