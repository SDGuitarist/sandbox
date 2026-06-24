#!/usr/bin/env bash
#
# G1 firebreak -- cheap entry gate (R6). Invoked as the SINGLE PreToolUse hook
# command: `bash .claude/hooks/firebreak-gate.sh`. Reads the PreToolUse JSON
# envelope on stdin and forwards to the python classifier ONLY when a RED marker
# is present; otherwise fast-path exit 0 so the bulk of GREEN actions never pay
# python's cold-start (~30-80ms x thousands of calls).
#
# Design: extract tool_name, then for Bash extract the COMMAND value and match
# markers against THAT (not the raw JSON). This lets the gate safely forward
# brace/backslash command-word obfuscation (`c{u,}rl`, `\cu\rl`) and direct
# script-path argv0 (`./x`, `/abs/x`, `path/to/x`) WITHOUT the raw-JSON `{`
# collision that previously forced those checks into the python layer.
#
# Marker matching is deliberately a SUPERSET of what the classifier denies:
# over-forwarding only costs a python cold-start; under-forwarding would let a
# RED action through unseen. For Write/Edit only the file_path is inspected --
# never the file `content` -- so writing code that mentions "python"/"curl"
# stays GREEN.

set -u
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
input="$(cat)"

forward() {
  printf '%s' "$input" | python3 "$HOOK_DIR/firebreak-classify.py"
  exit $?
}

tool_name="$(printf '%s' "$input" \
  | sed -n 's/.*"tool_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"

case "$tool_name" in
  Bash)
    # Everything after `"command": "` (value + trailing JSON tail). Over-capture
    # is safe; crucially this EXCLUDES the envelope's structural `{`, so a literal
    # `{` here means brace-expansion in the command itself. A real command
    # backslash is JSON-escaped to `\\` (two chars) -- distinct from an escaped
    # quote `\"` -- so we match `\\`, not bare `\`.
    cmd="$(printf '%s' "$input" \
      | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"//p' | head -1)"

    # Direct script-path argv0 (after optional VAR= assignments): ./x /abs path/to/x
    if printf '%s' "$cmd" | grep -Eq \
      '^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*(\.?/|[^[:space:]/]+/)'; then
      forward
    fi

    printf '%s' "$cmd" | grep -qiF \
      -e '$' -e '`' -e '~' -e '..' -e '{' -e '\\' \
      -e '.claude' -e 'settings.json' -e 'firebreak' -e 'todos/approvals' \
      -e 'mcp__' \
      -e 'curl' -e 'wget' -e 'ssh' -e 'scp' -e 'sftp' -e 'telnet' \
      -e 'nc ' -e 'ncat' -e 'rsync' -e 'gh ' \
      -e 'vercel' -e 'railway' -e 'flyctl' -e 'fly ' -e 'netlify' \
      -e 'wrangler' -e 'terraform' -e 'kubectl' -e 'heroku' -e 'aws ' -e 'gcloud' \
      -e 'push' -e 'force' -e 'filter-repo' -e 'filter-branch' -e 'alias.' \
      -e 'uninstall' -e 'publish' -e ' remove' \
      -e 'python' -e 'node' -e 'ruby' -e 'perl' -e 'eval' -e 'source ' \
      -e 'npm run' -e 'make' -e '.sh' -e '.venv' -e 'bash ' -e 'sh ' \
      -e 'rm ' -e 'unlink' -e 'shred' -e 'rmdir' -e '-delete' -e 'truncate' \
      -e 'cp ' -e 'mv ' -e 'ln ' -e 'dd ' -e 'tee ' -e 'sed ' -e 'install' \
      -e 'flock' -e 'timeout' -e 'nohup' -e 'setsid' -e 'unshare' -e 'doas' \
      -e 'sudo' -e 'xargs' -e 'nice ' -e 'ionice' -e 'chrt' -e 'stdbuf' \
      -e 'setarch' -e 'parallel' -e 'watch ' -e 'env ' -e 'command ' \
      -e 'npx' -e 'bunx' -e 'base64' -e 'deno' -e 'dlx' -e 'pipx' \
      -e 'ext::' -e 'fd::' \
      -e '> /' -e '>/' \
      -e ';' -e '&&' -e '||' -e '|' -e '& ' -e '(' \
      -e "''" -e '\"\"' \
      && forward
    exit 0
    ;;

  Write|Edit|MultiEdit|NotebookEdit)
    val="$(printf '%s' "$input" \
      | grep -oE '"(file_path|notebook_path|path)"[[:space:]]*:[[:space:]]*"[^"]*"' \
      | head -1 | sed -E 's/.*:[[:space:]]*"//; s/"$//')"
    # Absolute / home / env-rooted destinations need the classifier's worktree +
    # control-plane checks (e.g. $HOME/evil.txt is out-of-worktree).
    case "$val" in
      /*|'~'*|'$'*) forward ;;
    esac
    printf '%s' "$val" | grep -qiF \
      -e '.claude' -e 'settings.json' -e 'firebreak' -e 'todos/approvals' -e '..' \
      && forward
    exit 0
    ;;

  mcp__*)
    forward
    ;;
esac

exit 0
