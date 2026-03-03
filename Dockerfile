FROM python:3.11-slim

WORKDIR /app

# System dependencies for Pillow + TgCrypto
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    libfreetype6-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    zlib1g-dev \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Font for thumbnails
RUN mkdir -p assets/fonts temp && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf assets/fonts/ 2>/dev/null || true && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf assets/fonts/ 2>/dev/null || true

CMD ["python", "main.py"]