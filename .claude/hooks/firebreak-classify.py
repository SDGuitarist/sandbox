#!/usr/bin/env python3
"""
G1 Risk-Tiered Firebreak -- deterministic PreToolUse classifier.

Reads a PreToolUse hook JSON envelope on stdin, consults the run sentinel
(.claude/firebreak-active.json, found by walking up from cwd -- cwd-independent
so it works for worktree-isolated workers), and decides whether the tool call is
GREEN (allow, exit 0 silently) or RED (deny/defer: emit a permissionDecision
"deny" JSON + write an approval record under todos/approvals/).

  No sentinel  -> no-op (manual sessions untouched).
  Pure stdlib, single file, invoked as ONE command (never `python3 -c`).

Identity contract (empirically confirmed in Step 0, see docs/spikes/...):
  orchestrator -> no agent_id / no agent_type
  trusted      -> agent_type in {swarm-runner, tail-runner}
  worker       -> anything else (has agent_id, agent_type e.g. general-purpose
                  or swarm-<run>-<role>)

Decision order (see docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md
section "1. The classifier"):
  no-sentinel -> identity ->
    Write/Edit : control-plane -> learnings carve-out -> out-of-repo -> GREEN
    Bash       : git-normalize -> F13 opaque (FIRST, short-circuits)
                 -> control-plane / out-of-repo write -> outward/irreversible
                 -> indirection (allowlist KNOWN_TEST_FRAMEWORKS) -> GREEN
    mcp__*     : read-only allowlist -> else defer
  fail-closed  : any classification error on a forwarded (RED-bearing) call -> deny.

This protects against a worker's DIRECT tool calls only. Code executing inside an
allowlisted interpreter is invisible to a PreToolUse hook (declared F6 residual).
"""

import json
import os
import re
import sys
import uuid
from datetime import date

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

HOME = os.path.expanduser("~")
GLOBAL_SETTINGS = os.path.realpath(os.path.join(HOME, ".claude", "settings.json"))
DEVNOTES = os.path.realpath(os.path.join(HOME, "Documents", "dev-notes"))
PITFALLS = os.path.realpath(os.path.join(HOME, ".claude", "docs", "agent-pitfalls.md"))

TRUSTED = {"orchestrator", "swarm-runner", "tail-runner"}
LEARNINGS_WRITERS = {"orchestrator", "tail-runner"}  # NOT swarm-runner (F3+F5)

# F13 recognized command dispatchers (a literal argv[0] whose VERB may be opaque)
DISPATCHERS = {
    "git", "gh", "npm", "pnpm", "yarn", "pip", "pip3", "pipx", "uv", "docker",
    "cargo", "go", "aws", "gcloud", "kubectl", "heroku", "flyctl", "wrangler",
    "terraform", "rsync",
}

# F13 exec-wrappers to recurse through to the real command word. Includes
# package-runners (npx/bunx/pnpx) which fetch+exec the named command, so
# `npx vercel deploy` resolves to the `vercel` command word, and the `corepack`
# shim which passes through to the named package manager (`corepack pnpm dlx X`).
WRAPPERS = {
    "env", "nice", "nohup", "timeout", "xargs", "command", "builtin", "exec",
    "setsid", "stdbuf", "time", "sudo", "doas", "chroot", "unshare", "flock",
    "script", "setarch", "watch", "parallel", "ionice", "chrt", "npx", "bunx",
    "pnpx", "corepack",
}
# wrappers that consume one positional VALUE before the real command -- ONLY
# these, and only when the token looks like that value (a duration/priority
# number, a lockfile/fd, an arch name), NOT the command word. `nice`, `ionice`,
# `stdbuf`, `watch`, `parallel` take FLAGS only (no bare positional value), so they
# are NOT here -- consuming a bare positional ate the real verb
# (`nice rm -rf .claude/hooks` -> argv0 became `-rf`, no verb seen, ALLOW).
WRAPPER_TAKES_ARG = {"timeout", "flock", "setarch", "chrt"}
# binaries we never let a wrapper swallow as its "value" -- they're the command.
OUTWARD_BINS = {"curl", "wget", "ssh", "scp", "sftp", "nc", "ncat", "telnet",
                "rsync", "git", "make", "eval", "source"}
# wrapper flags that take a VALUE (so the value is skipped, not mistaken for the
# command word): `sudo -u user cmd`, `npx -p pkg cmd`, `npx --workspace app cmd`.
WRAPPER_VALUE_FLAGS = {"-u", "--user", "-g", "--group", "-p", "--package",
                       "-C", "--chdir", "-w", "--workspace", "--filter",
                       "--prefix", "--cwd", "--dir"}
# Per-wrapper option flags that take a SEPARATE value, so the value is not left to
# become argv0 (`nice -n 5 rm ...` -> `5` must be skipped, else argv0 = `5` and the
# real `rm` verb is never inspected).
WRAPPER_FLAG_VALUES = {
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "--class", "-n", "--classdata", "-p", "--pid"},
    "timeout": {"-k", "--kill-after", "-s", "--signal"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    "flock": {"-w", "--timeout", "-E", "--conflict-exit-code"},
    "watch": {"-n", "--interval"},
    "parallel": {"-j", "--jobs", "-N", "-L", "-n"},
}

# Bash write verbs that can target the control plane (F1 + F9). Includes
# metadata / creation verbs (chmod/chown/chgrp/touch/mkdir/chflags): they don't
# write CONTENT but a worker can use them to disable/clobber a control-plane file
# (`chmod 000 .claude/hooks/firebreak-classify.py`, `touch
# .claude/firebreak-active.json`) -- so their path positionals are checked too.
CP_WRITE_VERBS = {"rm", "mv", "cp", "install", "ln", "dd", "truncate", "tee", "sed",
                  "chmod", "chown", "chgrp", "touch", "mkdir", "chflags",
                  "setfacl", "xattr", "link", "mkfifo", "mknod",
                  "rmdir", "unlink", "shred", "chattr", "ex", "rename", "mmv"}
# verbs whose destination is arbitrary -> a fully-opaque dest defers (F9c)
ARBITRARY_DEST_VERBS = {"cp", "install", "ln", "dd", "mv", "sed", "truncate"}

DELETE_VERBS = {"rm", "unlink", "shred", "rmdir"}

# Verbs that only READ their path arguments. Used by the control-plane BACKSTOP:
# an UNRECOGNIZED verb (not here, not a known write/delete/dispatcher/wrapper/
# interpreter) that names a control-plane path as an argument fails closed -- so a
# future/unmodeled write binary (`busybox rm`, `vim -es`, `patch`, `sponge`, `gio`)
# can't quietly mutate the firebreak. A genuine reader (`cat .claude/...`) stays
# GREEN. (Writers via redirection are handled separately; interpreters defer via F2/F6.)
READ_ONLY_VERBS = {
    "cat", "bat", "less", "more", "head", "tail", "grep", "egrep", "fgrep", "rg",
    "ag", "ack", "ls", "ll", "stat", "file", "wc", "diff", "cmp", "colordiff",
    "jq", "yq", "cut", "tr", "uniq", "column", "nl", "od", "xxd", "hexdump",
    "strings", "basename", "dirname", "realpath", "readlink", "test", "true",
    "false", "echo", "pwd", "date", "printenv", "which", "type", "comm", "fold",
    "fmt", "expand", "unexpand", "rev", "tac", "look", "join", "paste", "tree",
    "du", "df", "md5", "md5sum", "shasum", "sha1sum", "sha256sum", "cksum",
    "sum", "b2sum", "cd", "pushd", "popd", "dirs", "git",
}

# Indirection set (F2 + F7): defer unless it structurally matches a framework
INTERPRETERS = {"python", "python3", "node", "ruby", "perl", "bash", "sh",
                "zsh", "dash", "ksh", "deno"}

# Two-token package-runner prefixes that fetch+exec the FOLLOWING command
# (like npx/bunx, but spelled as a dispatcher + subcommand). Includes the
# package-manager `exec` family (`npm exec`/`npm x`/`pnpm exec`/`yarn exec`/
# `bun x`), which run the named command word just like `npx`, so the inner
# RED command (`npm exec -- vercel deploy`) must be resolved and classified.
TWO_TOKEN_RUNNERS = {("pnpm", "dlx"), ("yarn", "dlx"), ("pipx", "run"),
                     ("npm", "exec"), ("npm", "x"), ("pnpm", "exec"),
                     ("yarn", "exec"), ("bun", "x")}
# Dispatchers that front a two-token runner (used to skip GLOBAL flags between the
# dispatcher and its runner verb: `pnpm --filter app exec <cmd>`).
RUNNER_DISPATCHERS = {d for (d, _v) in TWO_TOKEN_RUNNERS}

# Value-taking options a two-token runner may carry BEFORE the real command word
# (`pnpm dlx --package vercel vercel deploy`, `pipx run --spec ./evil cmd`,
# `npm exec --package=foo -- cmd`). Skipped (with their values) so the resolver
# lands on the real command, not the flag/value. `-c`/`--call` are NOT here --
# those carry a command STRING handled by extract_nested_commands.
RUNNER_VALUE_FLAGS = {"-p", "--package", "--spec", "--python", "--pip-args",
                      "-i", "--index-url", "--registry", "--node-range",
                      "-w", "--workspace", "--filter", "--prefix", "-C",
                      "--cwd", "--dir"}

# mcp__* read-only verb prefixes (everything else defers -- R4d)
MCP_READONLY_PREFIXES = (
    "get", "list", "search", "read", "download", "query", "resolve", "check",
    "inspect", "describe", "show", "fetch", "wait_for", "help", "view", "find",
    "count", "status",
)
# Mutating tokens that VETO the read-only prefix allowlist: if ANY of these appears
# as a `_`/`-`-split token of an mcp verb, it defers even behind a read prefix
# (`get_or_create`, `read_and_write`, `list_and_delete`). Exact-token match (not
# substring) so `get_updates`/`list_writes` are NOT falsely vetoed.
MCP_MUTATING_TOKENS = {
    "create", "write", "delete", "update", "set", "put", "post", "remove", "add",
    "insert", "modify", "patch", "upsert", "merge", "apply", "deploy", "publish",
    "send", "exec", "execute", "run", "drop", "truncate", "rename", "upload",
    "edit", "generate", "import", "trigger", "restart", "pause", "restore",
    "reset", "rebase", "cancel", "revoke", "grant", "invite", "respond", "reply",
    "comment", "share", "destroy", "kill", "stop", "approve", "reject",
    # extended (9th-pass MCP red-team): clearly write-side actions that a
    # read-only prefix ("getAndReplace", "readDisable") must not whitewash.
    "replace", "archive", "store", "overwrite", "flush", "lock", "unlock",
    "expire", "enable", "disable", "purge", "empty", "rotate", "schedule",
    "move", "label", "unlabel", "draft", "sync", "clear", "wipe", "evict",
    "expunge", "dispatch", "emit", "provision", "terminate", "suspend", "resume",
    "activate", "deactivate", "subscribe", "unsubscribe", "register",
    "unregister", "assign", "unassign", "attach", "detach", "reopen", "tag",
    "untag", "rollback", "snapshot", "duplicate", "clone", "fork", "transfer",
    "submit", "block", "unblock", "finalize", "mute", "unmute",
}

# opacity: command-substitution / backtick / $VAR / ${...} / brace-expansion /
# backslash-escape. (Brace/backslash MUST be checked here in the classifier on the
# isolated command -- NOT in the cheap gate, which greps raw JSON that always has
# "{". Step-0 Phase-1 constraint.)
OPAQUE_RE = re.compile(r"\$\(|`|\$\{|\$[A-Za-z_]|[{}]|\\")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WHICH_RE = re.compile(r"^\$\(which\s+([A-Za-z0-9_./-]+)\)$")

