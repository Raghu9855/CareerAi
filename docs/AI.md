# CareerAI Intelligence: ML, LLM & RAG Systems

CareerAI delivers intelligent career guidance by harmonizing three distinct AI disciplines:
1. **Machine Learning (ML)** for fast, deterministic compatibility scoring and skill gap ranking.
2. **Large Language Models (LLM)** for structured fit synthesis and custom interview preparation.
3. **Retrieval-Augmented Generation (RAG)** for private document search with verifiable source citations.

---

## 1. Machine Learning Compatibility Engine

### Architecture & Feature Vector
The ML engine extracts an 8-dimensional feature vector combining statistical NLP, canonical taxonomy matching, and length distributions:

```
[Candidate Text] + [Job Description]
               │
               ▼
   [Feature Extraction Pipeline]
   ├── 1. tfidf_cosine_sim      (TF-IDF n-gram (1,2) Cosine Similarity)
   ├── 2. skill_overlap_ratio   (Matched Skills / Job Required Skills)
   ├── 3. jaccard_similarity    (Word Token Set Jaccard Overlap)
   ├── 4. candidate_skill_count (Total Recognized Skills in Resume)
   ├── 5. job_skill_count       (Total Required Skills in Job Posting)
   ├── 6. matched_skill_count   (Count of Overlapping Skills)
   ├── 7. log_candidate_words   (log1p of Resume Word Count)
   └── 8. log_job_words         (log1p of Job Description Word Count)
               │
               ▼
  [RandomForestRegressor (v1.0)] -> Compatibility Score (0 - 100)
```

### Reproducible Training & Model Performance
- **Script**: `app/ml/train.py`
- **Model**: `RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42)`
- **Evaluation Metrics (Held-out Test Split)**:
  - **$R^2$ Score**: `0.9927`
  - **RMSE**: `2.6841`
  - **MAE**: `2.1635`
- **Artifacts**: Serialized into `app/ml/artifacts/model.joblib` and `metadata.json`.
- **Preloading**: Loaded once into memory at application lifespan startup using a thread-safe singleton (`ModelLoader`).
- **Resilience Fallback**: If the model artifact is missing, `HeuristicFallbackModel` activates seamlessly, preventing cold-start downtime.

### Honest Discussion of Limitations
1. **Lexical & Statistical Overlap**: While TF-IDF and n-gram overlap capture technical vocabulary well, they can miss deeply synonymous non-standard phrasing not captured in the canonical taxonomy.
2. **Domain Bias**: The training set focuses predominantly on modern software, cloud engineering, and technical professions in English.
3. **Absence of Soft-Skill Evaluation**: The model measures technical alignment, qualifications, and toolsets; it does not evaluate interpersonal dynamics or team culture.

---

## 2. LLM Integration & Resilience Layer

### Provider-Agnostic Interface (`LLMClient`)
The LLM engine communicates through an abstract `LLMClient` protocol:
- `OpenAICompatibleClient`: Connects to OpenAI, Azure, Groq, or self-hosted vLLM.
- `MockLLMClient`: High-fidelity mock used in unit and CI tests, with built-in fault injection (timeouts, 429 rate limits, malformed JSON).

### Resilient Client Wrapper (`ResilientLLMClient`)
All requests pass through a resilience layer providing:
1. **Exponential Backoff & Randomized Jitter**: Up to 3 retries on transient HTTP 429, 502, 503, and network timeouts.
2. **Prompt-Response Deduplication**: Concurrent requests sharing identical prompt hashes share the same `asyncio.Future`, preventing duplicate LLM billing.
3. **SHA-256 In-Memory Cache**: Repeated identical queries return cached structured responses within a 30-minute TTL.
4. **Graceful Degradation**: If an external LLM provider suffers a catastrophic outage, the API returns the ML compatibility score with `explanation_status="unavailable"` and `degraded=true` rather than breaking with an HTTP 500 error.

---

## 3. Document RAG Pipeline & Multi-Tenant Isolation

### Pipeline Workflow
```
[Document Upload]
       │
       ▼
[Sentence/Paragraph Chunker] (600 chars, 120 char overlap)
       │
       ▼
[Batch Embedder] (128-dim normalized semantic vectors)
       │
       ▼
[Vector Store & DB Chunks] (Stored with user_id, doc_id, chunk_index)
       │
       ▼
[User Question] -> [Query Vector] -> [Search filtered strictly by user_id]
                                    │
                                    ▼
       Top-K Chunks (Score >= 0.22) ──> [LLM Synthesis with Citations]
                                    │
                                    ▼
       Below Threshold (Score < 0.22) ─> "I cannot find the answer in your documents."
```

### Strict Multi-Tenant Isolation Guarantees
- Every vector chunk is stored with `metadata["user_id"]`.
- The `VectorStore.search(..., user_id=...)` method requires `user_id` as a mandatory parameter and prunes chunks from other users before scoring.
- Even if User B queries the exact words from User A's private document, the search returns 0 hits.
- Deleting a document removes both vectors from the vector store and records from the `document_chunks` table.

### Evaluation Benchmark Results (`scripts/eval_rag.py`)
Run via `python scripts/eval_rag.py`:
- **Top-1 Retrieval Hit Rate**: `100.0% (3/3)`
- **Empty Retrieval Rejection Rate**: `100.0% (1/1)`
- **Tenant Isolation Rate**: `100.0% (4/4)`
