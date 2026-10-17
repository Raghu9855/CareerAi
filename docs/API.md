# CareerAI REST API Reference

The CareerAI API follows RESTful conventions, supports strict versioning under `/api/v1`, and implements unified error responses and pagination envelopes.

---

## 1. Global Conventions

### Base URLs
- Local Development: `http://localhost:8000/api/v1`
- Production: `https://api.careerai.io/api/v1`

### Authentication
Protected routes require an `Authorization` header containing an active JWT Bearer token:
```http
Authorization: Bearer <access_token>
```

### Standard Error Response Format
All error responses (4xx, 5xx) adhere to a unified JSON format:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request payload or query parameters",
    "details": { ... }
  },
  "request_id": "4e72384a-1122-49da-9c88-e2193b22b109"
}
```

### Idempotency Keys
Mutating POST endpoints accept an optional header:
```http
X-Idempotency-Key: <unique-uuid-or-key>
```
If a request with this key was already completed within the past 24 hours, the cached response is immediately returned with the header `X-Idempotent-Replay: true`.

---

## 2. API Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/health` | Liveness probe returning service status | No |
| `GET` | `/ready` | Readiness probe verifying DB connectivity | No |
| `GET` | `/metrics` | Process memory, CPU, and model info | No |
| `POST` | `/api/v1/auth/register` | Register new user and return token pair | No (Rate limited) |
| `POST` | `/api/v1/auth/login` | Authenticate email/password credentials | No (Rate limited) |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token for new access token | No |
| `POST` | `/api/v1/auth/logout` | Revoke active refresh token session | Yes |
| `GET` | `/api/v1/users/me` | Retrieve profile of authenticated user | Yes |
| `POST` | `/api/v1/profiles` | Create or update candidate profile | Yes |
| `GET` | `/api/v1/profiles/me` | Fetch authenticated user's profile | Yes |
| `GET` | `/api/v1/skills` | List canonical system skills | Yes |
| `POST` | `/api/v1/skills/user` | Add skill with proficiency to user profile | Yes |
| `GET` | `/api/v1/jobs` | Paginated search of active job postings | Yes |
| `POST` | `/api/v1/jobs` | Post new job description | Yes (Admin) |
| `GET` | `/api/v1/applications` | List user's job application pipeline | Yes |
| `POST` | `/api/v1/applications` | Create and track job application | Yes |
| `POST` | `/api/v1/documents/upload` | Upload PDF, DOCX, or TXT resume | Yes |
| `GET` | `/api/v1/documents` | List uploaded candidate documents | Yes |
| `POST` | `/api/v1/ml/analyze` | Run ML fit scoring and skill-gap ranking | Yes |
| `GET` | `/api/v1/ml/model` | View active model version and metadata | Yes |
| `POST` | `/api/v1/ai/explain/{id}` | LLM-written fit explanation with fallback | Yes |
| `POST` | `/api/v1/ai/interview-prep/{id}`| LLM interview prep questions and tips | Yes |
| `POST` | `/api/v1/rag/index/{doc_id}` | Chunk, embed, and index document | Yes |
| `POST` | `/api/v1/rag/query` | Ask semantic questions over documents | Yes |
| `DELETE`| `/api/v1/rag/documents/{id}`| Delete document vectors and chunks | Yes |
| `POST` | `/api/v1/webhooks/endpoints` | Register a new webhook endpoint | Yes (Rate limited) |
| `GET` | `/api/v1/webhooks/endpoints` | List registered webhook endpoints | Yes |
| `GET` | `/api/v1/webhooks/endpoints/{id}` | Get webhook endpoint details | Yes |
| `PATCH`| `/api/v1/webhooks/endpoints/{id}` | Update URL, subscribed events, or status | Yes |
| `DELETE`| `/api/v1/webhooks/endpoints/{id}`| Delete endpoint and cascade delivery logs | Yes |
| `POST` | `/api/v1/webhooks/endpoints/{id}/test` | Fire synthetic ping event for connectivity check | Yes (Rate limited) |
| `GET` | `/api/v1/webhooks/endpoints/{id}/deliveries` | Retrieve delivery logs with retry schedules | Yes |

---

## 3. Core Endpoint Examples

### 3.1 ML Compatibility Analysis
```http
POST /api/v1/ml/analyze HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
Content-Type: application/json

{
  "document_id": 1,
  "job_description": "We are seeking a Senior Cloud Platform Engineer with deep expertise in Python, FastAPI, Docker, and AWS.",
  "job_skills": ["Python", "FastAPI", "Docker", "AWS", "Kubernetes"]
}
```

**Response (200 OK):**
```json
{
  "id": 12,
  "compatibility_score": 87.4,
  "skill_match_score": 80.0,
  "matched_skills": ["Python", "FastAPI", "Docker", "AWS"],
  "missing_skills": [
    {
      "skill": "Kubernetes",
      "importance": "high"
    }
  ],
  "model_version": "v1.0.0-rf-compatibility",
  "latency_ms": 14.2
}
```

### 3.2 RAG Document Question with Citations
```http
POST /api/v1/rag/query HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
Content-Type: application/json

{
  "question": "What databases and cloud platforms does the candidate specialize in?",
  "top_k": 3
}
```

**Response (200 OK):**
```json
{
  "question": "What databases and cloud platforms does the candidate specialize in?",
  "answer": "The candidate has extensive experience with MySQL, Redis, and AWS ECS cloud infrastructure as stated in their resume.",
  "citations": [
    {
      "document_id": 1,
      "filename": "alice_resume.txt",
      "chunk_index": 0,
      "text_snippet": "Extensive expertise deploying microservices to AWS ECS... Architected high-scale MySQL databases and configured Redis caching clusters.",
      "relevance_score": 0.884
    }
  ],
  "confidence": 0.884,
  "retrieval_count": 1,
  "latency_ms": 32.1,
  "has_answer": true
}
```

### 3.3 Webhook Delivery Payload & Verification

When events occur (`application.created`, `application.status_changed`, `application.withdrawn`, `application.deleted`, or `webhook.test`), CareerAI delivers an HTTP POST request to registered endpoints.

**Headers:**
```http
Content-Type: application/json
User-Agent: CareerAI-Webhook-Dispatcher/1.0
X-CareerAI-Event: application.status_changed
X-CareerAI-Delivery-Id: 42
X-CareerAI-Timestamp: 2026-10-17T12:00:00Z
X-CareerAI-Signature: sha256=a1b2c3d4e5f6...7890abcdef
```

**Payload Envelope:**
```json
{
  "event": "application.status_changed",
  "data": {
    "application_id": 7,
    "job_id": 3,
    "previous_status": "applied",
    "new_status": "interviewing"
  },
  "delivery_id": 42,
  "timestamp": "2026-10-17T12:00:00.000000Z"
}
```

**Signature Verification (Python Example):**
```python
import hmac
import hashlib

def verify_signature(secret: str, raw_body: bytes, expected_signature: str) -> bool:
    computed = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, expected_signature)
```

