# Infrastructure & Deployment

CareerAI is designed as a cloud-agnostic, containerized microservices platform.

## Architecture

- **Application Tier**: FastAPI (ASGI) running on Python 3.12/3.13 in isolated multi-stage Docker containers.
- **Relational Storage**: MySQL 8.0 with SQLAlchemy 2.0 async connection pooling and Alembic schema migrations.
- **Cache & Message Broker**: Redis 7.0 for rate limiting, distributed idempotency locking, and background task retry queues.
- **Object Storage**: Local persistent volume filesystem (`/app/storage/uploads`) with path-traversal protection.
- **Reverse Proxy & Ingress**: Nginx / Caddy / Cloud Load Balancer with TLS termination and security headers.

## Deployment Options

1. **Docker Compose Production**: Use `docker-compose.prod.yml` with Docker secrets for zero-downtime rolling deploys.
2. **PaaS (Render, Fly.io, etc.)**: Configured out of the box via `render.yaml`.
3. **Kubernetes / Podman**: Stateless API pods with Horizontal Pod Autoscaling (HPA) and PersistentVolumeClaims for document storage.