# Loopback hosts an outward send MAY target (everything else defers).
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}

# Standard write sinks a redirection MAY target outside the worktree.
DEV_SINKS = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/zero", "/dev/tty"}

# Dispatcher GLOBAL options that take a VALUE -- skipped when locating the
# subcommand verb, so `gh --repo o/n api` reads the verb as `api`, not `o/n`.
DISPATCHER_VALUE_FLAGS = {
    "gh": {"-R", "--repo", "--hostname"},
    "npm": {"--prefix", "-w", "--workspace", "--registry", "-C", "--cwd",
            "--userconfig", "--globalconfig"},
    "pnpm": {"--prefix", "-w", "--workspace", "--registry", "-C", "--cwd",
             "--dir", "--filter"},
    "yarn": {"--cwd", "--registry"},
    "pip": {"--log", "--cache-dir", "--proxy", "-i", "--index-url",
            "--extra-index-url", "--trusted-host", "-c", "--constraint",
            "-t", "--target"},
    "pip3": {"--log", "--cache-dir", "--proxy", "-i", "--index-url",
             "--extra-index-url", "--trusted-host", "-c", "--constraint",
             "-t", "--target"},
}

# Conventional LOCAL-OUTPUT flags a dispatcher SUBCOMMAND may use to WRITE a file
# or directory (`go build -o F`, `git archive -o F`/`--output=F`, `npm pack
# --pack-destination D`, `pip download -d D`/`--dest D`). A listed dispatcher is
# exempt from the unrecognized-verb control-plane BACKSTOP, so without checking
# these its local-output writes to the firebreak's own files slip through. The
# value is matched against the control plane ONLY, so a `-o`/`-d` that carries a
# non-path value (`kubectl get -o yaml`, `docker run -d`) is harmless -- `yaml`
# isn't a control-plane PATH. Keep this list current as new dispatcher output
# flags are discovered (same maintenance contract as DISPATCHERS itself -- F16
# watch-item).
DISPATCHER_OUTPUT_FLAGS = {
    "-o", "--output", "--output-dir", "--output-directory", "--out-dir",
    "--outdir", "-O", "--output-document", "-d", "--dir", "--dest",
    "--destination", "--pack-destination", "--target-directory", "--target-dir",
}
# Dispatcher subcommands whose local WRITE destination is a POSITIONAL (not a
# flag), so the unrecognized-verb backstop's positional sweep -- which we cannot
# apply wholesale to a dispatcher without denying benign positionals like `git add
# .claude/hooks` (staging, not a write) -- is replaced by a targeted per-subcommand
# rule. {dispatcher: {verb: collector}}; collector(rest_after_verb) -> [dest, ...].
DISPATCHER_POSITIONAL_WRITES = {
    # `git bundle create <FILE> <refs...>` -- FILE is the write target.
    "git": {"bundle": lambda a: a[1:2] if len(a) >= 2 and a[0] == "create" else []},
    # `docker|podman|nerdctl cp <SRC> <DEST>` -- copy INTO a local path. Take both
    # positionals; only a real control-plane path trips the check.
    "docker": {"cp": lambda a: a},
    "podman": {"cp": lambda a: a},
    "nerdctl": {"cp": lambda a: a},
}

# curl/wget flags that take a VALUE (so a flag value like `-d @data.json` is not
# mistaken for the target host).
CURL_VALUE_FLAGS = {
    "-o", "-d", "-H", "-X", "-F", "-u", "-A", "-e", "-b", "-c", "-K", "-T",
    "-m", "-w", "-x", "-E", "-Y", "-y", "-C",
    "--data", "--data-raw", "--data-binary", "--data-urlencode", "--header",
    "--request", "--form", "--user", "--user-agent", "--referer", "--cookie",
    "--cookie-jar", "--output", "--config", "--upload-file", "--proxy",
    "--connect-timeout", "--max-time", "--write-out", "--cert", "--key",
}


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #

def expand(path):
    if path is None:
        return None
    return os.path.expandvars(os.path.expanduser(path))


def realpath(path):
    try:
        return os.path.realpath(expand(path))
    except Exception:
        return expand(path) or ""


def under_tmp(path):
    rp = realpath(path)
    return rp == "/tmp" or rp.startswith("/tmp/") or rp.startswith("/private/tmp/")


def is_dev_sink(path):
    p = expand(path)
    return p in DEV_SINKS or p.startswith("/dev/fd/")


def inside_worktree(path, repo_root):
    """Best-effort: is `path` provably inside the run's worktree tree?

    Worker worktrees live under <repo_root>/.claude/worktrees/... so any path
    under repo_root counts. A relative path with no `..` escape is treated as
    worktree-relative (workers run with cwd == their worktree)."""
    if path is None:
        return False
    p = expand(path)
    if not os.path.isabs(p):
        return ".." not in p.split(os.sep)
    rp = os.path.realpath(p)
    if repo_root:
        rr = os.path.realpath(repo_root)
        if rp == rr or rp.startswith(rr + os.sep):
            return True
    return False


def is_control_plane(path):
    """realpath-resolved (defeats symlink/traversal); covers ~ / $HOME expansion.
    Case-insensitive on the `.claude`/firebreak shape (macOS FS folds case, so
    `.Claude/hooks` reaches the real dir)."""
    if path is None:
        return False
    rp = realpath(path)
    norm = rp.replace("\\", "/")
    low = norm.lower()
    base = os.path.basename(low)
    if rp == GLOBAL_SETTINGS or low == GLOBAL_SETTINGS.lower():
        return True
    if "/.claude/hooks/" in low and base.startswith("firebreak-") and \
            (base.endswith(".py") or base.endswith(".sh")):
        return True
    if base == "firebreak-active.json" and "/.claude/" in low:
        return True
    if "/todos/approvals/" in low or low.endswith("/todos/approvals"):
        return True
    return False


def is_control_plane_dir(path, repo_root=None):
    """A path whose mutation (delete / rename / chmod / metadata) would REMOVE or
    DISABLE a protected control-plane file -- i.e. the path IS, or is an ANCESTOR
    directory of, a protected location. Protected anchors: <repo>/.claude/hooks
    (firebreak hook scripts), <repo>/.claude/firebreak-active.json (sentinel),
    ~/.claude/settings.json (global hook registration), <repo>/todos/approvals
    (queue). So `rm -rf .claude/hooks`, `mv .claude .claude.bak`, `rmdir
    .claude/hooks`, and the parent-dir variants `rm -rf .` / `rm -rf ~` defer for a
    worker -- while a SIBLING subtree (`build/`, `.claude/worktrees/<agent>/...`,
    a new file under `.claude/`) stays writable (it is neither a protected anchor
    nor an ancestor of one)."""
    if path is None:
        return False
    t = realpath(path).replace("\\", "/").rstrip("/") or "/"
    tl = t.lower()
    # (1) the protected dir ITSELF, anywhere it can be reached -- any `.claude` or
    # `.claude/hooks` dir. A worker runs in a git worktree that carries its OWN
    # tracked copy of `.claude/hooks/firebreak-*` (the hook fires with the
    # worktree as cwd), so this must match by shape, not only the repo_root anchor.
    # Case-insensitive (macOS FS folds case).
    if tl.endswith("/.claude") or tl.endswith("/.claude/hooks"):
        return True
    # (2) an ANCESTOR of a protected anchor -- the parent-dir variants `rm -rf .`,
    # `rm -rf ~`, `rm -rf /` that would take a protected file down with them.
    anchors = [GLOBAL_SETTINGS.replace("\\", "/")]
    if repo_root:
        rr = os.path.realpath(repo_root).replace("\\", "/").rstrip("/")
        anchors += [rr + "/.claude/hooks", rr + "/.claude/firebreak-active.json",
                    rr + "/todos/approvals"]
    return any(t == "/" or a == t or a.startswith(t + "/")
               or a.lower() == tl or a.lower().startswith(tl + "/") for a in anchors)


GLOB_RE = re.compile(r"[*?\[]")


def _ansi_c_decode(s):
    """Decode bash ANSI-C `$'...'` escapes the way the shell does: `\\xHH` hex,
    `\\NNN` / `\\0NNN` octal, `\\uHHHH`/`\\UHHHHHHHH`, and the standard letter
    escapes. So `$'\\x2e\\x63laude'` becomes `.claude` (not the literal `x2ex63...`
    the old normalizer left, which reopened the whole control plane)."""
    simple = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f",
              "v": "\v", "e": "\x1b", "\\": "\\", "'": "'", '"': '"', "?": "?"}

    def repl(m):
        e = m.group(0)[1:]
        try:
            if e[0] == "x":
                return chr(int(e[1:], 16))
            if e[0] in "uU":
                return chr(int(e[1:], 16))
            if e[0] == "0":
                return chr(int(e[1:] or "0", 8))
            if e[0] in "01234567":
                return chr(int(e, 8))
        except (ValueError, OverflowError):
            return m.group(0)
        return simple.get(e[0], e[0])

    return re.sub(r"\\(x[0-9a-fA-F]{1,2}|u[0-9a-fA-F]{1,4}|U[0-9a-fA-F]{1,8}"
                  r"|0[0-7]{0,3}|[0-7]{1,3}|.)", repl, s)


def cp_normalize(token):
    """De-obfuscate a path token the way bash would BEFORE control-plane matching:
    DECODE ANSI-C `$'...'` (hex/octal/unicode/letter escapes), strip backslash-
    escapes, then remove quotes. Shell EXPANSIONS (`$VAR`/`${...}`/`$(...)`/backtick)
    and GLOB/BRACE metacharacters are LEFT IN PLACE -- the caller fails closed on
    those via the concrete-prefix check (they can't be statically resolved). Defeats
    `.cla""ude/hooks`, `.claude/hoo\\ks`, `$'.claude/hooks'`,
    `$'\\x2e\\x63laude/hooks'`, `.cla$'\\165'de/hooks`."""
    if not token:
        return token
    t = re.sub(r"\$'([^']*)'", lambda m: _ansi_c_decode(m.group(1)), token)
    t = re.sub(r"\\(.)", r"\1", t)             # de-escape  \x -> x (non-ANSI-C)
    t = re.sub(r"[\"']", "", t)                # remove remaining quotes
    return t


def _concrete_prefix(token):
    """Longest leading run of path segments carrying NO expansion/glob/brace
    metachar. `build/$X`->'build'; `${a[0]}`->''; `.claude/hook*`->'.claude'."""
    out = []
    for s in token.split("/"):
        if "$" in s or "`" in s or "{" in s or GLOB_RE.search(s):
            break
        out.append(s)
    return "/".join(out)


def _prefix_is_safe(prefix, repo_root):
    """A concrete leading prefix that provably bounds the target inside the
    worktree and away from the control plane (so a trailing glob/var is tolerable
    -- narrow `..`-injection residual)."""
    if not prefix or prefix in (".", ".."):
        return False
    if is_control_plane(prefix) or is_control_plane_dir(prefix, repo_root):
        return False
    return inside_worktree(prefix, repo_root) or under_tmp(prefix)


def _cp_path_protected(path, repo_root):
    """True if `path` IS a protected control-plane file, or IS / is INSIDE a
    protected `.claude` or `todos/approvals` dir -- but NOT a mere ANCESTOR (`.`,
    `~`, repo root). Used by the unrecognized-verb backstop, where `.`/`~` are
    benign operands (`eslint .`), unlike for a recursive delete."""
    if is_control_plane(path):
        return True
    rl = realpath(path).replace("\\", "/").rstrip("/").lower()
    return (rl.endswith("/.claude") or rl.endswith("/.claude/hooks")
            or "/.claude/" in rl + "/"
            or rl.endswith("/todos/approvals") or "/todos/approvals/" in rl + "/")


