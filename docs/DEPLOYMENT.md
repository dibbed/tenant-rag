# 🚀 Deployment Guide

This guide covers deploying the RAG Telegram Assistant in different environments.

## Table of Contents
- [Quick Deployment](#quick-deployment)
- [Environment Setup](#environment-setup)
- [Docker Deployment](#docker-deployment)
- [Production Deployment](#production-deployment)
- [Monitoring Setup](#monitoring-setup)
- [Troubleshooting](#troubleshooting)

## Quick Deployment

### Development Environment
```bash
# Clone and setup
git clone https://github.com/dibbed/rag-telegram-assistant.git
cd rag-telegram-assistant

# Configure environment
cp .env.example .env.development
# Edit .env.development with your credentials

# Deploy
./scripts/deploy.sh development --build --logs
```

### Production Environment
```bash
# Setup production environment
cp .env.example .env.production
# Edit .env.production with production credentials

# Deploy with monitoring
./scripts/deploy.sh production --pull --logs
```

## Environment Setup

### Required Environment Variables
```env
# Core Configuration
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key

# Optional Configuration
DEFAULT_LANG=fa
LOG_LEVEL=INFO
CACHE_TTL=3600
```

### Environment-Specific Files

#### Development (.env.development)
```env
LOG_LEVEL=DEBUG
CACHE_TTL=300
MAX_FILE_SIZE=5242880  # 5MB
DEVELOPMENT=true
```

#### Staging (.env.staging)
```env
LOG_LEVEL=INFO
CACHE_TTL=1800
MAX_FILE_SIZE=10485760  # 10MB
STAGING=true
```

#### Production (.env.production)
```env
LOG_LEVEL=WARNING
CACHE_TTL=7200
MAX_FILE_SIZE=20971520  # 20MB
PRODUCTION=true
ENABLE_METRICS=true
```

## Docker Deployment

### Single Container Deployment
```bash
# Build image
docker build -t ragbot:latest .

# Run container
docker run -d \
  --name ragbot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  ragbot:latest
```

### Docker Compose Deployment

#### Development
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

#### Production
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Multi-Stage Build Benefits
- **Smaller production images**: Only runtime dependencies included
- **Security**: No build tools in production image
- **Consistency**: Same Dockerfile for all environments
- **Optimization**: Separate layers for dependencies and application code

## Production Deployment

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- Minimum 2GB RAM
- 10GB available disk space
- SSL certificate (for HTTPS endpoints)

### Production Checklist

#### Security
- [ ] Use non-root user in containers
- [ ] Enable read-only filesystem where possible
- [ ] Configure proper network isolation
- [ ] Set up secrets management
- [ ] Enable container security scanning

#### Performance
- [ ] Configure resource limits
- [ ] Set up Redis for caching
- [ ] Enable connection pooling
- [ ] Configure log rotation
- [ ] Set up health checks

#### Monitoring
- [ ] Deploy Prometheus for metrics
- [ ] Set up Grafana dashboards
- [ ] Configure alerting rules
- [ ] Enable log aggregation
- [ ] Set up uptime monitoring

### Production Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │     RAG Bot     │    │     Redis       │
│   (nginx/traefik)│────│   (Primary)     │────│    (Cache)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Prometheus    │    │    Grafana      │
                       │  (Monitoring)   │────│  (Dashboards)   │
                       └─────────────────┘    └─────────────────┘
```

### Scaling Considerations

#### Horizontal Scaling
```yaml
# docker-compose.scale.yml
services:
  ragbot:
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
```

#### Load Balancing
```nginx
# nginx.conf
upstream ragbot_backend {
    server ragbot_1:8080;
    server ragbot_2:8080;
    server ragbot_3:8080;
}

server {
    listen 80;
    location / {
        proxy_pass http://ragbot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Monitoring Setup

### Prometheus Configuration
```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ragbot'
    static_configs:
      - targets: ['ragbot:8080']
```

### Grafana Dashboards
Key metrics to monitor:
- Request rate and response time
- Error rates by type
- Memory and CPU usage
- Vector store performance
- OpenAI API usage and errors

### Alerting Rules
```yaml
# monitoring/alert_rules.yml
groups:
  - name: ragbot_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(ragbot_errors_total[5m]) > 0.1
        for: 2m
```

### Log Aggregation
```yaml
# docker-compose.logging.yml
services:
  ragbot:
    logging:
      driver: "fluentd"
      options:
        fluentd-address: "localhost:24224"
        tag: "ragbot"
```

## Health Checks

### Application Health Check
```bash
# Check application health
curl http://localhost:8080/health

# Check specific components
curl http://localhost:8080/health/vector-store
curl http://localhost:8080/health/openai
```

### Docker Health Check
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import ragbot.configs.settings; print('healthy')" || exit 1
```

## Backup and Recovery

### Data Backup
```bash
# Backup vector store data
docker run --rm -v ragbot_data:/data -v $(pwd):/backup alpine \
    tar czf /backup/ragbot-data-$(date +%Y%m%d).tar.gz -C /data .

# Backup logs
docker run --rm -v ragbot_logs:/logs -v $(pwd):/backup alpine \
    tar czf /backup/ragbot-logs-$(date +%Y%m%d).tar.gz -C /logs .
```

### Recovery Process
```bash
# Restore data
docker run --rm -v ragbot_data:/data -v $(pwd):/backup alpine \
    tar xzf /backup/ragbot-data-20240101.tar.gz -C /data

# Restart services
docker-compose restart ragbot
```

## CI/CD Integration

### GitHub Actions Deployment
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          ssh production-server "cd /app && ./scripts/deploy.sh production --pull"
```

### Automated Testing
```bash
# Run deployment tests
pytest tests/deployment/ -v

# Run smoke tests
pytest tests/smoke/ -v --env=production
```

## Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check logs
docker-compose logs ragbot

# Check configuration
docker-compose config

# Validate environment
docker run --rm --env-file .env ragbot:latest python -c "import ragbot.configs.settings"
```

#### High Memory Usage
```bash
# Check memory usage
docker stats ragbot

# Reduce chunk size
echo "CHUNK_SIZE=256" >> .env

# Restart with memory limit
docker-compose up -d --force-recreate
```

#### Performance Issues
```bash
# Enable Redis caching
echo "REDIS_URL=redis://redis:6379" >> .env

# Increase worker processes
echo "WORKERS=4" >> .env

# Monitor performance
curl http://localhost:8080/metrics
```

### Rollback Procedure
```bash
# Quick rollback to previous version
docker-compose down
docker tag ragbot:previous ragbot:latest
docker-compose up -d

# Or use specific version
docker-compose down
docker pull ghcr.io/dibbed/rag-telegram-assistant:v1.0.0
docker-compose up -d
```

## Security Best Practices

### Container Security
- Use non-root user
- Enable read-only filesystem
- Scan images for vulnerabilities
- Keep base images updated

### Network Security
- Use internal networks for service communication
- Expose only necessary ports
- Implement rate limiting
- Use HTTPS for external endpoints

### Secrets Management
```bash
# Use Docker secrets
echo "your_bot_token" | docker secret create bot_token -
echo "your_openai_key" | docker secret create openai_key -
```

### Environment Isolation
```yaml
# docker-compose.prod.yml
services:
  ragbot:
    networks:
      - internal
    environment:
      - BOT_TOKEN_FILE=/run/secrets/bot_token
      - OPENAI_API_KEY_FILE=/run/secrets/openai_key
    secrets:
      - bot_token
      - openai_key

secrets:
  bot_token:
    external: true
  openai_key:
    external: true

networks:
  internal:
    driver: bridge
    internal: true
```

## Performance Optimization

### Resource Tuning
```yaml
# docker-compose.prod.yml
services:
  ragbot:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.2'
```

### Caching Strategy
```env
# Enable aggressive caching for production
CACHE_TTL=7200
REDIS_URL=redis://redis:6379
ENABLE_QUERY_CACHE=true
ENABLE_EMBEDDING_CACHE=true
```

### Database Optimization
```env
# Vector store optimization
FAISS_INDEX_TYPE=IVF
FAISS_NLIST=100
CHUNK_OVERLAP=50
```

This deployment guide provides comprehensive coverage of deploying the RAG Telegram Assistant across different environments with proper monitoring, security, and performance considerations.