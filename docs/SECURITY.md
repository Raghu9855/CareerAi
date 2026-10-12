# CareerAI Security & Compliance Architecture

CareerAI implements defence-in-depth principles across all API surfaces, storage backends, and AI pipelines.

---

## 1. Authentication & Session Management

- **Password Hashing**: Passwords are encrypted using bcrypt with an adaptive work factor (12 rounds) and automatic salt generation.
- **JWT Architecture**:
  - **Access Tokens**: Short-lived (30 minutes), signed using HMAC-SHA256 (`HS256`), containing minimal claims (`sub`, `role`, `iat`, `exp`).
  - **Refresh Tokens**: Long-lived (7 days), stored in MySQL as a SHA-256 hash. Raw tokens are never stored in plaintext.
- **Token Rotation & Replay Attack Protection**:
  - Every `/auth/refresh` call invalidates the submitted refresh token and generates a new pair.
  - If an already-revoked refresh token is re-submitted (indicating potential theft or replay attack), all active sessions for that user are immediately revoked.
- **Explicit Logout**: Revokes the specific refresh token session in the database.

---

## 2. Multi-Tenant Data Isolation & Ownership Controls

CareerAI enforces absolute multi-tenancy boundaries at both the database and vector store layers:

1. **Relational Database Queries**:
   - Every read, update, and delete query in repositories enforces `WHERE user_id = :current_user_id`.
   - Access attempts against another user's documents, jobs, or applications return HTTP 404 (or 403), preventing metadata or identifier enumeration.
2. **Document Vector Store**:
   - Vector chunk records require a mandatory `user_id` attribute.
   - Vector similarity search (`VectorStore.search`) strictly filters candidates by `user_id` before similarity calculation.
   - Deleting a candidate document triggers atomic deletion of both the MySQL tracking records and the vector embeddings.

---

## 3. Document Upload Security & Ingestion Hardening

To prevent Remote Code Execution (RCE), polyglot attacks, and denial of service via malicious uploads:

1. **Size Limits**: Strict cap of 10MB per upload enforced before disk buffering.
2. **Extension Whitelist**: Only `.pdf`, `.docx`, and `.txt` are accepted.
3. **MIME Type Validation**: Whitelist check on declared Content-Type header.
4. **Deep Magic Byte Verification**:
   - `.pdf` files must begin with `%PDF` (magic bytes `0x25 0x50 0x44 0x46`).
   - `.docx` files must begin with the ZIP OpenXML signature `PK\x03\x04`.
   - `.txt` uploads are scanned for null bytes (`\x00`) to detect executables disguised as text.
5. **Path Traversal Sanitization**:
   - `sanitize_filename()` strips all directory separators (`/`, `\`, `..`) and hazardous characters, retaining only alphanumerics, dots, underscores, and dashes.
   - Internal storage uses random UUID prefixes (`documents/{uuid}_{filename}`).

---

## 4. OWASP Top 10 Protections & Security Headers

Every HTTP response includes hardened security headers configured by `SecurityHeadersMiddleware`:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'`

### Distributed Rate Limiting
- Public authentication and AI endpoints are guarded by a sliding-window rate limiter backed by Redis (e.g. 20 requests/minute on `/auth/register`).
- Exceeding the rate limit returns `429 Too Many Requests` with a clear unified error payload.

### Zero-Secrets Policy
- No passwords, tokens, API keys, or credentials exist in the codebase or git history.
- Production environments inject all secrets dynamically from AWS Secrets Manager.
