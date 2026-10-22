# =============================================================================
#  Backend image: multi-stage build, CPU-only PyTorch, non-root runtime user.
#  Build:  docker build -t resume-screener-backend ./backend
#  Set PRELOAD_MODEL=0 to skip baking the embedding model into the image.
# =============================================================================
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

# Download the embedding model at build time so containers start offline.
ARG PRELOAD_MODEL=1
ENV HF_HOME=/opt/hf-cache
RUN if [ "$PRELOAD_MODEL" = "1" ]; then \
      python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"; \
    else mkdir -p /opt/hf-cache; fi


FROM python:3.11-slim AS runtime

# FORWARDED_ALLOW_IPS: only proxies on private networks (Nginx container, ingress,
# PaaS router) may set the client IP via X-Forwarded-For. Trusting "*" would let
# any client spoof its IP and bypass the login rate limit.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/hf-cache \
    UPLOAD_DIR=/app/uploads \
    FORWARDED_ALLOW_IPS="127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf-cache /opt/hf-cache
WORKDIR /app
COPY --chown=app:app app ./app
COPY --chown=app:app manage.py ./
RUN mkdir -p /app/uploads && chown app:app /app/uploads

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# --proxy-headers: read the client IP from X-Forwarded-For set by a trusted proxy (see FORWARDED_ALLOW_IPS).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
