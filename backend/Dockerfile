# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS base

# Install system deps needed by Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser (Chromium only — keeps image size reasonable)
RUN playwright install --with-deps chromium

COPY app/ ./app/

# Data volume mountpoint — SQLite DB lives here
VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
