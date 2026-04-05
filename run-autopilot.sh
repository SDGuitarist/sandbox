#!/bin/bash
set -e

CLAUDE_HOME="/home/claude-user"

# Build the container (only needed first time or after Dockerfile changes)
docker build -t claude-sandbox ~/Projects/sandbox

# Run Claude Code as non-root user inside the container.
#
# Mounts your config read-only, only /workspace is writable.
# Type /autopilot "description" then walk away.

docker run --rm -it \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v ~/Projects/sandbox:/workspace:rw \
  -v ~/.claude/plugins:$CLAUDE_HOME/.claude/plugins:ro \
  -v ~/.claude/skills:$CLAUDE_HOME/.claude/skills:ro \
  -v ~/.claude/agents:$CLAUDE_HOME/.claude/agents:ro \
  -v ~/.claude/hooks:$CLAUDE_HOME/.claude/hooks:ro \
  -v ~/.claude/commands:$CLAUDE_HOME/.claude/commands:ro \
  -v ~/.claude/settings.json:$CLAUDE_HOME/.claude/settings.json:ro \
  -v ~/.claude/CLAUDE.md:$CLAUDE_HOME/.claude/CLAUDE.md:ro \
  -w /workspace \
  claude-sandbox \
  --dangerously-skip-permissions
