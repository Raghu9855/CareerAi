"""FastAPI router for Document RAG indexing, search querying, and vector cleanup."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.pipeline import RAGPipeline
from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.rag import (
    DeleteRAGResponse,
    IndexDocumentResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)

router = APIRouter(prefix="/rag", tags=["Document RAG"])


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit(requests_per_minute=30))],
    summary="Ask Question Over Documents (RAG)",
    description=(
        "Performs semantic search strictly scoped to the authenticated user's documents. "
        "Returns synthesized answer with source citations or explains when information is missing."
    ),
)
async def query_documents(
    request: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RAGQueryResponse:
    """Execute RAG query with strict user isolation and source citations."""
    pipeline = RAGPipeline(session=db)
    return await pipeline.query(
        user_id=current_user.id,
        question=request.question,
        document_id=request.document_id,
        top_k=request.top_k,
    )


@router.post(
    "/index/{document_id}",
    response_model=IndexDocumentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit(requests_per_minute=20))],
    summary="Index or Re-Index Document in Vector Store",
    description="Extracts chunks and computes embeddings for vector retrieval.",
)
async def index_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IndexDocumentResponse:
    """Trigger chunking and vector indexing for an uploaded document."""
    pipeline = RAGPipeline(session=db)
    count = await pipeline.index_document(document_id=document_id, user_id=current_user.id)
    return IndexDocumentResponse(
        document_id=document_id,
        chunks_indexed=count,
        status="indexed",
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteRAGResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Document Vectors and Chunks",
    description="Removes document embeddings from vector store and chunk database records.",
)
async def delete_document_vectors(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeleteRAGResponse:
    """Delete document vectors and chunk tracking records with ownership check."""
    pipeline = RAGPipeline(session=db)
    vec_count, chunk_count = await pipeline.delete_document_vectors(
        document_id=document_id,
        user_id=current_user.id,
    )
    return DeleteRAGResponse(
        document_id=document_id,
        vectors_deleted=vec_count,
        chunks_deleted=chunk_count,
        status="deleted",
    )
