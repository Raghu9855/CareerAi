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
