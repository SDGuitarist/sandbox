#!/usr/bin/env bash
#
# G1 firebreak -- cheap entry gate (R6). Invoked as the SINGLE PreToolUse hook
# command: `bash .claude/hooks/firebreak-gate.sh`. Reads the PreToolUse JSON
# envelope on stdin and forwards to the python classifier ONLY when an
# envelope-safe RED marker is present; otherwise fast-path exit 0 so the bulk of
# GREEN actions never pay python's cold-start (~30-80ms x thousands of calls).
#
# Step-0 Phase-1 constraint: match ONLY envelope-safe markers here. Brace `{` and
# backslash `\` command-word obfuscation are NOT matched in this gate -- the raw
# JSON envelope always contains `{`, which would collapse the fast-path. Those are
# detected in the python classifier AFTER the command value is isolated.
#
# Marker matching is deliberately a SUPERSET of what the classifier denies
# (over-forwarding is safe and cheap; under-forwarding would miss a RED action).
# For Write/Edit only the extracted file_path is inspected -- never the file
# `content` -- so writing code that merely mentions "python"/"curl" stays GREEN.

set -u
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
input="$(cat)"

forward() {
  printf '%s' "$input" | python3 "$HOOK_DIR/firebreak-classify.py"
  exit $?
}

emit() { printf '%s' "$input"; }

# Bash fixed-string markers (case-insensitive, substring -- over-forward is safe).
# Includes envelope-safe opacity ($ / backtick / ${ are all matched by `$` and the
# backtick), path/control-plane suspects, outward verbs, indirection, write/delete
# verbs, and absolute-redirect forms.
bash_markers() {
  emit | grep -qiF \
    -e '$' -e '`' -e '~' -e '..' \
    -e '.claude' -e 'settings.json' -e 'firebreak' -e 'todos/approvals' \
    -e 'mcp__' \
    -e 'curl' -e 'wget' -e 'ssh' -e 'scp' -e 'sftp' -e 'telnet' \
    -e 'nc ' -e 'ncat' -e 'rsync' -e 'gh ' \
    -e 'vercel' -e 'railway' -e 'flyctl' -e 'fly ' -e 'netlify' \
    -e 'wrangler' -e 'terraform' -e 'kubectl' -e 'heroku' -e 'aws ' -e 'gcloud' \
    -e 'push' -e 'force' -e 'filter-repo' -e 'filter-branch' \
    -e 'uninstall' -e 'publish' \
    -e 'python' -e 'node' -e 'ruby' -e 'perl' -e 'eval' -e 'source ' \
    -e 'npm run' -e 'make' -e '.sh' -e '.venv' -e 'bash ' -e 'sh ' \
    -e 'rm ' -e 'unlink' -e 'shred' -e 'rmdir' -e '-delete' -e 'truncate' \
    -e 'cp ' -e 'mv ' -e 'ln ' -e 'dd ' -e 'tee ' -e 'sed ' -e 'install' \
    -e '> /' -e '>/'
}

tool='"tool_name"[[:space:]]*:[[:space:]]*'

if emit | grep -Eq "${tool}\"Bash\""; then
  bash_markers && forward
  exit 0
fi

if emit | grep -Eq "${tool}\"(Write|Edit|MultiEdit|NotebookEdit)\""; then
  val="$(emit | grep -oE '"(file_path|notebook_path|path)"[[:space:]]*:[[:space:]]*"[^"]*"' \
        | head -1 | sed -E 's/.*:[[:space:]]*"//; s/"$//')"
  case "$val" in
    /*|'~'*) forward ;;
  esac
  printf '%s' "$val" | grep -qiF \
    -e '.claude' -e 'settings.json' -e 'firebreak' -e 'todos/approvals' -e '..' \
    && forward
  exit 0
fi

if emit | grep -Eq "${tool}\"mcp__"; then
  forward
fi

exit 0
