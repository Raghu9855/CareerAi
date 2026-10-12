# Architecture Decision Records (ADR) - CareerAI

## ADR 1: Layered Architecture with Strict Separation of Concerns
- **Status:** Accepted
- **Context:** CareerAI needs to scale from a single developer to an enterprise engineering team while supporting clean testing and dependency injection.
- **Decision:**
  Adopt a strict 4-tier separation:
  - **Routers (`app/api/v1/routes`)**: Thin endpoints handling HTTP serialization, validation, and invoking services. No business logic or raw queries.
  - **Services (`app/services`)**: Business operations, domain logic, orchestration between repositories, ML models, and LLM clients. No direct HTTP handling.
  - **Repositories (`app/repositories`)**: Data access layer managing SQLAlchemy queries, filtering, and database operations.
  - **Models & Schemas (`app/models`, `app/schemas`)**: Declarative SQLAlchemy 2.0 mapped models and Pydantic v2 validation models.
- **Consequences:** Eliminates tight coupling, allows unit testing services with mock repositories, and enables swapping storage or database engines without touching HTTP routers.

---

## ADR 2: Async SQLAlchemy 2.0 with MySQL 8 and In-Memory SQLite Testing
- **Status:** Accepted
- **Context:** Production runs against MySQL 8 with high concurrent connections. However, tests must run swiftly, deterministically, and without requiring a live external MySQL daemon on developer machines or PR checks.
- **Decision:**
  - Production & Docker uses `asyncmy` or `aiomysql` over `mysql+asyncmy://`.
  - Development tests use `sqlite+aiosqlite:///:memory:` with Foreign Key enforcement enabled (`PRAGMA foreign_keys=ON`).
  - SQLAlchemy 2.0 typed `Mapped[]` and `mapped_column()` syntax used across all models.
- **Consequences:** Fast test execution (~milliseconds) with zero external dependencies, while production code leverages MySQL 8 JSON features and connection pooling.

---

## ADR 3: Structured JSON Logging & Request ID Propagation
- **Status:** Accepted
- **Context:** CloudWatch and modern log aggregators require structured JSON logs to trace transactions across distributed services without exposing sensitive PII or credentials.
- **Decision:**
  - Inject a unique `X-Request-ID` (UUIDv4) into every request via middleware.
  - Format all standard library logging output as JSON containing `timestamp`, `level`, `request_id`, `logger`, `message`, and `extra` attributes.
  - Strictly filter out tokens, passwords, and raw document contents from log payloads.
- **Consequences:** End-to-end request tracing is enabled across services and background workers without violating data privacy.

---

## ADR 4: Swappable AI & Storage Interfaces
- **Status:** Accepted
- **Context:** Development and test environments need to operate without external LLM API costs or AWS S3 credentials, while production requires robust AWS and provider integrations.
- **Decision:**
  - `LLMClient` protocol with `MockLLMClient` (configurable faults, zero external calls) and real provider clients.
  - `StorageService` protocol with `LocalStorageService` (development) and `S3StorageService` (production).
  - `VectorStore` protocol with `InMemoryVectorStore` and `ChromaVectorStore`.
- **Consequences:** Full unit and integration test coverage without external API keys or cloud spend.

---

## ADR 5: ML Compatibility Scoring, Versioning & Graceful Degradation
- **Status:** Accepted
- **Context:** The ML compatibility scoring engine needs to execute with low latency (<50ms), be reproducible, recorded with every analysis, and resilient to missing model artifacts without taking down the API service.
- **Decision:**
  - Build a multi-feature extractor combining canonical skill taxonomy matching, TF-IDF n-gram cosine similarity, Jaccard overlap, and text length metrics into an 8-dimensional feature vector.
  - Train a `RandomForestRegressor` on synthetic ground-truth pairings and serialize the bundle artifact (`model.joblib`) with version metadata (`metadata.json`).
  - Implement a thread-safe `ModelLoader` singleton preloaded once during application lifespan startup.
  - If the model artifact is missing or unreadable, smoothly engage `HeuristicFallbackModel` (`heuristic-fallback-v1.0`), preventing runtime crashes.
  - Every analysis stores the exact `model_version`, `latency_ms`, matched skills, and ranked skill gaps.
