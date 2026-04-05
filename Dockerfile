FROM node:20-alpine

# System dependencies (libgcc/libstdc++ needed for native binary on Alpine)
RUN apk add --no-cache git curl bash ripgrep libgcc libstdc++ ca-certificates perl jq shadow python3 py3-pip

# Create non-root user
RUN useradd -m -s /bin/bash claude-user

# Switch to non-root user before installing
USER claude-user

# Install Claude Code via native installer (not npm)
RUN curl -fsSL https://claude.ai/install.sh | bash

# Tell Claude Code to use system ripgrep instead of bundled
ENV USE_BUILTIN_RIPGREP=0

# Don't auto-update inside container
ENV DISABLE_AUTOUPDATER=1

# Add claude to PATH
ENV PATH="/home/claude-user/.local/bin:$PATH"

# Workspace
WORKDIR /workspace

ENTRYPOINT ["claude"]