def worker_cp_obfuscation_risk(token, repo_root):
    """For a WORKER control-plane-capable mutation/delete TARGET (already
    cp_normalize'd + same-command-var-expanded): True if the target still carries
    an UNRESOLVED expansion or a control-plane-reaching glob/brace that we cannot
    prove is worktree-internal -- fail closed. Kills the variable-expansion
    (arrays/`${!x}`/`${x:off}`/`${x/a/b}`/cmd-subst) and dot-glob/brace obfuscation
    families without enumerating each form.

    A plain non-dot glob (`*.pyc`, `build/*`) or brace (`{build,dist}`) does NOT
    match hidden `.claude` and stays allowed."""
    if not token:
        return False
    # (1) variable / command substitution -> value is unbounded.
    if "$" in token or "`" in token:
        if not _prefix_is_safe(_concrete_prefix(token), repo_root):
            return True
    # (2) glob/brace that can reach the control plane: a dot-leading glob segment
    # (`.cla*`, `.*`) matches the hidden `.claude`; a brace touching a dot
    # (`{.claude,x}`); or a concrete prefix that is itself control-plane
    # (`.claude/hook*`).
    if GLOB_RE.search(token) or "{" in token:
        for s in token.split("/"):
            if (GLOB_RE.search(s) or "{" in s) and s.startswith("."):
                return True
        if "{" in token and "." in token:
            return True
        pfx = _concrete_prefix(token)
        if pfx and (is_control_plane(pfx) or is_control_plane_dir(pfx, repo_root)):
            return True
    return False


def is_learnings_target(path, project_key):
    """Sanctioned learnings paths (F3); realpath defeats ../symlink escape."""
    if path is None:
        return False
    rp = realpath(path)
    if rp == PITFALLS:
        return True
    if rp == DEVNOTES or rp.startswith(DEVNOTES + os.sep):
        return True
    if project_key:
        memdir = os.path.realpath(
            os.path.join(HOME, ".claude", "projects", project_key, "memory"))
        if rp == memdir or rp.startswith(memdir + os.sep):
            return True
    return False


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #

def classify_identity(env):
    agent_id = env.get("agent_id")
    agent_type = env.get("agent_type")
    if not agent_id and not agent_type:
        return "orchestrator"
    if agent_type in ("swarm-runner", "tail-runner"):
        return agent_type
    return "worker"


# --------------------------------------------------------------------------- #
# Shell tokenization (preserves $(...) / backtick / ${...} / quoted spans)
# --------------------------------------------------------------------------- #

def shell_words(cmd):
    """Split into top-level words, keeping command-substitutions, backtick
    groups, and quoted strings intact (quotes preserved in the token)."""
    words, cur = [], []
    quote = None
    depth = 0          # $( ) nesting
    btick = False
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if quote:
            cur.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if btick:
            cur.append(c)
            if c == "`":
                btick = False
            i += 1
            continue
        if depth > 0:
            cur.append(c)
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            cur.append(c)
            i += 1
            continue
        if c == "`":
            btick = True
            cur.append(c)
            i += 1
            continue
        if c == "$" and i + 1 < n and cmd[i + 1] == "(":
            depth = 1
            cur.append("$")
            cur.append("(")
            i += 2
            continue
        if c.isspace():
            if cur:
                words.append("".join(cur))
                cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    if cur:
        words.append("".join(cur))
    return words


def strip_quotes(tok):
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in ("'", '"'):
        return tok[1:-1]
    return tok


def dequote(tok):
    """Remove ALL unescaped quote characters (not just surrounding) so command-word
    quote-splitting -- `c""url`, `cu''rl`, `g""it` -- normalizes to the real word.
    Opacity metachars ($()/`/${}) are preserved, so F13 still fires on them."""
    return re.sub(r'(?<!\\)["\']', "", tok) if tok else tok


def base_name(tok):
    return os.path.basename(dequote(tok))


def is_opaque(token):
    return token is not None and bool(OPAQUE_RE.search(token))


def _runner_subcommand_end(words, idx):
    """If words[idx] is a runner dispatcher whose runner verb (dlx/exec/x/run)
    follows -- possibly after the dispatcher's own GLOBAL value-flags
    (`pnpm --filter app exec X`, `pnpm -C dir dlx X`, `yarn --cwd x exec X`) --
    return the index JUST PAST the runner verb; else None. This generalizes the
    adjacent two-token match so a global flag between the dispatcher and its
    runner subcommand can't hide the inner command."""
    base = base_name(words[idx])
    if base not in RUNNER_DISPATCHERS:
        return None
    vflags = DISPATCHER_VALUE_FLAGS.get(base, set())
    j = idx + 1
    while j < len(words) and words[j].startswith("-"):
        name = words[j].split("=", 1)[0]
        if "=" not in words[j] and name in vflags and j + 1 < len(words):
            j += 2                       # global value-flag -> skip its value
        else:
            j += 1
    if j < len(words) and (base, base_name(words[j])) in TWO_TOKEN_RUNNERS:
        return j + 1
    return None


def _skip_runner_flags(words, idx):
    """After a two-token runner prefix, skip its leading option flags (and the
    values of value-taking ones) plus a `--` end-of-options separator, so the
    resolver lands on the real command word -- `pnpm dlx --package vercel
    vercel deploy` -> `vercel deploy`, `npm exec -- gh api` -> `gh api`."""
    while idx < len(words) and words[idx].startswith("-"):
        if words[idx] == "--":          # end-of-options -> next token is the cmd
            idx += 1
            break
        flag = words[idx]
        idx += 1
        name = flag.split("=", 1)[0]
        if "=" not in flag and name in RUNNER_VALUE_FLAGS and idx < len(words):
            idx += 1                     # skip the flag's value (e.g. `--spec X`)
    return idx


def _wrapper_value_ok(wrapper, tok):
    """Should `wrapper` consume `tok` as its OWN value rather than the command
    word? Refuse any recognized command verb (so the real verb is never eaten),
    then require the value SHAPE the wrapper actually takes."""
    b = base_name(tok)
    if b in CP_WRITE_VERBS or b in DELETE_VERBS or b in DISPATCHERS \
            or b in OUTWARD_BINS or b in INTERPRETERS or b == "truncate":
        return False
    if wrapper in ("timeout", "chrt"):
        return bool(re.match(r"^\+?\d", tok))        # duration / priority number
    if wrapper == "flock":
        return ("/" in tok) or ("." in tok) or tok.isdigit()  # lockfile / fd
    if wrapper == "setarch":
        return "/" not in tok                         # an arch name token
    return False


def resolve_argv0(words, sentinel):
    """Skip leading VAR= assignments and exec-wrappers; return (argv0, rest)."""
    idx = 0
    while idx < len(words) and ASSIGN_RE.match(words[idx]):
        idx += 1
    # recurse through exec-wrappers
    while idx < len(words):
        base = base_name(words[idx])
        if base in WRAPPERS:
            wflags = WRAPPER_VALUE_FLAGS | WRAPPER_FLAG_VALUES.get(base, set())
            idx += 1
            while idx < len(words) and words[idx].startswith("-"):
                flag = words[idx]
                idx += 1
                if "=" not in flag and flag in wflags and idx < len(words):
                    idx += 1  # skip the flag's value (`npx -p pkg`, `nice -n 5`)
            if base == "env":
                while idx < len(words) and ASSIGN_RE.match(words[idx]):
                    idx += 1
            elif base in WRAPPER_TAKES_ARG and idx < len(words) \
                    and not words[idx].startswith("-") \
                    and base_name(words[idx]) not in WRAPPERS \
                    and not is_opaque(words[idx]) \
                    and _wrapper_value_ok(base, words[idx]):
                idx += 1  # consume the wrapper's positional arg (duration/file/N)
            continue
        # two-token package runners: `pnpm dlx <cmd>`, `pipx run <cmd>`,
        # `npm exec -- <cmd>`, `npm x <cmd>` -- including a global dispatcher
        # flag BEFORE the runner verb (`pnpm --filter app exec <cmd>`). Then skip
        # the runner's own value-flags / `--` separator to reach the command word.
        end = _runner_subcommand_end(words, idx)
        if end is not None:
            idx = _skip_runner_flags(words, end)
            continue
        break
    if idx >= len(words):
        return None, []
    return words[idx], words[idx + 1:]


def first_verb(rest):
    """First non-flag token after a dispatcher (= the subcommand/verb)."""
    for w in rest:
        if w.startswith("-"):
            continue
        return w
    return None


def _pm_effective_verb(rest, dispatcher):
    """The package-manager verb, seeing THROUGH a workspace/exec/run wrapper so
    `yarn workspace app npm publish` / `pnpm --filter x publish` resolve to
    `publish`. Only re-scans when the surface verb is a wrapper -- so `npm install
    publish-helper` (verb `install`) is NOT misread as `publish`."""
    v = dispatcher_verb(rest, dispatcher)
    if v in ("workspace", "workspaces", "exec", "run", "dlx"):
        for w in rest:
            b = base_name(dequote(w))
            if b in ("publish", "unpublish", "uninstall", "remove"):
                return b
    return v


def dispatcher_verb(rest, dispatcher):
    """The subcommand verb, skipping GLOBAL flags AND their values for dispatchers
    whose value-taking options would otherwise be mistaken for the verb
    (`gh --repo o/n api` -> `api`; `pip --cache-dir /tmp uninstall` -> `uninstall`)."""
    vflags = DISPATCHER_VALUE_FLAGS.get(dispatcher, set())
    i = 0
    while i < len(rest):
        w = rest[i]
        if w.startswith("-"):
            name = w.split("=", 1)[0]
            if "=" not in w and name in vflags and i + 1 < len(rest):
                i += 2
            else:
                i += 1
            continue
        return dequote(w)
    return None


# --------------------------------------------------------------------------- #
# git normalization (R4a): drop -C/--git-dir/--work-tree/-c before the verb
# --------------------------------------------------------------------------- #

def git_normalized_rest(rest):
    out, i = [], 0
    while i < len(rest):
        w = rest[i]
        if w == "-C" or w == "-c":
            i += 2
            continue
        if w.startswith("--git-dir") or w.startswith("--work-tree"):
            if "=" not in w:
                i += 2
            else:
                i += 1
            continue
        if w.startswith("-"):
            i += 1
            continue
        out.append(w)
        out.extend(rest[i + 1:])
        return out
    return out


# Git subcommands that are outward / irreversible (push + history rewrite).
GIT_OUTWARD_VERBS = ("push", "filter-repo", "filter-branch")

# Git subcommands that mutate the WORKING TREE (can delete/overwrite/relocate the
# control-plane hook scripts / sentinel without a classic `rm`).
GIT_WT_VERBS = ("rm", "mv", "clean", "checkout", "restore", "switch", "reset",
                "stash", "worktree", "read-tree", "checkout-index", "config",
                "apply", "am")