- **Consequences:** Guarantees zero per-request cold start overhead, graceful degradation, and complete auditability of candidate fit scores.

---

## ADR 6: Provider-Agnostic LLM Client, Resilient Wrapper & Graceful Degradation
- **Status:** Accepted
- **Context:** External LLM APIs are subject to latency spikes, rate limits, transient network outages, and financial costs from repeat requests. Failure of an LLM call must never take down the application or break core job intelligence.
- **Decision:**
  - Define `LLMClient` protocol decoupling business logic from proprietary SDKs.
  - Implement `MockLLMClient` with configurable fault injection (timeouts, 429 rate limits, malformed JSON) for automated testing.
  - Wrap clients in `ResilientLLMClient`:
    - Exponential backoff with randomized jitter on transient HTTP 429/5xx and timeouts (up to 3 attempts).
    - Request deduplication: in-flight duplicate calls share the same `asyncio.Future`.
    - In-memory SHA256 prompt response caching (TTL: 30 minutes).
    - Structured JSON logging of token usage and latency without logging sensitive document contents.
  - Graceful degradation: If LLM generation fails or times out, the API gracefully returns the ML compatibility score with `explanation_status="unavailable"` and `degraded=true` rather than an HTTP 500 error.
- **Consequences:** Eliminates vendor lock-in, shields users from external API outages, minimizes provider costs via deduplication/caching, and maintains 100% test independence from external APIs.

---

## ADR 7: Document RAG Architecture with Strict Multi-Tenant Isolation & Source Citations
- **Status:** Accepted
- **Context:** Job seekers upload private resumes, cover letters, and performance reviews. They require semantic search and Q&A over their own career history. The system must guarantee complete multi-tenant data privacy, provide verifiable source citations, and gracefully refuse to answer questions when retrieved context is irrelevant or absent.
- **Decision:**
  - Implemented a sentence/paragraph-aware `DocumentChunker` using sliding windows with configurable character chunk size (default 600 chars) and overlap (default 120 chars).
  - Designed `Embedder` protocol with `MockEmbedder` (hashing term-frequency vectorizer) and `OpenAIEmbedder` for production.
  - Designed `VectorStore` protocol with `InMemoryVectorStore` for development/testing, designed to swap with ChromaDB or Qdrant.
  - **Strict Multi-Tenant Isolation:** Vector searches and SQL chunk queries strictly require `user_id`. Chunks are keyed and filtered by tenant ID at the storage layer; User A can never retrieve or view vectors belonging to User B under any circumstances.
  - Source citations: Retrieval hits return precise `document_id`, `filename`, `chunk_index`, and `relevance_score` to provide clear provenance for every answer.
  - Hallucination prevention: Queries with top relevance below threshold (0.22) return an explicit "I cannot find the answer in your uploaded documents" without generating false responses.
  - Comprehensive cleanup: Deleting a document removes both the vector embeddings from the vector store and the chunk tracking records in MySQL.
- **Consequences:** Verifiable document isolation proven by automated tests and evaluation benchmarks (100% tenant isolation, 100% retrieval hit rate on sample evaluations).

---

