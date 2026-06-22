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
    "git", "gh", "npm", "pnpm", "yarn", "pip", "pip3", "pipx", "docker",
    "cargo", "go", "aws", "gcloud", "kubectl", "heroku", "flyctl", "wrangler",
    "terraform", "rsync",
}

# F13 exec-wrappers to recurse through to the real command word
WRAPPERS = {
    "env", "nice", "nohup", "timeout", "xargs", "command", "exec", "setsid",
    "stdbuf", "time", "sudo", "doas", "chroot", "unshare", "flock", "script",
    "setarch", "watch", "parallel", "ionice", "chrt",
}
# wrappers that consume one positional argument before the real command
WRAPPER_TAKES_ARG = {"timeout", "nice", "flock", "stdbuf", "setarch", "ionice",
                     "chrt", "parallel", "watch"}

# Bash write verbs that can target the control plane (F1 + F9)
CP_WRITE_VERBS = {"rm", "mv", "cp", "install", "ln", "dd", "truncate", "tee", "sed"}
# verbs whose destination is arbitrary -> a fully-opaque dest defers (F9c)
ARBITRARY_DEST_VERBS = {"cp", "install", "ln", "dd", "mv", "sed", "truncate"}

DELETE_VERBS = {"rm", "unlink", "shred", "rmdir"}

# Indirection set (F2 + F7): defer unless it structurally matches a framework
INTERPRETERS = {"python", "python3", "node", "ruby", "perl", "bash", "sh",
                "zsh", "dash", "ksh"}

# mcp__* read-only verb prefixes (everything else defers -- R4d)
MCP_READONLY_PREFIXES = (
    "get", "list", "search", "read", "download", "query", "resolve", "check",
    "inspect", "describe", "show", "fetch", "wait_for", "help", "view", "find",
    "count", "status",
)

# opacity: command-substitution / backtick / $VAR / ${...} / brace-expansion /
# backslash-escape. (Brace/backslash MUST be checked here in the classifier on the
# isolated command -- NOT in the cheap gate, which greps raw JSON that always has
# "{". Step-0 Phase-1 constraint.)
OPAQUE_RE = re.compile(r"\$\(|`|\$\{|\$[A-Za-z_]|[{}]|\\")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WHICH_RE = re.compile(r"^\$\(which\s+([A-Za-z0-9_./-]+)\)$")


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
    """realpath-resolved (defeats symlink/traversal); covers ~ / $HOME expansion."""
    if path is None:
        return False
    rp = realpath(path)
    norm = rp.replace("\\", "/")
    base = os.path.basename(norm)
    if rp == GLOBAL_SETTINGS:
        return True
    if "/.claude/hooks/" in norm and base.startswith("firebreak-") and \
            (base.endswith(".py") or base.endswith(".sh")):
        return True
    if base == "firebreak-active.json" and "/.claude/" in norm:
        return True
    if "/todos/approvals/" in norm or norm.endswith("/todos/approvals"):
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


def base_name(tok):
    return os.path.basename(strip_quotes(tok))


def is_opaque(token):
    return token is not None and bool(OPAQUE_RE.search(token))


def resolve_argv0(words, sentinel):
    """Skip leading VAR= assignments and exec-wrappers; return (argv0, rest)."""
    idx = 0
    while idx < len(words) and ASSIGN_RE.match(words[idx]):
        idx += 1
    # recurse through exec-wrappers
    while idx < len(words):
        base = base_name(words[idx])
        if base in WRAPPERS:
            idx += 1
            while idx < len(words) and words[idx].startswith("-"):
                idx += 1
            if base == "env":
                while idx < len(words) and ASSIGN_RE.match(words[idx]):
                    idx += 1
            elif base in WRAPPER_TAKES_ARG and idx < len(words) \
                    and not words[idx].startswith("-") \
                    and base_name(words[idx]) not in WRAPPERS \
                    and not is_opaque(words[idx]):
                idx += 1  # consume the wrapper's positional arg (duration/file/N)
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


def extract_nested_commands(words):
    """Command strings handed to a `-c` flag -- `sh -c '<cmd>'`, `bash -c`,
    `flock /tmp/l -c '<cmd>'`, `timeout 5 sh -c '<cmd>'`, etc. The real action
    lives inside the string, so the classifier must recurse into it. (`python -c`
    runs python, not a shell command, but the top-level interpreter check already
    defers it -- a harmless extra recursion.)"""
    out = []
    for i in range(len(words) - 1):
        if strip_quotes(words[i]) == "-c":
            out.append(strip_quotes(words[i + 1]))
    return out


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
    nrest = git_normalized_rest(rest)
    verb = nrest[0] if nrest else None
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
        verb = first_verb(rest)
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
    """Targets of > / >> redirections (truncating/appending writes)."""
    return [strip_quotes(m.group(1))
            for m in re.finditer(r">>?\s*(\"[^\"]*\"|'[^']*'|[^\s|;&<>]+)", cmd)]


