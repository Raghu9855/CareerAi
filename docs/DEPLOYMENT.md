# CareerAI Production Deployment & Operations Guide

This guide details the complete, reproducible process for deploying **CareerAI** to production using multi-stage Docker containers, Docker Compose, Linux VMs, or Cloud PaaS (e.g., Render, Fly.io) with zero-downtime rolling deploys, database connection pooling, and health probes.

---

## 1. Architectural Overview

```
                      Internet
                         │
                         ▼
             [HTTPS :443 Reverse Proxy / Ingress]
             (TLS 1.3 Termination, Caddy / Nginx / Cloudflare)
                         │
                         ▼ Forward :8000
             [CareerAI FastAPI Container Tier]
             ├── Image: careerai:production
             ├── Multi-stage non-root container
             ├── Zero-dependency local persistent volume
             └── Health Probes: /health, /ready, /metrics
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
[MySQL 8.0 Database]             [Redis 7.0 Cache & Queue]
(InnoDB, Pre-ping Pools)         (Rate Limiting & Idempotency)
```

---

## 2. Prerequisites

1. **Docker** (>= 24.0) and **Docker Compose** (>= 2.20) installed on the deployment host.
2. A registered domain with TLS/SSL certificate configured via Reverse Proxy or PaaS.
3. Production secrets prepared for environment injection.

---

## 3. Production Deployment with Docker Compose

### Step 3.1: Environment Configuration
Create a `.env.production` file on your server (never commit secrets to version control):
```bash
APP_NAME=CareerAI
APP_ENV=production
APP_DEBUG=false
HOST=0.0.0.0
PORT=8000

# Database (MySQL 8)
DATABASE_URL=mysql+asyncmy://careerai_user:SECURE_DB_PASSWORD@mysql:3306/careerai_db

# Redis
REDIS_URL=redis://redis:6379/0

# Security & JWT
SECRET_KEY=GENERATE_SUPER_SECRET_MIN_32_CHAR_STRING
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Storage
STORAGE_BACKEND=local
STORAGE_LOCAL_ROOT=/app/storage/uploads
MAX_UPLOAD_SIZE_BYTES=10485760

# LLM Configuration
LLM_PROVIDER=mock  # or groq / openai / gemini with LLM_API_KEY
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
```

### Step 3.2: Launch the Production Stack
```bash
# Build and launch all services in detached mode
docker compose -f docker-compose.prod.yml up -d --build
```

### Step 3.3: Run Database Migrations
```bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

---

## 4. One-Click Cloud Deployment (Render / PaaS)

CareerAI includes native `render.yaml` infrastructure configuration:

```bash
# Push to your repository and connect Render to auto-deploy
git push origin main
```

The blueprint automatically provisions:
1. **Web Service**: FastAPI with Uvicorn ASGI workers.
2. **Managed MySQL Database**: High-availability transactional storage.
3. **Managed Redis Instance**: In-memory caching and distributed lock broker.
4. **Persistent Disk**: Attached to `/app/storage/uploads` for resume documents.

---

## 5. Health Probes & Monitoring

CareerAI exposes 3 native monitoring endpoints:

- **Liveness Probe**: `GET /health`
  - Returns `{"status": "ok"}`
  - Used by load balancers and orchestrators for process liveness checks.

- **Readiness Probe**: `GET /ready`
  - Returns deep dependency checks:
    ```json
    {
      "status": "ready",
      "app": "CareerAI",
      "checks": {
        "database": "healthy"
      }
    }
    ```

- **Process Telemetry**: `GET /metrics`
  - Reports Memory RSS (MB), active threads, Python runtime, and loaded ML model version.

---

## 6. Zero-Downtime Rolling Updates

To deploy an updated build without dropping connections:

```bash
# 1. Pull latest code
git pull origin main

# 2. Build updated production image
docker compose -f docker-compose.prod.yml build api

# 3. Perform rolling container replacement
docker compose -f docker-compose.prod.yml up -d --no-deps --build api

# 4. Verify healthy state
curl -s http://localhost:8000/ready
```

---

## 7. Rollback Runbook

If issues arise after deployment:

### Application Rollback:
```bash
# Revert to previous image tag or commit
docker compose -f docker-compose.prod.yml up -d --build api
```

### Database Schema Downgrade:
```bash
docker compose -f docker-compose.prod.yml exec api alembic downgrade -1
```