def git_local_category(rest, identity, repo_root):
    """Worker git commands that disable/destroy the control plane through the
    working tree (not push/history). Trusted identities are unaffected (F5)."""
    if identity in TRUSTED:
        return None
    nrest = git_normalized_rest(rest)
    verb = dequote(nrest[0]) if nrest else None
    if verb not in GIT_WT_VERBS:
        return None
    args = nrest[1:]
    flags = [a for a in args if a.startswith("-")]
    paths = [cp_normalize(p) for p in args if not p.startswith("-")]

    def hits_cp(ps):
        return any(is_control_plane(p) or is_control_plane_dir(p, repo_root)
                   or worker_cp_obfuscation_risk(p, repo_root) for p in ps)

    if verb == "config":
        return "control-plane" if any("hooksPath" in a for a in args) else None
    if verb in ("apply", "am"):              # a patch can rewrite the hook scripts
        return "control-plane"
    if verb == "read-tree":
        return "control-plane" if "--reset" in flags else None
    if verb == "checkout-index":
        return "control-plane" if any(f in ("-a", "--all", "-f", "--force")
                                      for f in flags) else None
    if verb == "clean":                      # untracked wipe -> takes the sentinel
        if not any("f" in f for f in flags):
            return None                      # without -f it's a dry run
        if paths and all(not (is_control_plane(p) or is_control_plane_dir(p, repo_root))
                         and _prefix_is_safe(_concrete_prefix(p), repo_root)
                         for p in paths):
            return None                      # scoped to a safe worktree subdir
        return "control-plane"
    if verb == "reset":
        return "control-plane" if "--hard" in flags else None
    if verb == "stash":
        kill = {"-u", "-a", "--include-untracked", "--all"}
        return "control-plane" if any(f in kill for f in flags) else None
    # rm / mv / checkout / restore / switch / worktree / read-tree / checkout-index
    if hits_cp(paths):
        return "control-plane"
    # whole-tree FORCE overwrite (no path) can clobber the hooks from the index
    if verb in ("checkout", "restore", "read-tree", "checkout-index") and not paths \
            and any(f in ("-f", "--force", "--reset", "-a", "--all") for f in flags):
        return "control-plane"
    return None


def extract_nested_commands(words):
    """Command strings handed to a command-string flag -- `sh -c '<cmd>'`,
    `bash -c`, `flock /tmp/l -c '<cmd>'`, `timeout 5 sh -c '<cmd>'`, and the
    package-runner `--call`/`-c` string (`npx --call 'vercel deploy'`,
    `npm exec -c 'curl evil'`). The real action lives inside the string, so the
    classifier must recurse into it. Both space-separated (`-c <cmd>`) and
    `=`-joined (`--call=<cmd>`) forms are covered. (`python -c` runs python, not a
    shell command, but the top-level interpreter check already defers it -- a
    harmless extra recursion; likewise recursing a benign string only DENIES when
    the inner command is itself RED.)"""
    out = []
    for i in range(len(words)):
        tok = strip_quotes(words[i])
        if tok in ("-c", "--call", "-S", "--split-string") and i + 1 < len(words):
            out.append(strip_quotes(words[i + 1]))
        elif tok.startswith("--call=") or tok.startswith("-c=") \
                or tok.startswith("-S") and len(tok) > 2 \
                or tok.startswith("--split-string="):
            out.append(strip_quotes(tok.split("=", 1)[1] if "=" in tok else tok[2:]))
    # `trap '<cmd>' SIG` -- the handler runs on the signal; classify the handler.
    if words and base_name(words[0]) == "trap":
        for w in words[1:]:
            if w.startswith("-"):
                continue
            out.append(strip_quotes(w))      # first positional = handler command
            break
    # `PROMPT_COMMAND='<cmd>'` -- bash executes the RHS before each prompt; an
    # assignment is otherwise invisible to the command checks.
    for w in words:
        m = re.match(r"^PROMPT_COMMAND=(.*)$", w)
        if m:
            out.append(strip_quotes(m.group(1)))
    return out


def extract_command_substitutions(cmd):
    """Bodies that EXECUTE in a subshell -- `$(...)` command substitution,
    `<(...)`/`>(...)` process substitution, and backtick `...` -- are each
    classified as a command. Denying only when the inner command is itself RED
    keeps benign forms (`$(date)`, `cat <(sort f)`) GREEN while catching
    outward-via-substitution (`echo $(curl evil)`, `cat <(curl evil)`)."""
    subs = []
    i, n = 0, len(cmd)
    while i < n:
        opener = (cmd[i] == "$" and i + 1 < n and cmd[i + 1] == "(") or \
                 (cmd[i] in "<>" and i + 1 < n and cmd[i + 1] == "(")
        if opener:
            depth, j = 1, i + 2
            start = j
            while j < n and depth > 0:
                if cmd[j] == "(":
                    depth += 1
                elif cmd[j] == ")":
                    depth -= 1
                j += 1
            subs.append(cmd[start:j - 1] if depth == 0 else cmd[start:j])
            i = j
        else:
            i += 1
    segs = cmd.split("`")
    for k in range(1, len(segs), 2):
        subs.append(segs[k])
    return subs


def _push(parts, cur):
    s = "".join(cur).strip()
    if s:
        parts.append(s)
    return []


# Shell keywords that PREFIX a real command in a control construct -- stripped so
# the body (`then RED`, `do RED`, `while RED-condition`) is classified.
CONTROL_KEYWORDS = {"if", "then", "elif", "else", "fi", "for", "while", "until",
                    "do", "done", "case", "esac", "select", "function",
                    "coproc"}
# `time` is handled as a WRAPPER (resolve_argv0), NOT a stripped keyword, so its
# `-p`/`--portability` flag is skipped and the real verb is reached (`time -p rm
# -rf .claude/hooks` -> argv0 `rm`, not `-p`).
_CMDPOS = ("", " ", "\t", "\n", ";", "&", "|", "(")


def strip_leading_keywords(seg):
    """Drop leading control keywords / `!` negation so `then curl evil` ->
    `curl evil`, `while curl evil` -> `curl evil`."""
    s = seg.strip()
    while s:
        if s[0] == "!":
            s = s[1:].strip()
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\b", s)
        if not (m and m.group(1) in CONTROL_KEYWORDS):
            break
        if m.group(1) == "case":
            # drop the `case SUBJECT in` header so SUBJECT isn't seen as a command
            inm = re.search(r"\bin\b", s[m.end():])
            s = s[m.end():][inm.end():].strip() if inm else ""
            continue
        s = s[m.end():].strip()
    return s


def split_commands(cmd):
    """Split a Bash command line into SIMPLE commands so EACH is classified.
    Splits on top-level control operators (`;` `&&` `||` `|` `|&` `&` newline) AND
    shell grouping (`( ... )`, `{ ...; }`); leading control keywords are stripped
    (`if`/`then`/`for`/`while`/`do`/...). So `base64 -d | sh`, `( curl evil )`,
    `if x; then curl evil; fi`, `for i in 1; do ./deploy; done` are all evaluated.
    Respects quotes, `$(...)`/`$((...))`/backtick/`${...}`, and backslash-escapes;
    does NOT split redirections (`2>&1`, `>&`, `&>`, `>|`) or brace-expansion
    (`c{u,}rl`). Command-substitution bodies are left intact (classified separately
    via extract_command_substitutions)."""
    parts, cur = [], []
    i, n = 0, len(cmd)
    quote = None
    pdepth = 0   # $( ) / $(( )) command-substitution + arithmetic
    bdepth = 0   # ${ } parameter expansion
    btick = False
    while i < n:
        c = cmd[i]
        if quote:
            cur.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if btick:
            cur.append(c)
            if c == "`":
                btick = False
            i += 1
            continue
        if pdepth > 0:
            cur.append(c)
            if c == "(":
                pdepth += 1
            elif c == ")":
                pdepth -= 1
            i += 1
            continue
        if bdepth > 0:
            cur.append(c)
            if c == "{":
                bdepth += 1
            elif c == "}":
                bdepth -= 1
            i += 1
            continue
        if c == "\\" and i + 1 < n:           # escaped char -> keep both, no split
            cur.append(c)
            cur.append(cmd[i + 1])
            i += 2
            continue
        if c in ("'", '"'):
            quote = c
            cur.append(c)
            i += 1
            continue
        if c == "`":
            btick = True
            cur.append(c)
            i += 1
            continue
        if c == "$" and i + 1 < n and cmd[i + 1] == "(":
            pdepth = 1
            cur.append("$")
            cur.append("(")
            i += 2
            continue
        if c == "$" and i + 1 < n and cmd[i + 1] == "{":
            bdepth = 1
            cur.append("$")
            cur.append("{")
            i += 2
            continue
        if c in "<>" and i + 1 < n and cmd[i + 1] == "(":   # process substitution
            pdepth = 1
            cur.append(c)
            cur.append("(")
            i += 2
            continue
        nxt = cmd[i + 1] if i + 1 < n else ""
        praw = cmd[i - 1] if i > 0 else ""
        if c == "&" and nxt == "&":
            cur = _push(parts, cur)
            i += 2
            continue
        if c == "|" and nxt in ("|", "&"):     # || or |&
            cur = _push(parts, cur)
            i += 2
            continue
        if c == "&":
            if praw == ">" or nxt == ">":      # >&  &>  2>&1 redirection
                cur.append(c)
                i += 1
                continue
            cur = _push(parts, cur)
            i += 1
            continue
        if c == "|":
            if praw == ">":                    # >| clobber redirect
                cur.append(c)
                i += 1
                continue
            cur = _push(parts, cur)
            i += 1
            continue
        if c in (";", "\n"):
            cur = _push(parts, cur)
            i += 1
            continue
        # shell grouping -> split so the grouped body is classified.
        if c == "(" and praw in _CMDPOS:       # subshell `( ... )` / `(cmd)`
            cur = _push(parts, cur)
            i += 1
            continue
        if c == ")":
            cur = _push(parts, cur)
            i += 1
            continue
        if c == "{" and praw in _CMDPOS and nxt in (" ", "\t", "\n"):  # `{ ...; }`
            cur = _push(parts, cur)
            i += 1
            continue
        if c == "}" and praw in (" ", "\t", "\n", ";"):
            cur = _push(parts, cur)
            i += 1
            continue
        cur.append(c)
        i += 1
    _push(parts, cur)
    out = [strip_leading_keywords(p) for p in parts]
    return [p for p in out if p]


def host_of(token):
    """Best-effort host portion of a curl/wget target (strip scheme, userinfo,
    path, query, port)."""
    t = strip_quotes(token)
    t = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", "", t)   # strip scheme
    t = t.split("/")[0].split("?")[0]
    if "@" in t:                                          # strip user:pass@
        t = t.split("@")[-1]
    if t.startswith("["):                                 # [ipv6]:port
        return t.split("]")[0] + "]"
    return t.split(":")[0]


