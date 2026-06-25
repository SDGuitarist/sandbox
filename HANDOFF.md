# HANDOFF — Sandbox

**Date:** 2026-06-24
**Branch:** `feat/g1-risk-tiered-firebreak` (working tree clean; HEAD **`883f5cf`** — **PUSHED, in sync with `origin`**)
**Phase:** **G1 risk-tiered firebreak — Plan GO ✅ → Step 0 PASS ✅ → Phase 1 CORE built + tested + HARDENED + RED-TEAM CONVERGED + F16b dispatcher-skip CLOSED + F16b pre-activation hardening ✅ (9 review passes + a 6-round parallel adversarial red-team; new-bypass rate 21→15→12→9→1→0, final round DRY; then F16b closed the watch-item's CP half; then a self-review enumerated the adjacent install/build-dest flags). Checkpointed for Codex re-review BEFORE activation.**
Latest commit **`883f5cf`** (F16b pre-activation hardening). Plan: `docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md`. Step 0: `docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md`. Reviews: 2nd–9th in `docs/reviews/` + **`docs/reviews/2026-06-24-g1-phase1-redteam-convergence.md`** (the 6-round sweep + the F16b follow-up).

**RED-TEAM CONVERGENCE (rounds 1–6, ~15 subagents executing real probes):** after the 9th pass I ran six rounds of parallel adversarial red-teaming and fixed whole CLASSES, not cases. Found+fixed ~58 bypasses across every surface. The convergence move = a **STRUCTURAL BACKSTOP**: any UNRECOGNIZED verb (not a known reader/write-verb/dispatcher/wrapper/interpreter) naming a control-plane path as a positional OR flag-value OR `name=value` fails closed — so `busybox rm`/`vim -es`/`patch`/`sponge`/future tools defer without enumeration (`READ_ONLY_VERBS` allowlists genuine readers). Other class fixes: ANSI-C hex/octal + case-insensitive path normalization; concrete-prefix fail-closed for all var/array/substring/pattern/`$()` delete targets; wrapper verb-eating (`nice -n 5 rm`); git working-tree destruction (rm/clean/checkout/restore/reset/stash/read-tree/apply/config-hooksPath); curl/wget `-o` output paths; redirect ops `>|`/`>&`; `trap`/`PROMPT_COMMAND` command execution; `ln` hardlink-to-hook; integer-IP hosts + nc/loopback carve-outs; socat/dig/docker/rclone/infra-CLI/uv/pipx coverage; extended MCP tokens. FPs fixed so unattended builds don't halt (cp/ln read-sources, loopback IPs, `find . -name '*.pyc' -delete`, `eslint .`, `pytest $F`). Round 6 = DRY (~90% confidence). **F16b follow-up (commit `959b03a`):** the structural backstop EXEMPTS listed `DISPATCHERS`, leaving a listed dispatcher able to write the CP via a **local-output flag/subcommand** (`go build -o .claude/hooks/…`, `git archive --output=`, `git bundle create`, `docker cp`, `npm pack --pack-destination`, `pip download -d` — 8/10 probed vectors ALLOWED pre-fix). Closed by a **dispatcher local-write backstop** (`DISPATCHER_OUTPUT_FLAGS` + `DISPATCHER_POSITIONAL_WRITES`) after the dispatcher-specific handling; benign worktree outputs + READ positionals (`git add`/`log`/`diff`) stay GREEN. **F16b pre-activation hardening (commit `883f5cf`):** a second self-review swept all 20 dispatchers and enumerated the adjacent install/build-dest flags — `DISPATCHER_OUTPUT_FLAGS += --root/--prefix/-w/--wheel-dir/-out/-t/--target/--target-dir/--out-dir/--modules-folder/--cache/--cache-dir/--cache-folder` (cargo install --root, pip wheel -w, terraform plan -out, npm install --prefix, pip install --target/-t, cargo build --target-dir, yarn --modules-folder); `git config -f`/`--file <CP>` denied in `git_local_category`; `git clone <CP-dir>` added to `DISPATCHER_POSITIONAL_WRITES`. Liberal-but-safe (a flag value defers ONLY when it resolves to a CP path). **Remaining declared residual:** a path embedded in a STRUCTURED flag value (`docker build -o type=local,dest=<CP>`). **Totals now: classifier 235/235, gate 26/26, superset 287/0-gaps, soundness 303 RED + 120 GREEN.**

**⏭ NEXT SESSION — resume here:** Branch `feat/g1-risk-tiered-firebreak`, HEAD **`883f5cf`** — **PUSHED, in sync with `origin`.** **Codex re-review #3 is OUT** — the user pasted `docs/handoffs/2026-06-24-g1-phase1-codex-rereview-handoff-3.md` (range **`ed54159..883f5cf`**, totals 235/26/287/303+120) into Codex and is bringing the verdict back. The one open question posed to Codex: accept the remaining structured-value residual (`docker build -o type=local,dest=<CP>`) as a v1 watch-item, or split `dest=`/`output=` sub-keys now. **When Codex's verdict returns:** (a) **GO / GO-WITH-RESIDUALS** → proceed to the **activation layer** (the 3 "Phase 1 REMAINING" items below: global hook wiring + orchestrator integration + positive-control real-spawn probe) — but DO NOT start activation without the user's explicit go-ahead (it's a global `~/.claude/settings.json` change). (b) **NO-GO** → fix per the established loop (read the cited file:line, fix the CLASS not the case per `docs/solutions/2026-06-24-enumerated-denylist-vs-structural-backstop.md`, re-run all four tests, add cases to corpora, update review/HANDOFF/plan). Lesson from the 9-pass saga is captured in that solution doc + memory `feedback_enumerated-denylist-vs-structural-backstop`.

**9th pass (same-command assignment-mechanism sweep — Codex re-review #2):** F14 resolved only `VAR=`/`export`/`declare`-bare assignments, so other same-command mechanisms still hid a control-plane target. Fix (F15): `collect_assignments` now also records the here-string `read [opts] VAR <<< .claude/hooks`, `printf -v VAR` (literal or `%s`-arg), and **flagged** keyword assignments (`declare -g`, `local -r`, `export --`); `expand_assigns` now resolves the in-place default `${D:=.claude/hooks}` / `${D:-…}` / `${D=…}` (incl. `$HOME`-rooted redirect `echo x > ${F:=$HOME/.claude/settings.json}`). **Opaque same-command RHS decided:** `D=$(echo .claude/hooks); rm -rf $D` stays GREEN as the **same already-accepted residual #2** as the direct `rm -rf $(echo .claude/hooks)` (not statically resolvable) — explicitly **NOT** relabeled "inherited" (the 7th-pass error). **Residual #2 reworded:** "a NON-statically-resolvable value (truly-inherited OR opaque-RHS)." Benign forms (`read D <<< build`, `rm -rf ${D:=build}`, `declare -g D=build`) stay GREEN. **Totals now: classifier 188/188, gate 26/26, superset 205/0-gaps, soundness 162 RED + 68 GREEN.**

**8th pass (same-command variable target bypass):** the 7th review wrongly called `D=.claude/hooks; rm -rf $D` an "inherited-`$VAR`" and let it through — but the assignment is in the SAME Bash command, so it's statically resolvable. Fix (F14): `collect_assignments` + `expand_assigns` resolve same-command vars (standalone / `export` / `declare`, chained `A=.claude; B=$A/hooks`, `$HOME`-rooted, redirects) before the control-plane checks; threaded through `bash_control_plane`/`bash_destructive`/cd-guard. Covers `rm -rf $D`, `chmod`/`rmdir`/`unlink`/`shred`/`touch $D`, `export D=…; rm -rf $D`. **Residual #2 narrowed:** only a GENUINELY-inherited `$VAR` (set in a prior separate command / the env, no assignment here) stays opaque — same-command `$VAR` ≠ inherited `$VAR`, no longer conflated. Benign same-command vars (`D=build; rm -rf $D`) stay GREEN. **Totals now: classifier 175/175, gate 26/26, superset 197/0-gaps, soundness 147 RED + 58 GREEN.**

**7th pass (directory-level control-plane mutation):** `is_control_plane` matched only protected FILES, so a worker could disable the firebreak by mutating the parent DIR (`rm -rf .claude/hooks`, `mv .claude .claude.bak`, `rmdir`/`unlink`/`shred`, `chmod -R 000 .claude`) — all classified allow. Fix: new `is_control_plane_dir` (a path that IS or is an ANCESTOR of a protected location — catches parent-dir variants `rm -rf .`/`rm -rf ~`); `bash_control_plane` checks file OR dir; `rmdir`/`unlink`/`shred` added to `CP_WRITE_VERBS`. Self-review found + fixed the `cd`-shift evasion (`( cd .claude && rm -rf hooks )`) via a `cd-into-CP + mutation` fail-closed guard. Benign worktree/sibling work (`.claude/worktrees/…`, `build/`, `.git/hooks`) stays GREEN; trusted identities unaffected (F5). **Totals now: classifier 168/168, gate 26/26, superset 191/0-gaps, soundness 132 RED + 51 GREEN.**

**6th pass (Codex NO-GO for activation → fixed):** Codex found 4 classifier false negatives outside the corpus (gate forwarded, classifier allowed): **P0** control-plane protection missed metadata/creation verbs (`chmod`/`chown`/`touch`/`mkdir`/`chflags`/…); **P0** runner value-flags (`--workspace`/`--filter`/`--prefix`) let recognized RED through; **P1** corepack/pnpx shims; **P1** MCP read-only allowlist allowed compound mutating verbs (`get_or_create`). All fixed + a second self-review found 3 deeper variants (global dispatcher flag before the runner verb `pnpm --filter app exec`; `setfacl`/`xattr`/`link`; MCP camelCase `getOrCreate`) — all fixed, 0 FN / 0 FP. Residual #3 **re-bounded honestly** (unlisted dispatcher/wrapper OR unrecognized package — matching the plan's F13 wording; the prior "unrecognized package only" was too narrow). **Totals now: classifier 151/151, gate 26/26, superset 177/0-gaps, soundness 107 RED + 40 GREEN.**

**5th pass (runner recursion):** closed three runner false negatives — `npx --call`/`-c` command-string flag; two-token runner value-flags; the `npm exec`/`npm x`/`pnpm exec`/`yarn exec`/`bun x` family. Reconciled the soundness count (docs said "70 RED"; live was 68). See the fifth-review doc.

**What's built (committed — `66182d9` … `18037ec`):**
- `.claude/hooks/firebreak-classify.py` — deterministic classifier, pure stdlib. Decision order (F13 opaque-word → control-plane/F9 → outward → indirection → mcp → fail-closed), Step-0 identity contract, atomic approval-record writer. Splits lists/pipelines AND shell grouping/control constructs (`( )`/`{ ; }`/`if`/`for`/`while`/`case`) classifying each simple command; recurses nested `-c`/`--call` command strings, `$(...)`/backtick/`<( )` substitution bodies, git `!`-aliases, and package runners (`npx`/`bunx`/`pnpx`/`corepack`; two-token `pnpm dlx`/`yarn dlx`/`pipx run` + the `npm exec`/`npm x`/`pnpm exec`/`yarn exec`/`bun x` family, with runner value-flags / global dispatcher flags / `--` skipped); resolves git config-aliases, `ext::` transports, and dispatcher global value-options; control-plane protection covers content + metadata/creation verbs (`chmod`/`chown`/`touch`/`mkdir`/`setfacl`/`xattr`/`rmdir`/`unlink`/`shred`/…) AND directory-level mutation (parent-dir/rename/delete of `.claude`·`.claude/hooks`, parent-dir variants `rm -rf .`/`~`, the `cd .claude && mutate` shift, and **same-command variable targets** resolved across every statically-visible assignment mechanism — `D=.claude/hooks; rm -rf $D`, `export`/`declare`/`local` incl. flags, `read … <<<`, `printf -v`, and the in-place default `${D:=.claude/hooks}`); MCP read-only allowlist vetoes compound mutating verbs (`get_or_create`/`getOrCreate`); dequotes argv0/verbs (defeats `c""url`); bare-host/opaque/file/proxy/resolve curl-wget defer; redirect-to-escaping-path for any verb; **plus the red-team hardening (rounds 1–6): a STRUCTURAL BACKSTOP for unrecognized verbs touching the control plane, ANSI-C/case path normalization, concrete-prefix var fail-closed, wrapper-eating fix, git working-tree destruction, curl `-o` output paths, `>|`/`>&` redirects, `trap`/`PROMPT_COMMAND` execution, `ln` hardlink-to-hook, and broad outward/deploy/package coverage; plus the F16b dispatcher local-write backstop (`DISPATCHER_OUTPUT_FLAGS` + `DISPATCHER_POSITIONAL_WRITES`) so a listed dispatcher can't write the CP via `-o`/`--pack-destination`/`git bundle create`/`docker cp` (plus the 883f5cf hardening that enumerated install/build-dest flags `--root`/`--prefix`/`-w`/`--wheel-dir`/`-out`/`-t`/`--target`/`--target-dir`/`--out-dir`/`--modules-folder`/cache-dirs, `git config -f`/`--file`, and `git clone <CP-dir>`).** **235/235** unit tests.
- `.claude/hooks/firebreak-gate.sh` — cheap entry gate (R6). Extracts tool_name + Bash command, matches markers against the COMMAND (not raw JSON). Inspects `file_path` not `content`. **26/26** tests.
- `.claude/hooks/test_firebreak_superset.py` — **gate-superset invariant** (gate forwards EVERY classifier denial; **287-case** corpus, 0 gaps).
- `.claude/hooks/test_firebreak_soundness.py` — **classifier soundness** (the "gate-forwards-but-classifier-allows" guard; **303 RED / 120 GREEN**).
- Run all four: `test_firebreak_classify.py` · `test_firebreak_gate.py` · `test_firebreak_superset.py` · `test_firebreak_soundness.py`.

**Phase 1 REMAINING — the activation layer (deliberately NOT done; user chose checkpoint-for-review):**
1. Wire the gate into **global `~/.claude/settings.json`** `hooks.PreToolUse` (matcher `Bash|mcp__*|Write|Edit`, command `bash .claude/hooks/firebreak-gate.sh`). Step-0-locked placement; **global change** (no-op without a sentinel).
2. **Orchestrator integration** (autopilot `SKILL.md`): write the sentinel after the provenance gate / before worker spawn, flip `phase→tail` before the tail-runner, run the **positive-control real-spawn probe** (abort if not live), remove the sentinel at run end.
3. **Phase 2:** `.gitignore` (`.claude/firebreak-active.json`, `todos/approvals/`) + approvals-queue schema polish + `resolve-todos` guard.

**Three bugs found & fixed during Phase-1 testing/review** (worth a reviewer's eye): a trusted learnings-writer could write an escaping path (`dev-notes/../.ssh/x`) — now denied for everyone outside the sanctioned set; the `bash` gate marker collided with the `"Bash"` tool name (every Bash call force-forwarded) — now requires a trailing space; the gate had no `remove` marker so `npm/yarn/pnpm remove` fast-pathed unseen despite the classifier denying it — found by the superset test, now fixed.

**Hardening passes:** `a5e9975` (gate brace/backslash + script-path; git config-alias + exec-wrapper `-c`); `44a4156` (lists/pipelines, bare-host curl, dispatcher value-options, npx/bunx, command-substitution + redirect-to-escaping false-negatives); `18037ec` (shell grouping/control constructs, process substitution, curl file/proxy/resolve sends, **quote-splitting FIXED**, two-token runners `pnpm dlx`/`yarn dlx`/`pipx run` + deno + builtin, git `ext::` RCE). Two adversarial sweeps to convergence (0 FN / 0 FP).
**Remaining residuals** (declared, see 6th/8th/9th-review docs): #1 allowlisted-interpreter escape; #2 **a NON-statically-resolvable value** target/redirect to a control-plane path — either a **GENUINELY-inherited `$VAR`** (set in a prior separate command / the environment, **no assignment in this command**, `rm -rf $D` with no `D=…` here) OR an **opaque same-command RHS** (`D=$(echo .claude/hooks); rm -rf $D`, the same residual as the direct `rm -rf $(echo .claude/hooks)`); every **statically-resolvable same-command** assignment (`D=.claude/hooks; rm -rf $D`, `read … <<<`, `printf -v`, `${D:=…}`, flagged `declare`/`local`) is now RESOLVED + denied (F14/F15, 8th/9th reviews) and is NOT this residual; #3 **an UNLISTED dispatcher/exec-wrapper with a literal `argv[0]`, OR a recognized runner fetching an UNRECOGNIZED package name** (`npx some-evil-pkg`) stays GREEN — recursion catches all *recognized* inner commands through every *listed* runner/shim, but set enumeration is leaky (re-bounded in the 6th review to match the plan's F13 wording; the prior "unrecognized package only" was too narrow); + pre-existing/external git aliases. (#4 quote-splitting is CLOSED.) **F16b note — the control-plane half of #3 is now closed for BOTH unrecognized verbs (F16 backstop) AND listed-dispatcher local-output writes (F16b + `883f5cf` hardening);** the prior seeds (`cargo install --root`, `pip wheel -w`, `terraform plan -out`, `npm install --prefix`, `pip install --target/-t`, `cargo build --target-dir`, `yarn --modules-folder`, `git config -f`/`--file`, `git clone <CP-dir>`) are now ENUMERATED + denied. The remaining dispatcher seam is a path embedded in a **STRUCTURED flag value** (`docker build -o type=local,dest=<CP>` — the dest sits in a comma-list seen as one opaque token).

## Current State

Today's session (manual) produced three governance/knowledge artifacts and one
completed brainstorm, all committed and pushed to master:

1. **Master extraction** of all unattended-swarm/autopilot/guardrails/evals work —
   `docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md`.
2. **Governance analysis** scoring the autopilot system against Google DeepMind's
   *Three Layers of Agent Security* (June 2026) — surfaced 5 gaps (G1–G5) —
   `docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md`
   (+ source PDF in the same dir).
3. **G1 brainstorm** (refined, 2 review passes, plan-ready) —
   `docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md`.

**G1 in one line:** a risk-tiered firebreak that enforces CLAUDE.md's existing
"Forbidden Actions" contract (currently unenforced under
`dangerouslySkipPermissions`) by classifying actions and **deferring** the
binding/irreversible tail to the `todos/` approval queue, keeping the safe
majority unattended.

## Decisions already locked in the G1 brainstorm

- **Escalation = defer-and-continue** via the existing `todos/` + `resolve-todos`
  queue (human = async batch reviewer, not a 2am babysitter).
- **Classifier = deterministic denylist (v1) → hybrid w/ AI advisory (Phase 2).**
  Deterministic always dispositive; AI only ever flags blind spots.
- **Merge-to-`main` = RED** (deferred for approval; v1 does NOT redesign assembly).
- **RED tier** = git force/shared-push + merge-to-main + prod-DB destructive +
  out-of-repo deletes + external sends + deploy + external-MCP-writes (default-deny)
  + package removal. **GREEN** = everything local in the worktree **+ the sanctioned
  learnings-propagation out-of-repo writes** (carve-out — must not be deferred).

## PLAN phase output (2026-06-21, session 2 — DONE)

1. **Spike GREEN (riskiest assumption verified first).** Empirically confirmed on
   claude 2.1.173 that a **PreToolUse hook fires AND blocks above
   `dangerouslySkipPermissions`** — for both the main session and a Task-spawned
   subagent. Mechanism viable; no fallback (agent-brief/tool-wrapper) needed.
   Residual = worktree-subagent firing + hook placement → gated as Step 0.
   Proof: `docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md`.
2. **Plan written, passed both gates** (plan-quality-gate = GO, ears-validator =
   PASS), then **deepened by 5 adversarial reviewers** (security, architecture,
   simplicity, data-integrity, performance) and **thinned to a safety-complete v1**.
3. **Both brainstorm open questions resolved:** (Q1) human-only approval via a
   glob-isolated `todos/approvals/` queue (NOT extending `resolve-todos`, which runs
   unattended); (Q2) no new run status needed.
4. **Deepening Review changed the design** (table R1–R8 at top of plan):
   - **R1** hook placement flipped **project → GLOBAL** + positive-control probe.
   - **R2** the graceful **deferred-merge wiring CUT from v1** — the swarm-runner
     merge is LOCAL and autopilot never pushes, so "merge-to-main" wasn't actually
     irreversible; the draft's pointer-commit reproduced FC51 base-drift and risked
     a silent false-`PIPELINE_PASS`. v1 merge-RED fires only on a `master`/shared
     target and just defers + one HANDOFF line.
   - **R3/R4** threat model restated honestly (guards honest mistakes + bounds
     outward blast radius, NOT adversarial-proof) + evasion hardening (git `-C`
     normalization, indirection-defer, outward allowlist incl. `gh api`/`npm
     publish`/`nc`/`ssh`, `mcp__*` read-only allowlist).
   - **R5** queue hardened: gitignore `todos/approvals/`, collision-free atomic
     uuid filenames (the `NNN` sequence races across 31 workers).
   - **R6** token-grep fast-path (python cold-start tax ≈ 7–12 min/run).
   - **R8** `/approve` skill deferred to v2; `resolve-todos` guard stays.
5. **User decisions (2026-06-21):** fully cut the status-mapping sliver (no v1
   status engineering for a deferred master-merge); next phase = Plan Review (Codex).
6. **v1 scope = Step 0 → Phase 1 → Phase 2.** v2 (deferred, documented): graceful
   merge disposition, `/approve` skill, AI advisory pass.
7. **Second-review pass (4 user-requested fixes + self-run review → F1–F5,
   commit `0f79883`/`356b542`):**
   - **F1** protect the firebreak **control plane** (hook config/scripts, sentinel,
     `todos/approvals/`) from the workers it governs; matcher extended to
     `Write`/`Edit`; positive-control probe spawns a **real** `isolation:"worktree"`
     + `bypassPermissions` agent.
   - **F2** cover interpreter/direct-script indirection
     (`python`/`python3`/`.venv/bin/*`, `node`, `ruby`, `./script`) vs a vetted
     `test_allowlist`; **declared residual** stated honestly (pytest runs
     worker-authored files = unbounded egress escape; v1 ≠ adversarial sandbox).
   - **F3** learnings carve-out re-keyed to **realpath target + learnings-writer
     identity** (orchestrator/tail-runner), not command shape.
   - **F4** all v2 merge-defer content (`/approve`, pointer commits,
     `PIPELINE_PASS_WITH_DEFERRED_RISK`) **isolated** out of the v1 body into a v2
     appendix.
   - **F5 (root fix from the self-run 2nd review):** key authority on a
     **TRUSTED-IDENTITY allowlist** (orchestrator/swarm-runner/tail-runner), **not
     `agent_id` presence** — the original rule would have **denied the mandatory
     learnings write** and **deferred the swarm-runner's local merge to `master`**
     on every run. Struck "merge" from the shared-push RED row (local merge =
     GREEN; only push/force-push is RED). Gate forwards-on-suspicion; **Step 0 now
     asserts `agent_id`/`agent_type` is present + unforgeable** (else fall back to
     blanket control-plane deny).
   - **Residual risks (now explicit/gated):** (a) the trusted-identity model rests
     on Step 0 proving `agent_type` is unforgeable; (b) the allowlisted-interpreter
     egress escape is a declared bound (real isolation needs OS/network egress
     control — out of scope for v1).
8. **Third/fourth/fifth review passes → F6–F13 (commits `8696bae` / `1458f5a` /
   `388cfaf` / `4ed63fe`), each driven by a Codex or self-run adversarial pass:**
   - **F6** every v1 guarantee (outward AND control-plane) holds for **DIRECT worker
     tool calls only** — an allowlisted interpreter runs worker-authored code
     in-process, invisible to the PreToolUse hook.
   - **F7/F12** `test_allowlist` = hardcoded `KNOWN_TEST_FRAMEWORKS`
     recognized-framework allowlist (plan-text-injection control, NOT a safety claim;
     a bad plan can't promote `python3 deploy.py` to a "test").
   - **F8** Step 0 validates hook metadata for **all four roles** (orchestrator /
     swarm-runner / tail-runner / worker) as an **empirical harness-contract check,
     NOT cryptographic unforgeability**.
   - **F9** env-indirected control-plane write destinations defer (scoped — plain
     worktree-relative writes incl. `> "$out"` stay GREEN).
   - **F10** **autopilot DOES push to a shared remote** — the pre-spawn
     spec-provenance gate (SKILL.md 9w.9.5) **conditionally** `git push`es a spec-only
     commit to `origin/<default-branch>`. Scoped out by ordering: firebreak active =
     **sentinel-present (sentinel-write → run-end)**; sentinel written AFTER the
     provenance gate → push not classified. (Replaced the false "never pushes" claim.)
   - **F11** the direct-call boundary has **named residuals**, not absolute protection.
   - **F13 (latest, Codex P0):** classifier **fail-closes on opaque command-word/verb**
     (`$(printf curl)`, `git $(printf push)`, `sudo $(printf curl)`, `c{u,}rl`) —
     shell-tokenize → defer if argv[0]/dispatcher-verb still contains an expansion;
     recurse exec-wrappers. **Honest downgrade:** set enumeration is leaky → F13
     *reduces, does not close*.
   - **THREE declared direct-call residuals (the current honest threat model):**
     #1 allowlisted-interpreter escape, #2 inherited-`$VAR` redirect to a control-plane
     path, #3 F13 unlisted-dispatcher/exec-wrapper leak. All stated consistently.
   - **Review trail:** Codex returned **NO-GO** once (F10 window contradiction +
     resolve-todos overclaim + shared-master wording — all fixed) and a **P0** on the
     opaque-command-word escape (→ F13). Self-run security reviews caught the F5
     identity inversion and the F13 "closes" overclaim. Handoff record:
     `docs/handoffs/2026-06-21-g1-firebreak-plan-claude-code-handoff.md`.

## Key Artifacts (this session)

| Item | Location |
|------|----------|
| **G1 PLAN (deepened, v1 thinned)** | **docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md** |
| **G1 spike (riskiest assumption, GREEN)** | **docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md** |
| Codex Plan-Review prompt (GO/NO-GO) | "Codex Handoff Prompt" section in the plan above |
| Codex NO-GO review record | docs/handoffs/2026-06-21-g1-firebreak-plan-claude-code-handoff.md |
| G1 brainstorm (plan input) | docs/brainstorms/2026-06-21-g1-risk-tiered-firebreak-brainstorm.md |
| Governance scorecard (G1–G5) | docs/governance/2026-06-21-autopilot-vs-three-layers-agent-security.md |
| Framework source PDF | docs/governance/three-layers-of-agent-security-deepmind-2026-06.pdf |
| Master extraction (system reference) | docs/solutions/2026-06-21-unattended-swarm-autopilot-master-extraction.md |
| Existing approval-queue pattern | todos/ + .claude/skills/resolve-todos/ |
| Permission bypass switch | .claude/settings.local.json (`dangerouslySkipPermissions`) |
| Forbidden Actions contract | CLAUDE.md ("Forbidden Actions", "Bash Command Rules") |

## Deferred Backlog (priority order)

0. **[ACTIVE → CONFIRMING CODEX GO/NO-GO] G1 risk-tiered firebreak** — plan through
   6 review passes (R1–R8, F1–F13), Codex NO-GO + P0 both addressed, build-ready
   pending Step 0. Next: re-run Codex GO/NO-GO; on GO → `/workflows:work` on v1
   (Step 0 → Phase 1 → Phase 2). Commit `4ed63fe`.
1. **FC51 orchestrator rule** — ensure the converged spec is at the worktree base
   before swarm spawn (cherry-pick the spec-update commit into worktree bases, OR
   inline-inject spec sections into briefs). Live fragility that bit Run 070.
   (Partly addressed by the 2026-06-21 `check_spec_provenance.py` BASEREF-FRESH
   change — that's the *detection* half; the orchestrator *repair* rule remains.)
2. **Track A `P-extract`** — refactor `swarm-runner.md` cherry-pick prose into a
   shared callable so Track A (FC51) earns a real EXERCISED fixture row. Overlaps #1.
3. **Suite adoption decision** — wire `validate_hardening.py` in as a blocking gate.
   Proposal: docs/proposals/validate-hardening-on-fixtures.md.
4. **Eval-harness ↔ catalog FC drift** — harness covers 47 FCs; catalog is at
   FC1–FC57. Add scenarios/judges for FC48–FC57. (Surfaced 2026-06-21.)
5. **[070-W4] Todo #070 (P2, LOW)** — double `get_schedule_entries` in
   `callsheets.generate`. File: todos/070-pending-p2-callsheets-generate-redundant-double-query.md
6. **G2–G5** (from the governance scorecard) — in-flight AI monitor (G2),
   monoculture mitigation in verification roles (G3), per-run-nonce ledger
   hardening (G4), delegation-as-authority-transfer (G5).

## Stashes (untouched, local)

3 stashes on `master`: `stash@{0}`/`{1}` are superseded cpaa WIP (safe to drop);
`stash@{2}` is unmerged venue-scraper proxy/`html_mode` work for
`feat/lead-scraper-expansion` (keeper — fix `claude-sonnet-4-20250514` →
`claude-sonnet-4-6` on revival).

## Recovery SHAs (older, if ever needed)

| Ref (deleted) | Tip SHA | Where it lives now |
|---------------|---------|--------------------|
| `feat/film-production-pm` | `9b432bf` | 2nd-parent lineage of `49deb17` on master |
| `test/fc52-9w95-rewire-real-swarm` | `998854e` | reflog / GC window (~30d) |

## Codex Handoff Prompt — Phase 1 CODE REVIEW (run this next)

```
You are reviewing Phase 1 of the G1 risk-tiered firebreak in the Sandbox repo,
branch feat/g1-risk-tiered-firebreak (local, not pushed; latest commit 18037ec).

CONTEXT (read these first):
- Plan:  docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md — start with
  "1. The classifier", "The RED tier — v1", "Acceptance Tests (EARS)", and the
  "Deepening Review — Changelog" (R1–R8, F1–F13).
- Step 0 results: docs/spikes/2026-06-21-g1-pretooluse-hook-under-bypass-spike.md
  (identity contract: orchestrator=no agent_id/type; trusted=agent_type in
  {swarm-runner,tail-runner}; worker=else). The gate extracts the Bash COMMAND
  value and matches markers against THAT (not raw JSON), so brace/backslash
  obfuscation and direct script paths forward without the raw-JSON `{` collision.

CODE UNDER REVIEW (only these — activation layer is intentionally NOT built yet):
- .claude/hooks/firebreak-classify.py     (deterministic classifier)
- .claude/hooks/firebreak-gate.sh         (cheap entry gate, R6)
- .claude/hooks/test_firebreak_classify.py (119 cases)
- .claude/hooks/test_firebreak_gate.py     (26 cases)
- .claude/hooks/test_firebreak_superset.py (gate ⊇ denials invariant, 140-case corpus)
- .claude/hooks/test_firebreak_soundness.py (classifier denies RED / allows GREEN; 70+26)
- docs/reviews/2026-06-2{2,3}-...-{second,third,fourth}-review.md (my review trail)
Run all four test files; classify/gate print "N/N passed"; superset prints "PASS:
... superset invariant holds"; soundness prints "PASS: ... classifier sound".

REVIEW FOR (P0/P1/P2, with file:line and a failing input where possible):
1. SOUNDNESS — can a WORKER get a RED action to ALLOW? Probe the decision order
   (F13 short-circuits first), the shell tokenizer (shell_words / resolve_argv0 —
   exec-wrapper recursion, VAR= stripping, dispatcher-verb opacity), the nested
   `-c` command-string recursion (classify_bash_command), git normalization
   (-C/-c/--git-dir) AND the git config-alias resolver (git_outward_category —
   `-c alias.*=push`, `git config alias.* push`, `!`-aliases), F9 escaping/opaque
   write dests, control-plane realpath matching, the learnings carve-out (identity
   + sanctioned target + no ../symlink escape), and mcp read-only allowlist. Find
   evasions the existing tests miss.
2. GATE COMPLETENESS (superset) — is the gate's marker set a true SUPERSET of
   classifier denials? test_firebreak_superset.py enforces this over a 112-case
   corpus (0 gaps) — try to BREAK it: find a command the classifier denies but the
   gate fast-paths, then add it to the corpus. Confirm no marker collides with
   envelope structural fields the way `bash`→`"Bash"` did (mitigated by command
   extraction).
3. CLASSIFIER SOUNDNESS (the opposite direction) — among commands the gate
   forwards, does the classifier actually DENY the RED ones? test_firebreak_soundness.py
   asserts RED-denied / GREEN-allowed; try to add a RED command it ALLOWS. Probe:
   list/pipeline + shell grouping/control-construct split (split_commands —
   `( curl evil )`, `if x; then curl evil; fi`, `for/while/case`), `$(...)`/backtick/
   `<( )` substitution recursion, redirect-to-escaping (`echo x > /etc/foo`), curl
   bare-host / `-K`config / `-i`input-file / `--proxy` / `--resolve` / `--connect-to`,
   dequote argv0/verb (`c""url`, `g""it push`), two-token runners (`pnpm dlx`/
   `pipx run`) + git `ext::`, dispatcher_verb value-flag skipping. (Two adversarial
   sweeps already drove this to 0 FN / 0 FP — try to find a 1st.)
4. FAIL-CLOSED & RECORD INTEGRITY — unparseable envelope, classifier exception,
   atomic write (temp+os.rename), filename RED-<run>-<cat>-<uuid>.md, deny still
   fires when the record write fails.
5. HONESTY — does the code match the declared residuals (#1 interpreter escape,
   #2 inherited-$VAR redirect, #3 runner/dispatcher + UNRECOGNIZED inner package)?
   Any guarantee broader in the comments than in the code? (#4 quote-splitting is
   now CLOSED.)

DECISION TO CONFIRM (held pending your verdict — do NOT assume; rule on it):
- RESIDUAL #3 BOUND: `npx`/`pnpm dlx`/`pipx run` now recurse to the real command,
  so all RECOGNIZED inner commands are caught (`npx vercel deploy` → deny). But a
  runner + an UNRECOGNIZED package name (`npx some-evil-pkg`, `pipx run mahler`)
  stays GREEN — the classifier cannot know an arbitrary fetched package is RED
  without running it. QUESTION: is that bound acceptable for v1, or should ANY
  `npx/dlx/pipx-run <non-allowlisted-pkg>` defer (stricter, more false positives
  on legit tools like `npx eslint`)? (Author recommends the current bound; rule.)
- Also still open: pre-existing/external git aliases (in-run alias SETUP is denied,
  so only aliases pre-dating the run survive) — accept as residual?

OUT OF SCOPE: global ~/.claude/settings.json wiring, the orchestrator/SKILL.md
sentinel+probe integration, Phase 2 (.gitignore + resolve-todos guard). Those are
the post-review activation steps.

Return: verdict (GO / GO-WITH-FIXES / NO-GO) + a P0/P1/P2 findings table + an
explicit ruling on the residual-#3 bound and git-alias decisions above.
```

After Codex returns: triage P0/P1/P2, apply fixes (re-run ALL FOUR suites green),
run my own adversarial second pass (~/.claude/docs/mandatory-review-workflow.md),
THEN proceed to the activation layer (global wire + orchestrator integration) as a
separate, explicitly-approved step. Decision to push the branch is the user's —
not pushed yet.
