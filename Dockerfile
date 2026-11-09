# =============================================================================
# PayFlow AI - Multi-Stage Dockerfile
# =============================================================================
# This Dockerfile uses multi-stage builds to minimize the final image size.
# Stage 1 (builder): Compiles dependencies and installs heavy packages
# Stage 2 (runtime): Minimal runtime image with only what's needed
#
# Build args:
#   SERVICE: Which service to run (api, app, webhook)
#   ENVIRONMENT: dev or prod
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies for compiling Python packages
# These are needed for packages like numpy, pandas, cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only requirements first (better layer caching)
# This layer is cached unless requirements.txt changes
COPY requirements.txt .

# Create virtual environment in a known location
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install dependencies
# Using --no-cache-dir keeps the image smaller
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime - Minimal image with application
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

# Metadata labels (OCI image spec)
LABEL maintainer="Sara <sara@example.com>" \
      org.opencontainers.image.title="PayFlow AI" \
      org.opencontainers.image.description="Enterprise Financial Analytics Platform" \
      org.opencontainers.image.version="4.0.0" \
      org.opencontainers.image.authors="Sara" \
      org.opencontainers.image.vendor="PayFlow AI"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    # Default service (can be overridden)
    SERVICE="api" \
    # Default environment
    ENVIRONMENT="production" \
    # Default port
    PORT="8000"

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    # Required for some ML libraries at runtime
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy virtual environment from builder stage
# This is the key to multi-stage builds - we get compiled packages
# without the build tools
COPY --from=builder /opt/venv /opt/venv

# Copy Docker helper scripts
COPY --chown=appuser:appuser docker/healthcheck.sh /healthcheck.sh
COPY --chown=appuser:appuser docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /healthcheck.sh /entrypoint.sh

# Copy application code
# .dockerignore will exclude unnecessary files
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/htmlcov && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports for different services
EXPOSE 8000 8001 8501

# Health check - runs every 30 seconds
# Start period gives the app time to initialize (especially for ML models)
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD /healthcheck.sh

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command - can be overridden by docker-compose
CMD ["/entrypoint.sh"]