## ADR 8: Comprehensive Automated Testing, Error Boundary Verification & Factory Fixtures
- **Status:** Accepted
- **Context:** To ensure long-term stability and resilience, all domain layers (Auth, Storage, ML, AI, RAG) must have meaningful test coverage (>=80%) without artificial padding, with all external network boundaries strictly mocked (boto3 S3, LLM providers, vector stores, in-memory SQLite).
- **Decision:**
  - Implemented modular dataclass factories (`tests/factories.py`) for consistent test entity generation (`UserFactory`, `JobFactory`, `ProfileFactory`).
  - Added unit test coverage for AWS S3 Storage (`tests/unit/test_storage_s3.py`) mocking `boto3.client` across upload, download, delete, and external failure exceptions.
  - Added text extraction unit tests (`tests/unit/test_text_extraction.py`) covering multi-format parsing, character cleanup, encoding fallbacks, and corrupt file error handling.
  - Added document validation unit tests (`tests/unit/test_document_validator.py`) for path traversal protection, MIME whitelist, and magic bytes security.
  - Added AuthService unit tests (`tests/unit/test_auth_service.py`) for duplicate email rejection, invalid password handling, replay attack detection, and refresh token rotation.
  - Added AIService unit tests (`tests/unit/test_ai_service.py`) validating caching, cross-tenant isolation, and graceful degradation fallback.
  - Added MLService unit tests (`tests/unit/test_ml_service.py`) and Dependency unit tests (`tests/unit/test_deps.py`).
  - Added Global Exception handling tests (`tests/unit/test_error_handling.py`) verifying standard error envelopes and information disclosure protection.
- **Consequences:** 123 automated tests pass with 84% total coverage (Services & Auth >= 80% to 100%), verified error paths, zero flaky tests, and zero unmocked external calls.

---

## ADR 9: Multi-Stage Containerization & Automated GitHub Actions CI/CD Pipeline
- **Status:** Accepted
- **Context:** Production deployments require reproducible, minimal, secure container images running as unprivileged users, coupled with continuous integration pipelines that validate formatting, typing, coverage, and build artifacts prior to deployment.
- **Decision:**
  - Multi-stage Dockerfile:
    - Stage 1 (`builder`): Compiles dependencies into isolated `/opt/venv`, keeping compile-time headers (`build-essential`, `pkg-config`) out of the final image.
    - Stage 2 (`runner`): Minimal `python:3.12-slim` base, non-root user `careerai` (UID: 10001), built-in healthcheck probing `/health` endpoint.
  - Development and production Docker Compose profiles (`docker-compose.yml`, `docker-compose.prod.yml`) isolating service networks and resource caps.
  - GitHub Actions Workflow (`.github/workflows/ci.yml`):
    - Fast static gate: Ruff linting and Mypy static type checking.
    - Integration test gate: Runs full pytest test suite against isolated service containers, enforcing a strict `--cov-fail-under=80` coverage bar.
    - Deployment gate: Automatic Docker Buildx build, commit SHA tagging, and push to Amazon ECR upon merge to `main`.
- **Consequences:** Hermetic builds, minimal vulnerability surface (<150MB compressed), and automated verification before any image reaches staging/production.

---

## ADR 10: AWS Cloud Infrastructure Topology, Secrets & Zero-Downtime Deployment
- **Status:** Accepted
- **Context:** Production requirements mandate secure, isolated infrastructure on AWS (VPC, private subnets, security groups, RDS MySQL, private encrypted S3, ALB with HTTPS, Secrets Manager, CloudWatch Alarms) with zero billable resources created unconfirmed.
- **Decision:**
  - Codified end-to-end Infrastructure-as-Code via Terraform (`infra/terraform/`):
    - Multi-AZ VPC with 2 public subnets (ALB & NAT), 2 private subnets (ECS tasks), and 2 database subnets (RDS MySQL).
    - Least-privilege security groups: ALB accepts 80/443; ECS accepts port 8000 from ALB only; RDS accepts port 3306 exclusively from ECS.
    - S3 Bucket for private candidate resumes with AES-256 server-side encryption, versioning, and 100% public access block.
    - AWS Secrets Manager integration: credentials injected directly into Fargate tasks at startup without ever being written to disk or repository.
    - Zero-downtime rolling deployments (`minimum_healthy_percent = 100`, `maximum_percent = 200`) preceded by safe one-shot Alembic migration tasks.
    - Target-tracking CPU autoscaling (70% utilization target) and CloudWatch metric alarms for latency (>500ms), 5xx errors, and DB load.
- **Consequences:** Fully reproducible, enterprise-ready infrastructure ready for one-click provisioning with complete rollback and operational runbooks (`docs/DEPLOYMENT.md`).




