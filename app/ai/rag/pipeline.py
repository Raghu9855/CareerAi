"""RAG pipeline coordinating chunking, embedding, vector store operations, retrieval, and LLM synthesis."""

import time

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.client import LLMClient, LLMMessage
from app.ai.llm.factory import get_llm_client
from app.ai.rag.chunker import DocumentChunker
from app.ai.rag.embedder import Embedder, get_embedder
from app.ai.rag.vector_store import VectorChunk, VectorStore, get_vector_store
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus
from app.schemas.rag import RAGQueryResponse, SourceCitation

logger = get_logger("careerai.ai.rag.pipeline")

MIN_RELEVANCE_THRESHOLD = 0.25
UNAVAILABLE_ANSWER = (
    "I could not find sufficient relevant information in your uploaded documents to answer this question. "
    "Please make sure your resume or career documents contain details related to your query."
)


class RAGPipeline:
    """End-to-end RAG orchestrator with strict user isolation, citation attribution, and threshold rejection."""

    def __init__(
        self,
        session: AsyncSession,
        vector_store: VectorStore | None = None,
        embedder: Embedder | None = None,
        llm_client: LLMClient | None = None,
        chunker: DocumentChunker | None = None,
    ) -> None:
        self.session = session
        self.vector_store = vector_store or get_vector_store()
        self.embedder = embedder or get_embedder()
        self.llm_client = llm_client or get_llm_client()
        self.chunker = chunker or DocumentChunker(chunk_size=500, chunk_overlap=100)

    async def index_document(self, document_id: int, user_id: int) -> int:
        """Chunk, embed, and store document segments in both DB and vector store."""
        # 1. Fetch document and enforce ownership
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.is_deleted.is_(False),
        )
        doc = (await self.session.execute(stmt)).scalar_one_or_none()
        if not doc:
            raise NotFoundError(message="Document not found", details={"document_id": document_id})

        if doc.status != DocumentStatus.READY or not doc.extracted_text:
            raise ValidationError(
                message=f"Document is not ready for indexing. Current status: {doc.status.value}",
                details={"document_id": document_id, "status": doc.status.value},
            )

        # 2. Clear any preexisting chunks for this document
        await self.delete_document_vectors(document_id, user_id)

        # 3. Chunk extracted text
        text_chunks = self.chunker.chunk_text(
            text=doc.extracted_text,
            document_id=doc.id,
            user_id=user_id,
        )
        if not text_chunks:
            return 0

        # 4. Generate batch embeddings
        texts = [tc.content for tc in text_chunks]
        embeddings = await self.embedder.embed_documents(texts)

        # 5. Populate VectorStore and DB DocumentChunk models
        vector_chunks: list[VectorChunk] = []
        db_chunks: list[DocumentChunk] = []

        for tc, emb in zip(text_chunks, embeddings, strict=True):
            metadata = {
                "user_id": user_id,
                "document_id": doc.id,
                "chunk_index": tc.chunk_index,
                "filename": doc.filename,
                "original_filename": doc.filename,
            }
            vector_chunks.append(
                VectorChunk(
                    id=tc.vector_id,
                    vector=emb,
                    text=tc.content,
                    metadata=metadata,
                )
            )
            db_chunks.append(
                DocumentChunk(
                    document_id=doc.id,
                    user_id=user_id,
                    chunk_index=tc.chunk_index,
                    vector_id=tc.vector_id,
                    text_snippet=tc.content[:300],
                    token_count=tc.token_count,
                )
            )

        # Index in vector store
        await self.vector_store.add_chunks(vector_chunks)

        # Save to database
        self.session.add_all(db_chunks)
        await self.session.commit()

        logger.info(f"Successfully indexed document {doc.id} ({len(vector_chunks)} chunks)")
        return len(vector_chunks)

    async def query(
        self,
        user_id: int,
        question: str,
        document_id: int | None = None,
        top_k: int = 4,
    ) -> RAGQueryResponse:
        """Execute semantic search strictly filtered by user_id, evaluate relevance threshold, and synthesize answer."""
        start_time = time.perf_counter()

        # 1. Embed query
        query_vector = await self.embedder.embed_query(question)

        # 2. Strict user-scoped vector retrieval
        search_hits = await self.vector_store.search(
            query_vector=query_vector,
            user_id=user_id,
            top_k=top_k,
            document_id=document_id,
            min_similarity=MIN_RELEVANCE_THRESHOLD,
        )

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 3. Empty or weak retrieval: "I don't know" threshold fallback
        if not search_hits:
            logger.info(f"RAG query returned no chunks meeting threshold for user {user_id}")
            return RAGQueryResponse(
                question=question,
                answer=UNAVAILABLE_ANSWER,
                citations=[],
                confidence=0.0,
                retrieval_count=0,
                latency_ms=latency_ms,
                has_answer=False,
            )

        top_confidence = search_hits[0].score

        # 4. Construct prompt with source citations
        context_blocks = []
        citations: list[SourceCitation] = []

        for hit in search_hits:
            meta = hit.metadata
            doc_id = meta.get("document_id", 0)
            fname = meta.get("original_filename", meta.get("filename", "document"))
            c_idx = meta.get("chunk_index", 0)

            context_blocks.append(f"[Source: {fname} (Document ID: {doc_id}, Chunk: {c_idx})]:\n{hit.text}")
            citations.append(
                SourceCitation(
                    document_id=doc_id,
                    filename=fname,
                    chunk_index=c_idx,
                    text_snippet=hit.text[:200] + ("..." if len(hit.text) > 200 else ""),
                    relevance_score=hit.score,
                )
            )

        full_context = "\n\n".join(context_blocks)

        messages = [
            LLMMessage(
                role="system",
                content=(
                    "You are CareerAI Document Intelligence Assistant. Answer the user's question accurately "
                    "and concisely, relying STRICTLY and EXCLUSIVELY on the provided document excerpts below.\n"
                    "If the answer is not contained in the context, explicitly reply: "
                    "'I cannot find the answer in your uploaded documents.'\n"
                    "Always mention the relevant source documents cited in your explanation."
                ),
            ),
            LLMMessage(
                role="user",
                content=(f"Context Excerpts:\n{full_context}\n\nUser Question: {question}\n\nAnswer:"),
            ),
        ]

        # 5. Synthesize answer with LLM
        try:
            llm_response = await self.llm_client.generate(messages=messages, temperature=0.1)
            answer_text = llm_response.content.strip()
        except Exception as exc:
            logger.error(f"LLM synthesis failed in RAG pipeline: {exc}")
            # Gracefully provide context snippet attribution if LLM fails
            answer_text = f"Based on your documents, the most relevant section states: '{search_hits[0].text[:300]}...'"

        total_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return RAGQueryResponse(
            question=question,
            answer=answer_text,
            citations=citations,
            confidence=top_confidence,
            retrieval_count=len(search_hits),
            latency_ms=total_latency_ms,
            has_answer=True,
        )

    async def delete_document_vectors(self, document_id: int, user_id: int) -> tuple[int, int]:
        """Delete vectors from VectorStore and chunk tracking rows from database."""
        # 1. Delete from vector store
        vectors_deleted = await self.vector_store.delete_by_document(document_id=document_id, user_id=user_id)

        # 2. Delete from database
        stmt = delete(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        chunks_deleted = int(getattr(result, "rowcount", 0))

        logger.info(
            f"Removed RAG index for document {document_id}: {vectors_deleted} vectors, {chunks_deleted} DB chunks"
        )
        return vectors_deleted, chunks_deleted
