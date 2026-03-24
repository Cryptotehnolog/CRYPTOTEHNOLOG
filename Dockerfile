# ==================== CRYPTOTEHNOLOG Python Service Dockerfile ====================
# Multi-stage build for optimized image size

ARG PYTHON_BASE_IMAGE=python:3.12-slim
ARG APP_VERSION=1.22.0

# ==================== Stage 1: Builder ====================
FROM ${PYTHON_BASE_IMAGE} AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install
COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==================== Stage 2: Runtime ====================
FROM ${PYTHON_BASE_IMAGE} AS runtime

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 cryptotechnolog && \
    mkdir -p /app /app/logs /app/data && \
    chown -R cryptotechnolog:cryptotechnolog /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=cryptotechnolog:cryptotechnolog src/ /app/src/
COPY --chown=cryptotechnolog:cryptotechnolog config/ /app/config/
COPY --chown=cryptotechnolog:cryptotechnolog pyproject.toml /app/

# Switch to non-root user
USER cryptotechnolog
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command
CMD ["python", "-m", "cryptotechnolog.main"]

# Labels
LABEL maintainer="CRYPTOTEHNOLOG Team" \
      version="${APP_VERSION}" \
      description="Institutional-Grade Crypto Trading Platform"
