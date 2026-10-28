"""RAG Evaluation Script measuring retrieval hit-rate, empty rejection, and tenant isolation."""

import asyncio
from typing import Any

from app.ai.rag.chunker import DocumentChunker
from app.ai.rag.embedder import MockEmbedder
from app.ai.rag.vector_store import InMemoryVectorStore, VectorChunk

# Sample ground-truth Q&A evaluation dataset
EVAL_DOCUMENTS: list[dict[str, Any]] = [
    {
        "doc_id": 101,
        "filename": "john_doe_backend_resume.pdf",
        "text": (
            "John Doe - Senior Backend Engineer. 6 years experience in Python, FastAPI, and SQLAlchemy. "
            "Designed high-throughput MySQL and Redis caching layers. Led containerization using Docker "
            "and Kubernetes. Implemented GitHub Actions CI/CD pipelines deploying to production clusters."
        ),
    },
    {
        "doc_id": 102,
        "filename": "kubernetes_administrator_cert.pdf",
        "text": (
            "Certified Kubernetes Administrator (CKA). Validation Number: CKA-987654321. "
            "Demonstrated proficiency in cluster architecture, RBAC authorization, PersistentVolumes, "
            "Ingress controllers, networking, and monitoring."
        ),
    },
    {
        "doc_id": 103,
        "filename": "bachelor_degree_transcript.pdf",
        "text": (
            "University of Technology - Bachelor of Science in Computer Science, Magna Cum Laude. "
            "Relevant Coursework: Distributed Systems, Database Management Systems, Compilers, "
            "Data Structures & Algorithms, Network Security."
        ),
    },
]

EVAL_QUERIES: list[dict[str, Any]] = [
    {
        "question": "What databases and caching technologies does John Doe use?",
        "expected_doc_id": 101,
        "expected_keywords": ["mysql", "redis"],
        "expect_hit": True,
    },
    {
        "question": "What is the CKA certification validation number?",
        "expected_doc_id": 102,
        "expected_keywords": ["cka-987654321"],
        "expect_hit": True,
    },
    {
        "question": "What university degree and honors did the candidate earn?",
        "expected_doc_id": 103,
        "expected_keywords": ["computer science", "magna cum laude"],
        "expect_hit": True,
    },
    {
        "question": "What is the candidate's favorite pasta recipe and culinary background?",
        "expected_doc_id": None,
        "expected_keywords": [],
        "expect_hit": False,  # Should return empty or below threshold
    },
]


async def run_rag_evaluation() -> dict[str, float]:
    """Execute evaluation benchmark and report accuracy metrics."""
    print("=" * 65)
    print("CareerAI RAG Retrieval Hit-Rate & Isolation Evaluation Benchmark")
    print("=" * 65)

    test_user_id = 42
    unauthorized_user_id = 999

    chunker = DocumentChunker(chunk_size=300, chunk_overlap=50)
    embedder = MockEmbedder(dimension=128)
    vector_store = InMemoryVectorStore()

    # 1. Index evaluation documents
    total_chunks = 0
    for doc in EVAL_DOCUMENTS:
        chunks = chunker.chunk_text(doc["text"], document_id=doc["doc_id"], user_id=test_user_id)
        texts = [c.content for c in chunks]
        embeddings = await embedder.embed_documents(texts)

        vector_chunks = [
            VectorChunk(
                id=c.vector_id,
                vector=emb,
                text=c.content,
                metadata={
                    "user_id": test_user_id,
                    "document_id": doc["doc_id"],
                    "filename": doc["filename"],
                    "chunk_index": c.chunk_index,
                },
            )
            for c, emb in zip(chunks, embeddings, strict=False)
        ]
        await vector_store.add_chunks(vector_chunks)
        total_chunks += len(vector_chunks)

    print(f"Indexed {len(EVAL_DOCUMENTS)} documents across {total_chunks} chunks.")

    # 2. Evaluate query retrieval accuracy
    hits_count = 0
    expected_hits_count = 0
    empty_rejection_count = 0
    total_unanswerable = 0
    isolation_passed = 0

    for item in EVAL_QUERIES:
        q_vec = await embedder.embed_query(item["question"])

        # Query as legitimate user
        results = await vector_store.search(
            query_vector=q_vec,
            user_id=test_user_id,
            top_k=3,
            min_similarity=0.25,
        )

        # Cross-user query test: unauthorized user must retrieve 0 chunks
        isolated_results = await vector_store.search(
            query_vector=q_vec,
            user_id=unauthorized_user_id,
            top_k=3,
            min_similarity=0.25,
        )
        if len(isolated_results) == 0:
            isolation_passed += 1

        if item["expect_hit"]:
            expected_hits_count += 1
            if results:
                top_doc_id = results[0].metadata.get("document_id")
                if top_doc_id == item["expected_doc_id"]:
                    hits_count += 1
                    msg = (
                        f"  [PASS] '{item['question'][:35]}...' -> "
                        f"Matched Doc {top_doc_id} (Score: {results[0].score:.3f})"
                    )
                    print(msg)
                else:
                    msg = (
                        f"  [MISS] '{item['question'][:35]}...' -> "
                        f"Expected {item['expected_doc_id']}, Got {top_doc_id}"
                    )
                    print(msg)
            else:
                print(f"  [MISS] '{item['question'][:40]}...' -> No chunks retrieved above threshold")
        else:
            total_unanswerable += 1
            if len(results) == 0:
                empty_rejection_count += 1
                print(f"  [PASS] Unanswerable query correctly rejected with 0 chunks: '{item['question'][:40]}...'")
            else:
                print(f"  [FAIL] Unanswerable query incorrectly returned chunks: score={results[0].score}")

    hit_rate = (hits_count / expected_hits_count) * 100.0 if expected_hits_count > 0 else 0.0
    rejection_rate = (empty_rejection_count / total_unanswerable) * 100.0 if total_unanswerable > 0 else 0.0
    isolation_rate = (isolation_passed / len(EVAL_QUERIES)) * 100.0

    print("-" * 65)
    print(f"Retrieval Hit Rate (Top-1)        : {hit_rate:.1f}% ({hits_count}/{expected_hits_count})")
    print(f"Empty Retrieval Rejection Rate    : {rejection_rate:.1f}% ({empty_rejection_count}/{total_unanswerable})")
    print(f"Tenant Isolation Rate             : {isolation_rate:.1f}% ({isolation_passed}/{len(EVAL_QUERIES)})")
    print("=" * 65)

    assert hit_rate >= 80.0, f"Hit rate {hit_rate}% is below target 80%"
    assert rejection_rate == 100.0, f"Rejection rate {rejection_rate}% must be 100%"
    assert isolation_rate == 100.0, f"Isolation rate {isolation_rate}% must be 100%"

    return {
        "hit_rate": hit_rate,
        "rejection_rate": rejection_rate,
        "isolation_rate": isolation_rate,
    }


if __name__ == "__main__":
    asyncio.run(run_rag_evaluation())