def looks_like_host(token):
    t = strip_quotes(token)
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", t):      # explicit scheme
        return True
    h = host_of(t)
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", h):           # ipv4
        return True
    if re.match(r"^(0x[0-9a-fA-F]+|0[0-7]+|\d{5,})$", h):  # integer-encoded IP
        return True                                        # (decimal/hex/octal)
    if re.match(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$", h):  # dotted domain
        return True
    return False


def _decode_int_ip(h):
    """Decode an integer-encoded IPv4 host (decimal / 0x-hex / 0-octal) to dotted
    quad, else None. So `2130706433` -> '127.0.0.1' (loopback) but `3627734016` ->
    an external dotted quad."""
    try:
        if re.fullmatch(r"0x[0-9a-f]+", h):
            n = int(h, 16)
        elif re.fullmatch(r"0[0-7]+", h):
            n = int(h, 8)
        elif re.fullmatch(r"\d+", h):
            n = int(h)
        else:
            return None
    except ValueError:
        return None
    if n > 0xFFFFFFFF:
        return None
    return f"{(n >> 24) & 255}.{(n >> 16) & 255}.{(n >> 8) & 255}.{n & 255}"


def _is_loopback(host):
    h = host.lower().strip("[]")
    if h in LOOPBACK_HOSTS or h.startswith("127."):
        return True
    ip = _decode_int_ip(h)                    # integer-encoded loopback (127.x)
    return ip is not None and (ip.startswith("127.") or ip == "0.0.0.0")


def curl_external_category(rest, binary="curl"):
    """curl/wget -> external-send unless every target is provably loopback.
    Also defers on: file-driven requests (`-K/--config`, wget `-i/--input-file`),
    DNS/route overrides (`--resolve`, `--connect-to`), and non-loopback proxies
    (`-x/--proxy/--socks*`) -- each can externalize a send that looks local."""
    # Flags whose mere presence makes the destination unverifiable -> defer.
    defer_flags = ({"--config", "-i", "--input-file"} if binary == "wget"
                   else {"-K", "--config", "--resolve", "--connect-to"})
    proxy_flags = {"-x", "--proxy", "--preproxy", "--socks5", "--socks4",
                   "--socks5-hostname", "--socks4a"}
    targets, i, n = [], 0, len(rest)
    while i < n:
        w = rest[i]
        name = w.split("=", 1)[0]
        if name in defer_flags:
            return "external-send"
        if name in proxy_flags:
            val = w.split("=", 1)[1] if "=" in w else (rest[i + 1] if i + 1 < n else "")
            ph = host_of(val)
            if is_opaque(ph) or not _is_loopback(ph):
                return "external-send"
            i += 1 if "=" in w else 2
            continue
        if w.startswith("-"):
            i += 2 if ("=" not in w and w in CURL_VALUE_FLAGS) else 1
            continue
        targets.append(w)
        i += 1
    for t in targets:
        h = host_of(t)
        if is_opaque(h):                       # can't verify it's loopback
            return "external-send"
        if not looks_like_host(t):
            continue
        if _is_loopback(h):
            continue                           # loopback target -- allowed
        return "external-send"                 # a non-loopback host
    return None


def git_alias_defs(rest):
    """Inline `-c alias.NAME=VALUE` definitions (git config-alias evasion of the
    push denylist: `git -c alias.p=push p`)."""
    defs, i = {}, 0
    while i < len(rest):
        w, val = rest[i], None
        if w == "-c" and i + 1 < len(rest):
            val = strip_quotes(rest[i + 1])
            i += 2
        elif w.startswith("-c") and len(w) > 2:
            val = w[2:]
            i += 1
        else:
            i += 1
            continue
        m = re.match(r"alias\.([^=]+)=(.*)", val)
        if m:
            defs[m.group(1)] = m.group(2)
    return defs


def git_alias_value_category(value, identity, repo_root, sentinel, depth):
    """A git alias/config VALUE -> RED category or None. `!<shell>` runs a shell
    command (classify it; a bare `!`-escape is outward by default); otherwise the
    value is a git subcommand whose first word is checked against the denylist."""
    v = strip_quotes(value).strip()
    if not v:
        return None
    if v.startswith("!"):
        return classify_bash_command(v[1:].strip(), identity, repo_root,
                                     sentinel, depth + 1) or "external-send"
    if v.split()[0] in GIT_OUTWARD_VERBS:
        return "shared-push"
    return None


def git_outward_category(rest, identity, repo_root, sentinel, depth):
    """git push / history-rewrite, resolving inline aliases and config-alias setup.
    A LOCAL `git merge --no-ff` (no push) stays GREEN (F5)."""
    # `ext::`/`fd::` git transports run an arbitrary command (RCE) -- defer on any.
    for t in rest:
        tv = strip_quotes(t)
        if tv.startswith("ext::") or tv.startswith("fd::") or "ext::" in tv:
            return "external-send"
    nrest = git_normalized_rest(rest)
    verb = dequote(nrest[0]) if nrest else None   # defeat `git pu""sh`
    aliases = git_alias_defs(rest)
    # 1. any inline alias DEFINITION whose value is outward -> defer (whether or
    #    not it is invoked in this same command).
    for val in aliases.values():
        c = git_alias_value_category(val, identity, repo_root, sentinel, depth)
        if c:
            return c
    # 2. resolve the invoked verb THROUGH an inline alias, then check.
    effective = aliases.get(verb, verb)
    if effective:
        c = git_alias_value_category(effective, identity, repo_root, sentinel, depth)
        if c:
            return c
    # 3. `git config alias.NAME <outward...>` -- setting a dangerous alias.
    if verb == "config":
        joined = " ".join(strip_quotes(t) for t in nrest[1:])
        m = re.match(r"alias\.[^\s=]+[\s=]+(.*)", joined)
        if m:
            c = git_alias_value_category(m.group(1), identity, repo_root,
                                         sentinel, depth)
            if c:
                return c
    # 4. plain push / history rewrite.
    if verb in GIT_OUTWARD_VERBS:
        return "shared-push"
    return None


# --------------------------------------------------------------------------- #
# Bash categories
# --------------------------------------------------------------------------- #

def f13_opaque_defer(words, sentinel):
    """F13: opaque command-word / dispatcher-verb -> defer. Checked FIRST."""
    argv0, rest = resolve_argv0(words, sentinel)
    if argv0 is None:
        return None
    if is_opaque(argv0):
        if not _opaque_guard_ok(argv0, rest, sentinel):
            return "opaque-command-word"
    if base_name(argv0) in DISPATCHERS:
        verb = dispatcher_verb(rest, base_name(argv0))
        if is_opaque(verb):
            return "opaque-dispatcher-verb"
    return None


def _opaque_guard_ok(argv0, rest, sentinel):
    """Over-defer guard: resolve a few provably-safe opaque argv0 to GREEN."""
    runners = set(sentinel.get("runners", []) or [])
    if strip_quotes(argv0) in runners:
        return True
    m = WHICH_RE.match(argv0)
    if m and m.group(1) in INTERPRETERS:
        return True
    # python$VAR -m pytest / unittest
    if argv0.startswith("python") and is_opaque(argv0):
        rl = [strip_quotes(w) for w in rest]
        if "-m" in rl:
            j = rl.index("-m")
            if j + 1 < len(rl) and rl[j + 1] in ("pytest", "unittest"):
                return True
    return False


def redirection_targets(cmd):
    """Targets of redirections that TRUNCATE/APPEND a file: `>`, `>>`, `>|`
    (noclobber override), `>&`/`&>`/`&>>` (both-streams), and fd-numbered forms
    (`1>`, `2>`, `1>|`, `2>>`). The operator family is matched explicitly so a
    target hidden behind `|`/`&` (`>| file`, `>& file`) is still extracted; a
    `&>file` to a control-plane path is a clobber just like `>file`."""
    pat = r"(?:\d*>>?|\d*>\||&>>?|\d*>&)\s*(\"[^\"]*\"|'[^']*'|[^\s|;&<>]+)"
    return [strip_quotes(m.group(1)) for m in re.finditer(pat, cmd)]


def _write_dest_targets(a0, rest):
    """Write destinations that are NOT plain positionals, per verb:
    `dd of=F`, `sort -o F`/`--output F`, `tar -C DIR`/`--directory DIR`,
    `unzip -d DIR`, `rsync ... DEST` (when `--delete` makes it destructive)."""
    out = []
    if a0 in ("curl", "wget"):
        # curl/wget WRITE their downloaded body to `-o`/`--output` (curl) or
        # `-O`/`--output-document` (wget) -- a worker can overwrite a control-plane
        # file via a LOOPBACK url. Cover separate, glued, and `=` forms.
        oflags = ({"-o", "--output"} if a0 == "curl"
                  else {"-O", "--output-document"})
        i = 0
        while i < len(rest):
            w = rest[i]
            if w in oflags and i + 1 < len(rest):
                out.append(rest[i + 1]); i += 2; continue
            if "=" in w and w.split("=", 1)[0] in oflags:
                out.append(w.split("=", 1)[1])
            elif w.startswith("-o") and a0 == "curl" and len(w) > 2:
                out.append(w[2:])
            elif w.startswith("-O") and a0 == "wget" and len(w) > 2:
                out.append(w[2:])
            i += 1
    elif a0 == "dd":
        out += [w[3:] for w in rest if w.startswith("of=")]
    elif a0 == "sort":
        i = 0
        while i < len(rest):
            w = rest[i]
            if w in ("-o", "--output") and i + 1 < len(rest):
                out.append(rest[i + 1]); i += 2; continue
            if w.startswith("-o") and len(w) > 2:
                out.append(w[2:])
            elif w.startswith("--output="):
                out.append(w.split("=", 1)[1])
            i += 1
    elif a0 == "tar":
        i = 0
        while i < len(rest):
            w = rest[i]
            if w in ("-C", "--directory") and i + 1 < len(rest):
                out.append(rest[i + 1]); i += 2; continue
            if w.startswith("--directory="):
                out.append(w.split("=", 1)[1])
            elif w.startswith("-C") and len(w) > 2:        # glued `-C.claude`
                out.append(w[2:])
            i += 1
    elif a0 == "unzip":
        i = 0
        while i < len(rest):
            w = rest[i]
            if w == "-d" and i + 1 < len(rest):
                out.append(rest[i + 1]); i += 2; continue
            if w.startswith("-d") and len(w) > 2:           # glued `-d.claude`
                out.append(w[2:])
            i += 1
    elif a0 in ("rsync", "ditto", "cpio", "pax"):
        # any copy/overwrite tool: its DEST (last positional) is ALWAYS a write
        # target -- `rsync evil .claude/hooks/x` overwrites the hook with NO
        # `--delete` needed. (`--delete` only adds the wipe capability.)
        positionals = [w for w in rest
                       if not w.startswith("-") and not ASSIGN_RE.match(w)]
        if positionals:
            out.append(positionals[-1])       # DEST is the last positional
    return [strip_quotes(t) for t in out]


def positional_args(rest):
    return [strip_quotes(w) for w in rest
            if not w.startswith("-") and not ASSIGN_RE.match(w)]


def _arg_path_candidates(rest):
    """Every token that could carry a PATH to an (unrecognized) verb -- positionals,
    `--flag=VALUE` right-hand sides, `name=VALUE` operands, and glued short-flag
    values (`-o<path>`). Lets the backstop see a control-plane path delivered as a
    flag value (`--output=.claude/hooks/x`, `-o.claude/hooks/x`), not just a bare
    positional. Over-extraction is harmless -- `_cp_path_protected` only fires on a
    real control-plane path."""
    out = []
    for w in rest:
        out.append(strip_quotes(w))
        if "=" in w:
            out.append(strip_quotes(w.split("=", 1)[1]))   # --output=PATH / dest=PATH
        if w.startswith("-") and len(w) > 2:
            out.append(strip_quotes(re.sub(r"^-+[A-Za-z]*", "", w)))  # -o<glued>PATH
    return [c for c in out if c]


def _dispatcher_output_targets(a0, rest):
    """Local WRITE destinations a LISTED dispatcher carries -- via a conventional
    output FLAG (`go build -o F`, `git archive --output=F`, `npm pack
    --pack-destination D`, `pip download -d D`) or a known positional-write
    SUBCOMMAND (`git bundle create F`, `docker cp SRC DEST`). NOT every positional:
    `git add .claude/hooks` stages (does not write the hook) and must stay GREEN, so
    only declared write positions are returned. Caller normalizes/expands + checks
    the control plane, so a flag carrying a non-path value (`kubectl get -o yaml`)
    yields a harmless candidate the CP check filters out."""
    out = []
    i = 0
    while i < len(rest):
        w = rest[i]
        name = w.split("=", 1)[0]
        if w in DISPATCHER_OUTPUT_FLAGS and i + 1 < len(rest):
            out.append(rest[i + 1]); i += 2; continue
        if "=" in w and name in DISPATCHER_OUTPUT_FLAGS:
            out.append(w.split("=", 1)[1])
        elif len(w) > 2 and not w.startswith("--") and w[:2] in DISPATCHER_OUTPUT_FLAGS:
            out.append(w[2:])                       # glued `-o<path>`/`-d<path>`/`-O<path>`
        i += 1
    pos_rules = DISPATCHER_POSITIONAL_WRITES.get(a0)
    if pos_rules:
        verb = dispatcher_verb(rest, a0)
        collector = pos_rules.get(verb)
        if collector:
            # positionals AFTER the subcommand verb (skip the verb token itself)
            after = positional_args(rest)
            after = after[1:] if after and after[0] == verb else after
            out += collector(after)
    return [strip_quotes(t) for t in out]


def _has_link_flag(rest):
    """True if a `cp` invocation creates a hard/symlink alias (`-l`/`--link`,
    `-s`/`--symbolic-link`) rather than copying content."""
    for w in rest:
        if w in ("-l", "--link", "-s", "--symbolic-link"):
            return True
        if w.startswith("-") and not w.startswith("--") and \
                ("l" in w[1:] or "s" in w[1:]):
            return True
    return False


def _cp_dest(rest, pos):
    """Destination of `cp`/`ln`/`install`: the `-t DIR`/`--target-directory` value
    if present, else the LAST positional. (Leading positionals are read sources.)"""
    i = 0
    while i < len(rest):
        w = rest[i]
        if w in ("-t", "--target-directory") and i + 1 < len(rest):
            return strip_quotes(rest[i + 1])
        if w.startswith("--target-directory="):
            return strip_quotes(w.split("=", 1)[1])
        i += 1
    return pos[-1] if pos else None


def bash_control_plane(words, cmd, identity, repo_root, sentinel, assigns=None):
    """F1 + F9: control-plane / out-of-repo / opaque write. Covers write-verb
    positionals (cp/mv/tee/...) AND redirections (`> dest`) for ANY command verb
    (so `echo x > /etc/foo` is caught). `assigns` resolves same-command `$VAR`
    targets (`D=.claude/hooks; rm -rf $D`)."""
    assigns = assigns or {}
    argv0, rest = resolve_argv0(words, sentinel)
    if argv0 is None:
        return None
    a0 = base_name(argv0)
    if a0 == "git":                          # working-tree destruction of the CP
        c = git_local_category(rest, identity, repo_root)
        if c:
            return c
    cp_src = []
    if a0 in ("cp", "ln", "install"):
        # only the DESTINATION is a write target; leading positionals are read
        # SOURCES that legitimately live outside the worktree (`cp ../tmpl build/x`,
        # `ln -s ../shared node_modules/shared`).
        pos = positional_args(rest)
        dest = _cp_dest(rest, pos)
        cp_targets = [cp_normalize(expand_assigns(dest, assigns))] if dest else []
        # BUT `ln` (hard/symlink) and `cp --link/--symbolic-link` create a writable
        # ALIAS, so a control-plane SOURCE is itself dangerous (`ln .claude/hooks/x
        # y; echo evil > y` rewrites the hook through the shared inode/symlink).
        if a0 == "ln" or (a0 == "cp" and _has_link_flag(rest)):
            cp_src = [cp_normalize(expand_assigns(t, assigns)) for t in pos]
    elif a0 in CP_WRITE_VERBS:
        cp_targets = [cp_normalize(expand_assigns(t, assigns))
                      for t in positional_args(rest)]
    else:
        cp_targets = []
    redir = [cp_normalize(expand_assigns(t, assigns))
             for t in redirection_targets(cmd)]
    # Write destinations that are NOT plain positionals: `dd of=F`, `sort -o F`,
    # `tar -C DIR`, `unzip -d DIR`, `rsync --delete ... DEST`. Checked against the
    # control-plane ONLY (not the broad F9b escape sweep -- their other args are
    # read SOURCES that legitimately live outside the worktree).
    dest_targets = [cp_normalize(expand_assigns(t, assigns))
                    for t in _write_dest_targets(a0, rest)]
    worker = identity not in TRUSTED

    # Control-plane path via any write target -> worker denied, trusted allowed.
    # A protected FILE (is_control_plane) OR a directory whose mutation would
    # remove/disable one (is_control_plane_dir: `rm -rf .claude/hooks`, `mv
    # .claude .claude.bak`). The dir check applies to mutation verbs only -- not
    # plain redirects, which create a file and can't remove the dir.
    for t in cp_targets + dest_targets + cp_src:
        if is_control_plane(t) or is_control_plane_dir(t, repo_root):
            return "control-plane" if worker else None
    for t in redir:
        if is_control_plane(t):
            return "control-plane" if worker else None
    if not worker:
        return None
    for t in dest_targets:
        if worker_cp_obfuscation_risk(t, repo_root):
            return "control-plane"

    # Obfuscated control-plane target: an unresolved variable/cmd-subst or a
    # control-plane-reaching glob/brace we can't bound to the worktree -> fail
    # closed (kills array/`${!x}`/substring/pattern-sub/`$(...)` + dot-glob
    # disguises of a `.claude` target).
    for t in cp_targets:
        if worker_cp_obfuscation_risk(t, repo_root):
            return "control-plane"

    # F9: write-verb positional / dest-flag to an escaping / fully-opaque dest
    # (`curl -o /etc/x`, `dd of=/etc/x`, `tar -C /etc`).
    for t in cp_targets:
        if is_opaque(t) and a0 in ARBITRARY_DEST_VERBS:
            return "control-plane"   # fully-opaque arbitrary dest (F9c)
        if not is_dev_sink(t) and not inside_worktree(t, repo_root) \
                and not under_tmp(t):
            return "control-plane"   # escaping / non-worktree dest (F9b)
    for t in dest_targets:
        if not is_dev_sink(t) and not is_opaque(t) \
                and not inside_worktree(t, repo_root) and not under_tmp(t):
            return "control-plane"   # write-dest escaping the worktree

    # Redirection write (ANY verb) to a statically-resolvable escaping dest.
    # An opaque/unresolvable redirect dest stays GREEN (declared residual #2;
    # the plan keeps `> "$out"` computed-worktree-path writes GREEN).
    for t in redir:
        if is_opaque(t):
            continue
        if not is_dev_sink(t) and not inside_worktree(t, repo_root) \
                and not under_tmp(t):
            return "control-plane"

    # BACKSTOP (catch-all): an UNRECOGNIZED verb that names a control-plane path as
    # an argument fails closed. The deny-known-bad verb list can never be complete
    # (busybox/toybox multi-call shims, `vim -es`, `patch`, `sponge`, `gio`, a new
    # archive tool, ...), so any argv0 we don't recognize as a known reader / write
    # verb / dispatcher / wrapper / interpreter, when pointed at the firebreak's own
    # files or dirs, defers. A genuine reader (`cat .claude/...`) is allowlisted.
    if a0 not in READ_ONLY_VERBS and a0 not in CP_WRITE_VERBS \
            and a0 not in DELETE_VERBS and a0 not in DISPATCHERS \
            and a0 not in WRAPPERS and a0 not in INTERPRETERS and a0 != "find":
        for cand in _arg_path_candidates(rest):
            t = cp_normalize(expand_assigns(cand, assigns))
            if _cp_path_protected(t, repo_root):   # IS/inside the CP, not ancestor
                return "control-plane"

    # DISPATCHER LOCAL-WRITE BACKSTOP (F16 dispatcher-skip fix). A LISTED dispatcher
    # is EXEMPT from the unrecognized-verb backstop above, yet can still WRITE the
    # control plane through a LOCAL-OUTPUT flag/subcommand that is neither an outward
    # push/deploy (caught later by bash_outward) nor a known CP_WRITE verb -- e.g.
    # `go build -o .claude/hooks/firebreak-classify.py`, `git archive
    # --output=.claude/hooks/x HEAD`, `git bundle create .claude/hooks/x HEAD`,
    # `docker cp c:/x .claude/hooks/firebreak-classify.py`, `npm pack
    # --pack-destination .claude/hooks`, `pip download -d .claude/hooks`. git's own
    # working-tree destruction (GIT_WT_VERBS) was already disposed by
    # git_local_category at the top of this function; this closes the local-OUTPUT
    # half for every dispatcher. Scoped to declared write positions, so benign
    # positionals (`git add .claude/hooks` = staging, not a write) stay GREEN.
    if a0 in DISPATCHERS:
        scan = git_normalized_rest(rest) if a0 == "git" else rest
        for cand in _dispatcher_output_targets(a0, scan):
            t = cp_normalize(expand_assigns(cand, assigns))
            if _cp_path_protected(t, repo_root) \
                    or worker_cp_obfuscation_risk(t, repo_root):
                return "control-plane"
    return None


def bash_destructive(words, cmd, repo_root, sentinel, assigns=None):
    """Data deletes and out-of-repo deletes (errs toward defer). `assigns` resolves
    same-command `$VAR` targets."""
    assigns = assigns or {}
    argv0, rest = resolve_argv0(words, sentinel)
    if argv0 is None:
        return None
    a0 = base_name(argv0)
    if a0 == "find" and ("-delete" in rest or "-exec" in rest
                         or "-execdir" in rest):
        # Scope it: deny when the search ROOT is the control-plane dir itself /
        # out-of-repo, when a control-plane literal appears (`-name 'firebreak-*'`,
        # `-path '*/.claude/*'`), or when a control-plane-ANCESTOR root (`.`, `~`)
        # is swept with NO name/path filter (whole-tree wipe). A benign in-worktree
        # cleanup (`find build -delete`, `find . -name '*.pyc' -delete`) stays GREEN.
        roots = []
        for w in rest:
            if w.startswith("-"):
                break
            roots.append(cp_normalize(expand_assigns(w, assigns)))
        roots = roots or ["."]
        for r in roots:
            rl = realpath(r).rstrip("/").lower()
            if is_control_plane(r) or rl.endswith("/.claude") \
                    or rl.endswith("/.claude/hooks") or "/.claude/" in rl + "/" \
                    or "/todos/approvals" in rl:
                return "control-plane"         # root IS the protected dir / inside it
            if not inside_worktree(r, repo_root) and not under_tmp(r):
                return "out-of-repo-delete"
        low = cmd.lower()
        if any(lit in low for lit in (".claude", "firebreak-", "settings.json",
                                      "todos/approvals")):
            return "control-plane"
        has_filter = any(p in rest for p in ("-name", "-iname", "-path", "-ipath",
                                             "-regex", "-iregex", "-wholename"))
        if not has_filter and any(is_control_plane_dir(r, repo_root) for r in roots):
            return "control-plane"             # unfiltered whole-tree wipe from `.`/`~`
        return None
    if a0 not in DELETE_VERBS and a0 != "truncate":
        return None
    for t0 in positional_args(rest):
        t = expand_assigns(t0, assigns)
        rp = realpath(t)
        if rp.endswith(".db") and not under_tmp(t):
            return "data"
        if not inside_worktree(t, repo_root) and not under_tmp(t):
            return "out-of-repo-delete"
    return None


def bash_outward(words, sentinel, identity, repo_root, depth):
    """Outward / irreversible (allowlist-deny). Local git merge stays GREEN."""
    argv0, rest = resolve_argv0(words, sentinel)
    if argv0 is None:
        return None
    a0 = base_name(argv0)

    if a0 in ("curl", "wget"):
        return curl_external_category(rest, a0)
    if a0 in ("nc", "ncat"):
        # loopback port-probe (`nc -z localhost 5432`) is benign; a listener
        # (`nc -l ...`, reverse-shell risk) or a non-loopback host defers.
        if any(w == "-l" or w.startswith("-l") or w == "--listen" for w in rest):
            return "external-send"
        for w in rest:
            h = strip_quotes(w)
            if w.startswith("-") or h.isdigit():
                continue
            if is_opaque(h) or not _is_loopback(host_of(h)):
                return "external-send"
        return None
    if a0 in ("ssh", "scp", "sftp", "telnet", "socat", "dig", "host",
              "nslookup", "drill", "whois", "ftp", "tftp", "lftp",
              "rclone", "s3cmd", "kafkacat", "kcat", "mosquitto_pub",
              "sendmail", "mailx", "mail", "mutt", "ncftp", "rsh", "mc"):
        return "external-send"
    if a0 == "glab":                         # GitLab CLI -- like gh
        return "external-send"
    if a0 in ("docker", "podman", "nerdctl"):
        v = dispatcher_verb(rest, a0)
        if v in ("push", "login"):
            return "external-send"
        if v in ("run", "exec", "create") and any(
                w in ("-v", "--volume", "--mount", "--privileged")
                or w.startswith("-v") or w.startswith("--volume=")
                or w.startswith("--mount=") for w in rest):
            return "control-plane"           # host bind-mount escape
        return None
    if a0 == "rsync":
        if any(":" in strip_quotes(w) and not strip_quotes(w).startswith("-")
               for w in rest):
            return "external-send"
        return None
    if a0 == "gh":
        verb = dispatcher_verb(rest, "gh")
        if verb in ("api", "release", "pr", "gist", "repo", "secret",
                    "workflow", "run", "issue"):
            return "external-send"
        return None
    if a0 in ("aws", "gcloud"):
        return "external-send"

    # deploy
    if a0 in ("vercel", "railway", "fly", "flyctl", "netlify", "wrangler",
              "heroku", "pulumi", "serverless", "sls", "doctl", "cdk",
              "ansible-playbook", "ansible", "nomad", "skaffold", "flux"):
        return "deploy"
    if a0 == "argocd" and dispatcher_verb(rest, "argocd") in ("app", "sync", "login"):
        return "deploy"
    if a0 == "helm" and dispatcher_verb(rest, "helm") in ("install", "upgrade",
                                                          "uninstall", "delete", "rollback"):
        return "deploy"
    if a0 == "terraform" and dispatcher_verb(rest, "terraform") in ("apply", "destroy"):
        return "deploy"
    if a0 == "kubectl":
        return "deploy"

    # packages
    if a0 in ("pip", "pip3", "pipx") and dispatcher_verb(rest, a0) == "uninstall":
        return "package"
    if a0 in ("gem", "brew", "cargo", "conda", "apt", "apt-get", "yum", "dnf",
              "apk", "pacman", "go") and "uninstall" in [dequote(w) for w in rest]:
        return "package"
    if a0 in ("apt", "apt-get", "yum", "dnf", "brew", "conda", "pacman", "apk") \
            and ("remove" in [dequote(w) for w in rest]
                 or "purge" in [dequote(w) for w in rest]):
        return "package"
    if a0 == "uv":                           # `uv pip uninstall`, `uv publish`
        v = dispatcher_verb(rest, "uv")
        if v == "publish":
            return "deploy"
        if v == "pip" and "uninstall" in [dequote(w) for w in rest]:
            return "package"
    if a0 in ("npm", "pnpm", "yarn"):
        if _pm_effective_verb(rest, a0) in ("uninstall", "remove", "rm",
                                            "publish", "unpublish"):
            return "package"

    # git push / force / history rewrite (resolves inline `-c alias.*` evasion)
    if a0 == "git":
        return git_outward_category(rest, identity, repo_root, sentinel, depth)
    return None


def bash_indirection(words, cmd, sentinel):
    """F2 + F7: interpreters / scripts / eval / npm run / make -> defer unless
    the command structurally matches the hardcoded KNOWN_TEST_FRAMEWORKS."""
    argv0, rest = resolve_argv0(words, sentinel)
    if argv0 is None:
        return None
    a0 = base_name(argv0)
    raw0 = strip_quotes(argv0)

    if _matches_known_test_framework(a0, raw0, rest):
        return None  # allowlisted -> GREEN (still runs arbitrary code: F6 residual)

    # eval / source / dot
    if a0 in ("eval", "source") or raw0 == ".":
        return "indirection"
    # npm run / make are NOT auto-allowed
    if a0 in ("npm", "pnpm", "yarn") and dispatcher_verb(rest, a0) == "run":
        return "indirection"
    if a0 == "make":
        return "indirection"
    # interpreters on a non-framework target
    if a0 in INTERPRETERS or raw0.endswith("/python") or "/.venv/bin/" in raw0:
        return "indirection"
    # direct script execution: ./x.sh, /abs/script, path/to/script
    if raw0.startswith("./") or raw0.startswith("/") or "/" in raw0:
        return "indirection"
    return None


def _matches_known_test_framework(a0, raw0, rest):
    """Direct framework invocations only -- no shell metachars, no arbitrary
    <script>.py / ./script target. npm run / make excluded (F7)."""
    rl = [strip_quotes(w) for w in rest]
    if a0 in ("pytest", "rspec", "jest", "vitest"):
        return True
    if a0 in ("python", "python3"):
        return len(rl) >= 2 and rl[0] == "-m" and rl[1] in ("pytest", "unittest")
    if a0 == "go":
        return len(rl) >= 1 and rl[0] == "test"
    if a0 == "cargo":
        return len(rl) >= 1 and rl[0] == "test"
    return False


def expand_assigns(token, assigns):
    """Substitute `$VAR` / `${VAR}` using SAME-COMMAND assignments only. An unknown
    var stays literal -- so a genuinely INHERITED env var keeps its `$` and remains
    opaque (the declared residual), while a var assigned earlier in this same Bash
    command resolves to a concrete path the control-plane checks can see.

    Also resolves an in-place DEFAULT expansion `${VAR:=word}` / `${VAR:-word}` /
    `${VAR=word}` / `${VAR-word}` to its statically-visible default `word` (when VAR
    is not a known same-command assign) -- so `rm -rf ${D:=.claude/hooks}` and `echo
    x > ${F:=$HOME/.claude/settings.json}` expose their literal target. A bare
    `${VAR}` (no operator) or an alternate `${VAR:+word}` / other operator stays
    literal/opaque when VAR is unknown (declared residual)."""
    if not token or "$" not in token:
        return token

    def repl(m):
        if m.group("bname") is not None:        # ${VAR...} braced form
            name = m.group("bname")
            op = m.group("op")
            word = m.group("word") or ""
            if op:                              # default operator `:-`/`:=`/`-`/`=`
                if name in assigns:
                    return assigns[name]
                return expand_assigns(word, assigns)
            if word == "":                      # bare `${VAR}`
                return assigns.get(name, m.group(0))
            # any OTHER operator we do NOT statically apply -- substring `${x:2}`,
            # pattern-sub `${x/a/b}`, case `${x^^}`, index `${a[0]}`, indirect... --
            # MUST stay opaque (returning the raw value would drop the transform and
            # under-resolve). Keep it literal so the obfuscation guard fails closed.
            return m.group(0)
        name = m.group("sname")                 # $VAR bare form
        return assigns.get(name, m.group(0))

    pattern = (r"\$\{(?P<bname>\w+)(?P<op>:?[-=])?(?P<word>[^}]*)\}"
               r"|\$(?P<sname>\w+)")
    return re.sub(pattern, repl, token)


def collect_assignments(simples):
    """Variables assigned WITHIN this Bash command -> {VAR: literal value}. Covers
    `VAR=value` (its own simple), `export`/`declare`/`typeset`/`local VAR=value`,
    the here-string read `read [opts] VAR <<< value`, and `printf -v VAR FORMAT`
    (no-`%` format). This is what distinguishes a same-command assignment
    (statically resolvable -> must be checked) from an INHERITED environment
    variable (set in a prior, separate command/environment -> genuinely opaque,
    declared residual). An opaque RHS (`$(...)`, backtick, or a not-yet-assigned
    `$VAR`) is skipped so we never fabricate a value -- so an opaque same-command
    RHS (`D=$(echo .claude/hooks)`) is NOT resolvable and falls in the same declared
    residual as an inherited var. RHS may reference earlier same-command assigns
    (`A=x; B=$A/y`). Inline prefixes (`D=x cmd`) are NOT collected: bash expands a
    later `$D` arg from the PARENT shell before that assignment applies."""
    assigns = {}

    def record(name, raw):
        # resolve same-command vars, then `~`/`$HOME`/`$PWD` etc. so
        # `F=$HOME/.claude/settings.json` becomes a concrete path. Opaque RHS
        # (still $(...)/`backtick`/unknown $VAR) -> skip (declared residual).
        if not ASSIGN_RE.match(name + "="):
            return
        if raw.lstrip().startswith("("):       # array literal `a=(...)` -> not a
            return                              # scalar path; `${a[0]}` stays opaque
        val = expand(expand_assigns(strip_quotes(raw), assigns))
        if is_opaque(val):
            return
        assigns[name] = val

    for s in simples:
        w = shell_words(s)
        if not w:
            continue
        b0 = base_name(w[0])
        # `read [opts] VAR <<< value` -- here-string assignment (single var only;
        # a multi-var read splits on IFS and is not statically resolvable).
        if b0 == "read" and "<<<" in w:
            hidx = w.index("<<<")
            names = [x for x in w[1:hidx] if not x.startswith("-")]
            if len(names) == 1 and hidx + 1 < len(w):
                record(names[0], w[hidx + 1])
            continue
        # `printf -v VAR FORMAT [ARG]` -- assigns the literal FORMAT to VAR when it
        # has no `%` conversion; or the single ARG when FORMAT is exactly `%s`. Any
        # richer `%`-format is not statically resolvable -> skip (declared residual).
        if b0 == "printf" and "-v" in w:
            vidx = w.index("-v")
            if vidx + 2 < len(w):
                name, fmt = w[vidx + 1], strip_quotes(w[vidx + 2])
                if fmt == "%s" and vidx + 3 < len(w):
                    record(name, w[vidx + 3])
                elif "%" not in fmt:
                    record(name, w[vidx + 2])
            continue
        tok = None
        if b0 in ("export", "declare", "typeset", "local"):
            # skip the keyword's own flags (`declare -g`, `local -r`, `export --`)
            # and take the FIRST `VAR=value` token.
            tok = next((x for x in w[1:] if ASSIGN_RE.match(x)), None)
        elif len(w) == 1 and ASSIGN_RE.match(w[0]):
            tok = w[0]
        if not tok:
            continue
        name, val = tok.split("=", 1)
        record(name, val)
    return assigns


def _xargs_risk(cmd, simples):
    """`xargs <verb>` where the real target is fed on stdin. Outward verb -> defer
    (xargs-to-curl is rare benign). Delete/CP verb -> defer only if the command
    line carries a control-plane literal (so `find . -name '*.pyc' | xargs rm`
    stays GREEN)."""
    fed_outward = fed_cp = False
    for s in simples:
        w = shell_words(s)
        for i, t in enumerate(w):
            if base_name(t) != "xargs":
                continue
            j = i + 1
            while j < len(w) and w[j].startswith("-"):   # skip xargs flags
                j += 1
            if j < len(w):
                vb = base_name(dequote(w[j]))
                if vb in OUTWARD_BINS or vb in ("vercel", "railway", "fly",
                        "flyctl", "netlify", "wrangler", "heroku", "kubectl"):
                    fed_outward = True
                if vb in CP_WRITE_VERBS or vb in DELETE_VERBS:
                    fed_cp = True
    if fed_outward:
        return "external-send"
    if fed_cp:
        low = cmd.lower()
        if any(lit in low for lit in (".claude", "firebreak-", "settings.json",
                                      "todos/approvals")):
            return "control-plane"
    return None


def classify_bash_command(cmd, identity, repo_root, sentinel, depth=0):
    """Classify a Bash command LINE -> RED category or None. Splits lists and
    pipelines (`;` `&&` `||` `|` `&`) so EVERY simple command is evaluated
    (e.g. `base64 -d | sh`, `foo && curl evil`); any RED simple command wins."""
    if depth > 4:                       # runaway nesting -> fail closed
        return "fail-closed"
    simples = split_commands(cmd)
    if not simples:                     # nothing left after stripping -> classify raw
        return classify_simple_command(cmd, identity, repo_root, sentinel, depth)
    # Same-command variable assignments (`D=.claude/hooks; rm -rf $D`) are resolved
    # so a control-plane target hidden behind a same-command var is still checked.
    assigns = collect_assignments(simples)
    # `cd <control-plane-dir> && <mutate>`: the classifier resolves each simple
    # against the PROCESS cwd, so a `cd .claude` makes a later relative mutation
    # (`rm -rf hooks`) resolve wrong. If the sequence both cd's into the control
    # plane AND carries a mutation verb, fail-closed for a worker (no legitimate
    # reason to cd into the firebreak's own dir and mutate).
    if identity not in TRUSTED and _cd_into_control_plane(simples, repo_root, assigns) \
            and _has_mutation_verb(simples, sentinel):
        return "control-plane"
    # `... | xargs <verb>`: the destructive/outward target arrives on STDIN, off
    # the argv the classifier sees. Fail closed for a worker when xargs feeds an
    # outward verb, or feeds a delete/CP verb AND a control-plane literal appears
    # in the line (`echo .claude/hooks | xargs rm -rf`).
    if identity not in TRUSTED:
        c = _xargs_risk(cmd, simples)
        if c:
            return c
    for s in simples:
        c = classify_simple_command(s, identity, repo_root, sentinel, depth, assigns)
        if c:
            return c
    return None


def _cd_into_control_plane(simples, repo_root, assigns=None):
    """True if any `cd`/`pushd` in the sequence targets a control-plane dir
    (same-command `$VAR` targets resolved)."""
    assigns = assigns or {}
    for s in simples:
        w = shell_words(s)
        if not w or base_name(w[0]) not in ("cd", "pushd"):
            continue
        for t in w[1:]:
            if t.startswith("-"):
                continue
            te = expand_assigns(strip_quotes(t), assigns)
            if is_control_plane_dir(te, repo_root) or is_control_plane(te):
                return True
            break
    return False


def _has_mutation_verb(simples, sentinel):
    """True if any simple command is a write/delete/metadata mutation or a
    `find ... -delete/-exec` or carries a `>`/`>>` redirection."""
    for s in simples:
        if redirection_targets(s):
            return True
        argv0, rest = resolve_argv0(shell_words(s), sentinel)
        if argv0 is None:
            continue
        a0 = base_name(argv0)
        if a0 in CP_WRITE_VERBS or a0 in DELETE_VERBS:
            return True
        if a0 == "find" and ("-delete" in rest or "-exec" in rest):
            return True
    return False


def classify_simple_command(cmd, identity, repo_root, sentinel, depth=0, assigns=None):
    """One simple command -> RED category or None. Recurses into nested `-c`
    command strings (sh/bash/flock -c '<cmd>', which may themselves be pipelines)
    and git `!`-aliases so the real action behind a wrapper/alias cannot evade.
    `assigns` = same-command variable assignments (resolves `$VAR` targets)."""
    if depth > 4:
        return "fail-closed"
    assigns = assigns or {}
    words = shell_words(cmd)
    for inner in extract_nested_commands(words):
        c = classify_bash_command(inner, identity, repo_root, sentinel, depth + 1)
        if c:
            return c
    for sub in extract_command_substitutions(cmd):   # $(...) / `...` bodies execute
        c = classify_bash_command(sub, identity, repo_root, sentinel, depth + 1)
        if c:
            return c
    if identity == "worker":            # F13 first -- short-circuits
        c = f13_opaque_defer(words, sentinel)
        if c:
            return c
    c = bash_control_plane(words, cmd, identity, repo_root, sentinel, assigns)
    if c:
        return c
    c = bash_destructive(words, cmd, repo_root, sentinel, assigns)
    if c:
        return c
    c = bash_outward(words, sentinel, identity, repo_root, depth)
    if c:
        return c
    c = bash_indirection(words, cmd, sentinel)
    if c:
        return c
    return None


# --------------------------------------------------------------------------- #
# mcp
# --------------------------------------------------------------------------- #

def mcp_decision(tool_name):
    parts = tool_name.split("__")
    verb = (parts[-1] if len(parts) >= 3 else tool_name).lower()
    # A read-only PREFIX is not enough: a compound verb can pair a read prefix
    # with a mutating action (`get_or_create`, `read_and_write`, `getOrCreate`).
    # Veto FIRST on any mutating token so the prefix can't whitewash it. Split on
    # `_`/`-` AND camelCase boundaries (insert `_` before an interior capital) so
    # `getOrCreate` -> get/or/create. Exact-token match avoids substring false
    # positives (`get_updates` is NOT vetoed by `update`).
    raw = (parts[-1] if len(parts) >= 3 else tool_name)
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", raw).lower()
    if any(t in MCP_MUTATING_TOKENS for t in re.split(r"[_\-]+", snake)):
        return "mcp-write"
    if any(verb.startswith(p) for p in MCP_READONLY_PREFIXES):
        return None
    return "mcp-write"


# --------------------------------------------------------------------------- #
# Top-level classification
# --------------------------------------------------------------------------- #

def classify(env, sentinel):
    """Return (decision, category, reason). decision in {allow, deny}."""
    tool = env.get("tool_name", "")
    tin = env.get("tool_input", {}) or {}
    identity = classify_identity(env)
    repo_root = sentinel.get("repo_root")
    project_key = sentinel.get("project_key")
    blanket = bool(sentinel.get("blanket_deny_control_plane"))

    # ---- Write / Edit -----------------------------------------------------
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        target = tin.get("file_path") or tin.get("path") or tin.get("notebook_path")
        if is_control_plane(target):
            if blanket:
                # fallback: only the orchestrator writing ONLY the sentinel passes
                rp = realpath(target)
                if identity == "orchestrator" and os.path.basename(rp) == \
                        "firebreak-active.json":
                    return "allow", None, "sentinel teardown (blanket-deny mode)"
                return "deny", "control-plane", "blanket-deny: control-plane write"
            if identity in TRUSTED:
                return "allow", None, f"control-plane write by trusted {identity}"
            return "deny", "control-plane", f"worker write to control plane: {target}"
        # learnings carve-out (F3 + F5): sanctioned target + learnings-writer
        if is_learnings_target(target, project_key):
            if identity in LEARNINGS_WRITERS:
                return "allow", None, f"learnings carve-out ({identity})"
            return "deny", "control-plane", \
                f"learnings write from non-writer identity {identity}"
        # Any other out-of-worktree write -> defer for ANYONE. The only
        # legitimate out-of-repo writes are control-plane (trusted) and
        # sanctioned-learnings (writer), both handled above; an escaping or
        # non-sanctioned target -- even from a trusted learnings-writer -- is
        # denied (EARS: "...or targets a [escaping path] -> not allowed").
        if not inside_worktree(target, repo_root) and not under_tmp(target):
            return "deny", "out-of-repo-write", f"out-of-worktree write: {target}"
        return "allow", None, "worktree write"

    # ---- Bash -------------------------------------------------------------
    if tool == "Bash":
        cmd = tin.get("command", "") or ""
        cat = classify_bash_command(cmd, identity, repo_root, sentinel, 0)
        if cat:
            return "deny", cat, f"bash RED ({cat}): {cmd}"
        return "allow", None, "local/build"

    # ---- mcp__* -----------------------------------------------------------
    if tool.startswith("mcp__"):
        cat = mcp_decision(tool)
        if cat:
            return "deny", cat, f"mcp tool not on read-only allowlist: {tool}"
        return "allow", None, "mcp read-only"

    return "allow", None, "unclassified tool"


# --------------------------------------------------------------------------- #
# Sentinel + approval record + output
# --------------------------------------------------------------------------- #

def find_sentinel():
    override = os.environ.get("FIREBREAK_SENTINEL")
    if override:
        return override if os.path.isfile(override) else None
    d = os.getcwd()
    while True:
        cand = os.path.join(d, ".claude", "firebreak-active.json")
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def write_approval_record(sentinel, env, category, reason):
    """Atomic temp-file + os.rename. Returns the filename, or None on failure."""
    repo_root = sentinel.get("repo_root")
    if not repo_root:
        return None
    approvals = os.path.join(repo_root, "todos", "approvals")
    os.makedirs(approvals, exist_ok=True)
    run_id = sentinel.get("run_id") or "unknown"
    fname = f"RED-{run_id}-{category}-{uuid.uuid4().hex[:12]}.md"
    final = os.path.join(approvals, fname)
    tmp = final + ".tmp"
    tin = env.get("tool_input", {}) or {}
    payload = tin.get("command") or tin.get("file_path") or json.dumps(tin)
    body = (
        f"---\n"
        f"status: awaiting-approval\n"
        f"kind: approval\n"
        f"run_id: \"{run_id}\"\n"
        f"red_category: {category}\n"
        f"tool: {env.get('tool_name', '')}\n"
        f"agent_id: \"{env.get('agent_id', '') or ''}\"\n"
        f"agent_type: \"{env.get('agent_type', '') or ''}\"\n"
        f"created: {date.today().isoformat()}\n"
        f"---\n\n"
        f"# Deferred RED action -- human approval required\n\n"
        f"**Reason:** {reason}\n\n"
        f"**cwd:** `{os.getcwd()}`\n\n"
        f"**Replayable payload:**\n\n```\n{payload}\n```\n\n"
        f"To approve: review the above, then run the command yourself.\n"
    )
    with open(tmp, "w") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp, final)
    return fname


