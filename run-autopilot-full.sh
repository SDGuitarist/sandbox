#!/bin/bash
set -euo pipefail

IMAGE_NAME="claude-sandbox"
CLAUDE_HOME="/home/claude-user"

if [ $# -ne 1 ]; then
  echo "Usage: $0 /absolute/path/to/project"
  exit 1
fi

PROJECT_PATH="$(cd "$1" && pwd)"

if [ ! -d "$PROJECT_PATH" ]; then
  echo "Project path does not exist: $PROJECT_PATH"
  exit 1
fi

case "$PROJECT_PATH" in
  "$HOME/Projects/sandbox"/*) ;;
  *)
    echo "Project path must be inside ~/Projects/sandbox"
    exit 1
    ;;
esac

: "${AUTOPILOT_ANTHROPIC_KEY:?Set AUTOPILOT_ANTHROPIC_KEY first}"

docker build -t "$IMAGE_NAME" "$HOME/Projects/sandbox"

docker run --rm -it \
  --name claude-full \
  -e ANTHROPIC_API_KEY="$AUTOPILOT_ANTHROPIC_KEY" \
  -e APIFY_TOKEN="${AUTOPILOT_APIFY_TOKEN:-}" \
  -e HUNTER_API_KEY="${AUTOPILOT_HUNTER_API_KEY:-}" \
  -v "$PROJECT_PATH:/workspace:rw" \
  -v "$HOME/.claude/plugins:$CLAUDE_HOME/.claude/plugins:ro" \
  -v "$HOME/.claude/skills:$CLAUDE_HOME/.claude/skills:ro" \
  -v "$HOME/.claude/agents:$CLAUDE_HOME/.claude/agents:ro" \
  -v "$HOME/.claude/hooks:$CLAUDE_HOME/.claude/hooks:ro" \
  -v "$HOME/.claude/commands:$CLAUDE_HOME/.claude/commands:ro" \
  -v "$HOME/.claude/settings.json:$CLAUDE_HOME/.claude/settings.json:ro" \
  -v "$HOME/.claude/CLAUDE.md:$CLAUDE_HOME/.claude/CLAUDE.md:ro" \
  -v "$HOME/.claude/docs:$CLAUDE_HOME/.claude/docs:rw" \
  -v "$HOME/.claude/projects:$CLAUDE_HOME/.claude/projects:rw" \
  -v "$HOME/Documents/dev-notes:/home/claude-user/Documents/dev-notes:rw" \
  -w /workspace \
  "$IMAGE_NAME" \
  --dangerously-skip-permissions
