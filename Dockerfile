# JARVIS — Multi-agent AI assistant
# Used by docker-compose.yaml for homelab deployment (Scenario B)

FROM python:3.13-slim AS base

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY packages/ packages/
COPY apps/ apps/
COPY config/ config/
COPY data/context/ data/context/

# Default: run the CLI
CMD ["uv", "run", "python", "-m", "apps.cli.main"]
