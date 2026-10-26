# syntax=docker/dockerfile:1

# -----------------------------------------------------------------------------
# Stage 1: Build & Dependency Installation
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# Create virtual environment and install project dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# -----------------------------------------------------------------------------
# Stage 2: Production Runtime (Configured for Hugging Face Spaces & PaaS)
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces expects non-root user with UID 1000
RUN useradd -m -u 1000 user

# Copy pre-built virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=7860
ENV HOME=/home/user

# Copy application source code and migrations
COPY --chown=user:user alembic ./alembic
COPY --chown=user:user alembic.ini ./
COPY --chown=user:user app ./app

# Create storage and vector directories with proper ownership
RUN mkdir -p /app/storage/uploads /app/storage/vector_store && \
    chown -R user:user /app

USER user

EXPOSE 7860

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-7860}/health || exit 1

# Auto-run Alembic migrations to initialize SQLite tables, then launch FastAPI on $PORT (defaults to 7860)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
