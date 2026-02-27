# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libfreetype6-dev libjpeg62-turbo-dev libpng-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
LABEL name="CosmicBotz" description="AutoPost Generator — Pyrofork Edition"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 libjpeg62-turbo libpng16-16 zlib1g fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY . .
RUN mkdir -p assets/fonts temp && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf assets/fonts/ 2>/dev/null || true
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser
CMD ["python", "main.py"]
