# Sawmill Development Container
# Used for sandboxed autonomous development loops

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Claude Code CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI via npm
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user for safety (do this early so we can set up home dir)
RUN useradd -m -s /bin/bash developer

# Set up working directory
WORKDIR /workspace

# Copy requirements first for layer caching
COPY pyproject.toml ./
COPY README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir textual tomli tomli-w pydantic pytest pytest-asyncio rich-click

# Copy the rest of the project
COPY . .

# Fix ownership
RUN chown -R developer:developer /workspace

# Switch to non-root user
USER developer

# Create .claude directory (will be mounted over at runtime)
RUN mkdir -p /home/developer/.claude

# Set environment variables
ENV PYTHONPATH=/workspace
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/developer

# Default command - can be overridden
CMD ["bash"]
