#!/usr/bin/env bash
# Sensitive-file filesystem scan for the advisory audit.
# Catches files that .gitignore intentionally hides.
# Used by autopilot Step 1.55 (baseline) and Advisory Audit (post-run diff).
#
# Usage: bash scripts/sensitive-file-scan.sh [root_dir]
# Defaults to current directory if no argument given.

ROOT="${1:-.}"

find "$ROOT" -type f \( \
  -name '.env' -o -name '.env.*' \
  -o -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \
  -o -name '*.csv' -o -name '*.jsonl' \
  -o -name '*.pem' -o -name '*.key' -o -name '*.p12' -o -name '*.pfx' -o -name '*.p8' -o -name '*.crt' \
  -o -name 'credentials.json' -o -name '*-credentials.json' -o -name '*-service-account.json' \
  -o -name '.npmrc' -o -name 'kubeconfig' \
  -o -name '*.tfstate' -o -name '*.tfstate.backup' -o -name '*.tfvars' \
  -o -name '.docker/config.json' \
\) \
  -not -path '*/.git/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/.venv/*' \
  -not -path '*/venv/*' \
  -not -path '*/.next/*' \
  -not -path '*/dist/*' \
  -not -path '*/build/*' \
  -not -path '*/.claude/worktrees/*' \
  -not -name '.env.example'