def positional_args(rest):
    return [strip_quotes(w) for w in rest
            if not w.startswith("-") and not ASSIGN_RE.match(w)]


def bash_control_plane(words, cmd, identity, repo_root, sentinel):
    """F1 + F9: control-plane / out-of-repo / opaque write verb."""
    argv0, rest = resolve_argv0(words, sentinel)
    if argv0 is None:
        return None
    a0 = base_name(argv0)
    targets = []
    if a0 in CP_WRITE_VERBS:
        targets += positional_args(rest)
    targets += redirection_targets(cmd)        # >, >> apply to any verb
    if not targets:
        return None

    for t in targets:
        # control-plane path -> trusted allowed, worker denied
        if is_control_plane(t):
            if identity in TRUSTED:
                return None
            return "control-plane"
        # F9: control-plane-capable verb to escaping / opaque destination
        if a0 in CP_WRITE_VERBS and identity not in TRUSTED:
            if is_opaque(t) and a0 in ARBITRARY_DEST_VERBS:
                return "control-plane"   # fully-opaque arbitrary dest (F9c)
            if not inside_worktree(t, repo_root) and not under_tmp(t):
                return "control-plane"   # escaping / non-worktree dest (F9b)
    return None


def bash_destructive(words, cmd, repo_root, sentinel):
    """Data deletes and out-of-repo deletes (errs toward defer)."""
    argv0, rest = resolve_argv0(words, sentinel)
    if argv0 is None:
        return None
    a0 = base_name(argv0)
    if a0 == "find" and ("-delete" in rest or "-exec" in rest):
        return "out-of-repo-delete"
    if a0 not in DELETE_VERBS and a0 != "truncate":
        return None
    for t in positional_args(rest):
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
        for w in rest:
            wv = strip_quotes(w)
            if wv.startswith(("http://", "https://", "ftp://")):
                host = re.sub(r"^[a-z]+://", "", wv).split("/")[0].split(":")[0]
                if host not in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                    return "external-send"
        return None
    if a0 in ("nc", "ncat", "ssh", "scp", "sftp", "telnet"):
        return "external-send"
    if a0 == "rsync":
        if any(":" in strip_quotes(w) and not strip_quotes(w).startswith("-")
               for w in rest):
            return "external-send"
        return None
    if a0 == "gh":
        verb = first_verb(rest)
        if verb in ("api", "release", "pr", "gist", "repo", "secret",
                    "workflow", "run", "issue"):
            return "external-send"
        return None
    if a0 in ("aws", "gcloud"):
        return "external-send"

    # deploy
    if a0 in ("vercel", "railway", "fly", "flyctl", "netlify", "wrangler", "heroku"):
        return "deploy"
    if a0 == "terraform" and first_verb(rest) in ("apply", "destroy"):
        return "deploy"
    if a0 == "kubectl":
        return "deploy"

    # packages
    if a0 in ("pip", "pip3") and first_verb(rest) == "uninstall":
        return "package"
    if a0 in ("npm", "pnpm", "yarn"):
        if first_verb(rest) in ("uninstall", "remove", "rm", "publish"):
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
    if a0 in ("npm", "pnpm", "yarn") and first_verb(rest) == "run":
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


def classify_bash_command(cmd, identity, repo_root, sentinel, depth=0):
    """Full Bash classification -> RED category or None. Recurses into nested
    `-c` command strings (sh/bash/flock -c '<cmd>') and git `!`-aliases so the
    real action behind a listed exec-wrapper or alias cannot evade the denylist."""
    if depth > 4:                       # runaway nesting -> fail closed
        return "fail-closed"
    words = shell_words(cmd)
    for inner in extract_nested_commands(words):
        c = classify_bash_command(inner, identity, repo_root, sentinel, depth + 1)
        if c:
            return c
    if identity == "worker":            # F13 first -- short-circuits
        c = f13_opaque_defer(words, sentinel)
        if c:
            return c
    c = bash_control_plane(words, cmd, identity, repo_root, sentinel)
    if c:
        return c
    c = bash_destructive(words, cmd, repo_root, sentinel)
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
