# 🚀 Production Deployment Guide

This guide covers deploying the RAGBot API backend across development, staging, and production environments.

---

## 1. Deployment Architecture

```text
               Internet / Clients
                       ↓
         Reverse Proxy (Nginx / Cloudflare)
         - SSL/TLS Termination
         - Client IP Forwarding (X-Forwarded-For)
         - Request Buffering
                       ↓
         ASGI Application Server (Uvicorn)
         - Process Manager / Multiple Workers
         - FastAPI Application Instance
         - Edge protection: trusted proxies, CORS allowlist,
           rate limits, request size limit
                       ↓
         Persistent Storage & Databases
         - ./data/vector_store (FAISS index files)
         - ./cache/sentence_transformers (Downloaded models)
         - Redis Server (Optional L2 Cache)
```

---

## 2. Server Prerequisites & Environment

- **Operating System**: Linux (Ubuntu 22.04+ recommended) or Windows Server
- **Python**: 3.10, 3.11, or 3.12
- **Memory**:
  - Minimum: 4 GB RAM (with SentenceTransformers e5-small-v2 on CPU)
  - Recommended: 8 GB+ RAM for high-concurrency ingestion and vector search
- **Disk**: 10 GB+ SSD storage for vector stores and cached embeddings

### Environment Variables (`.env`)

Create a production `.env` file based on `env.example`:

```env
# Server Binding
HOST=0.0.0.0
PORT=8000
WORKERS=4
RELOAD=false

# LLM Configuration
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-prod-your-openai-api-key-here
LLM_TEMPERATURE=0.3
LLM_TIMEOUT=60.0

# Embedding Configuration
EMBED_PROVIDER=sentence_transformers
EMBED_MODEL=intfloat/e5-small-v2
EMBED_BATCH_SIZE=64

# Vector Store
VECTOR_STORE_DEFAULT_STORE=faiss
VECTOR_STORE_PERSIST_PATH=./data/vector_store

# Security & Limits
SECURITY_RATE_LIMIT_REQUESTS=60
SECURITY_RATE_LIMIT_WINDOW=60
SECURITY_MAX_FILE_SIZE_MB=50
# Edge protection (docs/features/edge-protection/README.md)
SECURITY_TRUSTED_PROXIES=127.0.0.1
SECURITY_RATE_LIMIT_STORAGE_URL=redis://localhost:6379/1
SECURITY_CORS_ALLOWED_ORIGINS=https://app.example.com

# Caching & Redis (Optional)
ENABLE_REDIS=false
REDIS_URL=redis://localhost:6379/0
CACHE_TTL=3600

# Logging
LOG_LEVEL=INFO
```

---

## 3. Running with Uvicorn / Gunicorn

### Direct Uvicorn Execution

```bash
# Activate virtual environment
source venv/bin/activate

# Launch production server with 4 worker processes
uvicorn ragbot.api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --access-log \
  --no-proxy-headers
```

> **Edge protection:** the application trusts forwarded headers only from the proxies listed in `SECURITY_TRUSTED_PROXIES` (for Nginx on the same host, `127.0.0.1`). Always start uvicorn with `--no-proxy-headers`, and never use `--forwarded-allow-ips='*'`: it lets every client choose its own address. `python main.py` and the Docker image already turn off uvicorn proxy headers.

### Systemd Service Configuration (`ragbot.service`)

Create `/etc/systemd/system/ragbot.service`:

```ini
[Unit]
Description=RAGBot FastAPI Backend Server
After=network.target

[Service]
User=ragbot
Group=ragbot
WorkingDirectory=/opt/ragbot
EnvironmentFile=/opt/ragbot/.env
ExecStart=/opt/ragbot/venv/bin/uvicorn ragbot.api.app:app --host 0.0.0.0 --port 8000 --workers 4 --no-proxy-headers
Restart=always
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ragbot
sudo systemctl start ragbot
```

---

## 4. Reverse Proxy Setup (Nginx)

Place Nginx in front of Uvicorn for SSL termination, request buffering, and large file streaming:

```nginx
server {
    listen 80;
    server_name ragbot.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ragbot.example.com;

    ssl_certificate /etc/letsencrypt/live/ragbot.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ragbot.example.com/privkey.pem;

    # Document upload limits
    client_max_body_size 60M;
    client_body_timeout 120s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Keepalive and timeouts
        proxy_http_version 1.1;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
        proxy_send_timeout 60s;
    }

    # Direct access to health checks without buffering
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_buffering off;
    }
}
```

With this Nginx setup, set `SECURITY_TRUSTED_PROXIES=127.0.0.1` so that the service uses the client address that Nginx reports. Keep `client_max_body_size` a little above `SECURITY_MAX_FILE_SIZE_MB` (60M for 50 MB). If the service runs in a container behind a proxy container, trust only the proxy container's own address, and do not publish port 8000 on the host.

---

## 5. Docker Deployment

### Dockerfile Deployment

Build and run using Docker:

```bash
# Build image
docker build -t tenant-rag:latest .

# Run container
docker run -d \
  --name tenant-rag \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/cache:/home/appuser/.cache/huggingface \
  --env-file .env \
  tenant-rag:latest
```

### Docker Compose

```yaml
version: '3.8'

services:
  tenant-rag:
    build: .
    container_name: tenant-rag
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./cache:/home/appuser/.cache/huggingface
      - ./plugins:/app/plugins
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  # Optional Qdrant Vector DB
  # qdrant:
  #   image: qdrant/qdrant:latest
  #   ports:
  #     - "6333:6333"
  #   volumes:
  #     - ./data/qdrant:/qdrant/storage
```

---

## 6. Known Production Boundaries & Limitations

1. **Rate Limiting Across Workers and Instances**:
   Without `SECURITY_RATE_LIMIT_STORAGE_URL`, each Uvicorn worker process counts requests on its own, so `--workers 4` allows four times the configured limit. Set `SECURITY_RATE_LIMIT_STORAGE_URL=redis://...` to share one count across all workers and instances. If Redis is unavailable, each instance counts on its own until Redis recovers, and a warning is logged.
2. **FAISS Concurrency Model**:
   `FAISSVectorStore` handles thread-safe and async-safe concurrent access via an in-process class-level `async_lock`. It is ideal for single-node deployments. If horizontal multi-server autoscaling is needed, use a dedicated vector database server such as **Qdrant**.
3. **Hardware Isolation in CI/CD**:
   Always execute automated testing and validation with CPU isolation variables:
   ```bash
   CUDA_VISIBLE_DEVICES="" TORCH_DEVICE="cpu" pytest -o addopts=''
   ```