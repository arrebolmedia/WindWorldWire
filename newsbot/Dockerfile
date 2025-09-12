# Multi-stage build for NewsBot services
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

FROM base as development

# Copy source code
COPY . .

# Install package in development mode
RUN uv pip install -e .

# Create non-root user
RUN useradd --create-home --shell /bin/bash newsbot
USER newsbot

# Service-specific setup
ARG SERVICE_NAME
ENV SERVICE_NAME=${SERVICE_NAME}

# Default command (will be overridden by docker-compose)
CMD ["python", "-m", "uvicorn", "--help"]

FROM development as production

# Production optimizations
ENV ENVIRONMENT=production

# Switch back to root for final setup
USER root

# Remove development dependencies and clean up
RUN uv pip uninstall -y pytest pytest-asyncio pytest-cov black ruff mypy \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Switch back to non-root user
USER newsbot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT:-8000}/healthz || exit 1

# Default command
CMD ["python", "-m", "newsbot.services.${SERVICE_NAME}.main"]