#!/usr/bin/env bash
#
# plan-review.sh -- Send a plan to Codex for external review.
#
# Usage:
#   ./scripts/plan-review.sh path/to/plan.md
#   ./scripts/plan-review.sh path/to/plan.md --output codex-review.md
#
# Requires: codex CLI installed and authenticated.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/prompts/plan-review.md"

# --- Parse arguments ---
PLAN_FILE=""
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output|-o)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 <plan-file> [--output <output-file>]"
      echo ""
      echo "Send a plan to Codex for external review."
      echo "If no plan file is given, reads from stdin."
      exit 0
      ;;
    *)
      PLAN_FILE="$1"
      shift
      ;;
  esac
done

# --- Read plan content ---
if [[ -n "$PLAN_FILE" ]]; then
  if [[ ! -f "$PLAN_FILE" ]]; then
    echo "Error: Plan file not found: $PLAN_FILE" >&2
    exit 1
  fi
  PLAN_CONTENT="$(cat "$PLAN_FILE")"
else
  if [[ -t 0 ]]; then
    echo "Error: No plan file given and nothing on stdin." >&2
    echo "Usage: $0 <plan-file> [--output <output-file>]" >&2
    exit 1
  fi
  PLAN_CONTENT="$(cat)"
fi

# --- Read review prompt ---
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Error: Review prompt not found: $PROMPT_FILE" >&2
  exit 1
fi
REVIEW_PROMPT="$(cat "$PROMPT_FILE")"

# --- Build the full prompt ---
FULL_PROMPT="$(printf '%s\n\n---\n\n# Plan to Review\n\n%s' "$REVIEW_PROMPT" "$PLAN_CONTENT")"

# --- Run Codex ---
echo "Sending plan to Codex for review..." >&2

if [[ -n "$OUTPUT_FILE" ]]; then
  codex exec "$FULL_PROMPT" > "$OUTPUT_FILE"
  echo "Review saved to: $OUTPUT_FILE" >&2
else
  codex exec "$FULL_PROMPT"
fi
