# ─────────────────────────────────────────────────────────────────────────────
# AutoPost Bot — Production Dockerfile
# Optimized for Render.com deployment (webhook mode)
# Multi-stage build: keeps final image lean
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools + Pillow system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies into isolated prefix
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="AutoPost Bot"
LABEL description="Telegram AutoPost Generator Bot — Render Webhook Edition"

WORKDIR /app

# Runtime system deps only (no dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    zlib1g \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# ── Setup runtime directories & font ──────────────────────────────────────────
RUN mkdir -p assets/fonts assets/overlays temp logs && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf assets/fonts/ 2>/dev/null || \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf       assets/fonts/DejaVuSans-Bold.ttf 2>/dev/null || \
    echo "WARNING: DejaVu font not found — watermark text may use fallback font"

# ── Non-root user for security ─────────────────────────────────────────────────
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# ── Health check (Render hits /health every 30s) ──────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# ── Expose webhook port (Render injects $PORT env var) ────────────────────────
EXPOSE 8080

# ── Entrypoint: webhook webserver ─────────────────────────────────────────────
CMD ["python", "webserver.py"]
