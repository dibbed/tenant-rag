# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/appuser \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged runtime user
RUN useradd -m -u 10001 -s /bin/bash appuser

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . .

# Create application & cache directories and set non-root ownership
RUN mkdir -p /home/appuser/.cache/huggingface /app/data/vector_stores /app/data/tenants /app/logs \
    && chown -R appuser:appuser /home/appuser /app

# Switch to unprivileged runtime user
USER appuser

# Expose HTTP API port
EXPOSE 8000

# Health check against FastAPI endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
