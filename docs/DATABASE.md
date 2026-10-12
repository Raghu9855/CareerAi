# CareerAI Database Architecture & Schema Reference

CareerAI uses **MySQL 8.0** with SQLAlchemy 2.0 (typed async declarative mapping) and Alembic for schema migrations.

---

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    users ||--o| profiles : "has one"
    users ||--o{ user_skills : "possesses"
    skills ||--o{ user_skills : "classified under"
    users ||--o{ documents : "owns"
    documents ||--o{ document_chunks : "chunked into"
    users ||--o{ applications : "submits"
    jobs ||--o{ applications : "receives"
    users ||--o{ analyses : "requests"
    jobs ||--o{ analyses : "analyzed against"
    documents ||--o{ analyses : "source of"
    users ||--o{ refresh_tokens : "authenticated by"

    users {
        int id PK
        string email UK
        string hashed_password
        string full_name
        string role
        boolean is_active
        boolean is_verified
        datetime created_at
        datetime updated_at
        datetime deleted_at
    }

    profiles {
        int id PK
        int user_id FK,UK
        string headline
        text summary
        string location
        int years_of_experience
        datetime updated_at
    }

    skills {
        int id PK
        string name UK
        string category
    }

    user_skills {
        int id PK
        int user_id FK
        int skill_id FK
        string proficiency_level
        int years_experience
    }

    documents {
        int id PK
        int user_id FK
        string filename
        string storage_path
        string mime_type
        int file_size
        string doc_type
        string status
        text extracted_text
        int char_count
    }

    document_chunks {
        int id PK
        int document_id FK
        int user_id FK
        int chunk_index
        string vector_id UK
        string text_snippet
        int token_count
    }

    jobs {
        int id PK
        string title
        string company
        text description
        string location
        string status
        json required_skills
        int posted_by FK
    }

    applications {
        int id PK
        int user_id FK
        int job_id FK
        string status
        text notes
        datetime applied_at
    }

    analyses {
        int id PK
        int user_id FK
        int job_id FK
        int document_id FK
        float compatibility_score
        float skill_match_score
        float text_similarity_score
        json matched_skills
        json missing_skills
        string model_version
        text llm_explanation
        json interview_prep
        float latency_ms
    }

    refresh_tokens {
        int id PK
        int user_id FK
        string token_hash UK
        datetime expires_at
        boolean is_revoked
    }
```

---

## 2. Table Schemas & Constraints

### 2.1 `users` Table
- `email`: `VARCHAR(255)` with unique B-tree index, stored normalized in lowercase.
- `hashed_password`: Secure bcrypt / argon2 hash string.
- `role`: Enum (`user`, `admin`).
- `deleted_at`: Soft delete timestamp; filtered out on all standard select queries.

### 2.2 `documents` Table
- `user_id`: Foreign key with `ON DELETE CASCADE`.
- `status`: Enum (`uploaded`, `processing`, `ready`, `failed`).
- `doc_type`: Enum (`resume`, `cover_letter`, `career_note`, `other`).
- `storage_path`: Internal storage reference (e.g. `documents/{uuid}_{filename}`).

### 2.3 `document_chunks` Table
- `user_id`: Mandatory tenant identifier for multi-tenant vector isolation.
- `vector_id`: Unique identifier referencing the vector embedding in the vector store (`user_{uid}_doc_{did}_chunk_{idx}`).

### 2.4 `analyses` Table
- `compatibility_score`: ML computed score (0 to 100).
- `matched_skills` & `missing_skills`: Structured JSON arrays.
- `model_version`: Auditable version tag of the active ML model artifact.
- `llm_explanation` & `interview_prep`: Persisted LLM outputs for caching.

---

## 3. Indexing & Query Optimization Strategy

1. **Multi-Tenant Ownership Indexes**:
   - `idx_documents_user_status` on `(user_id, status)`: Accelerates document listings and ready checks.
   - `idx_applications_user_status` on `(user_id, status)`: Optimizes user pipeline view.
   - `idx_chunks_user_doc` on `(user_id, document_id)`: Speeds up vector deletion and chunk retrieval.
2. **Search & Filter Indexes**:
   - `idx_jobs_status_created` on `(status, created_at)`: Optimizes paginated job searches.
   - `idx_analyses_user_created` on `(user_id, created_at)`: Instant user history retrieval.
3. **Soft Delete Filter**:
   - All models inherit `SoftDeleteMixin` providing `is_deleted` and `deleted_at` fields. Repositories automatically apply `WHERE deleted_at IS NULL`.
