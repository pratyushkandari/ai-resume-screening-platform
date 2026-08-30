# =============================================================================
#  Backend Dockerfile - Multi-Stage, Non-Root Production Image
# =============================================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

# Install system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create unprivileged user for secure execution
RUN addgroup --system appgroup && adduser --system --group appuser \
    && mkdir -p uploads /tmp/hf_cache /tmp/torch_cache \
    && chown -R appuser:appgroup /app /tmp/hf_cache /tmp/torch_cache \
    && chmod -R 777 /tmp/hf_cache /tmp/torch_cache

ENV HOME=/home/appuser \
    HF_HOME=/tmp/hf_cache \
    TRANSFORMERS_CACHE=/tmp/hf_cache \
    TORCH_HOME=/tmp/torch_cache

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