def emit_deny(reason_text):
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason_text,
        }
    }
    print(json.dumps(out))


def main():
    if os.environ.get("FIREBREAK_TRACE"):
        # Test hook: lets the gate's unit test prove the fast-path did NOT
        # spawn python on a GREEN call. No effect in production (unset).
        sys.stderr.write("CLASSIFIER_RAN\n")
    raw = sys.stdin.read()
    try:
        env = json.loads(raw) if raw.strip() else {}
    except Exception:
        # Unparseable envelope on a forwarded call -> fail closed.
        emit_deny("FIREBREAK_DEFERRED: unparseable hook input. Do not retry.")
        return 0

    sentinel_path = find_sentinel()
    if not sentinel_path:
        return 0  # no-op: manual session, firebreak inactive
    try:
        with open(sentinel_path) as f:
            sentinel = json.load(f)
    except Exception:
        sentinel = {}

    try:
        decision, category, reason = classify(env, sentinel)
    except Exception as exc:  # fail-closed
        decision, category, reason = "deny", "fail-closed", f"classifier error: {exc!r}"

    if decision == "allow":
        return 0

    record = None
    try:
        record = write_approval_record(sentinel, env, category or "unknown", reason)
    except Exception as exc:
        sys.stderr.write(f"FIREBREAK_RECORD_WRITE_FAILED: {exc!r}\n")

    where = f"todos/approvals/{record}" if record else \
        "todos/approvals/ (RECORD_WRITE_FAILED)"
    emit_deny(f"FIREBREAK_DEFERRED: {category} -> {where}. Do not retry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
