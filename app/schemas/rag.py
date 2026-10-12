"""Pydantic v2 schemas for RAG querying, indexing, and citations."""

from pydantic import BaseModel, ConfigDict, Field


class RAGQueryRequest(BaseModel):
    """User question submission over their private documents."""

    question: str = Field(min_length=3, max_length=1000, description="Question text to answer from documents")
    document_id: int | None = Field(default=None, description="Optional target document ID to restrict search to")
    top_k: int = Field(default=4, ge=1, le=10, description="Maximum number of context chunks to retrieve")


class SourceCitation(BaseModel):
    """Source reference attributing answers to specific document chunks."""

    model_config = ConfigDict(from_attributes=True)

    document_id: int
    filename: str
    chunk_index: int
    text_snippet: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class RAGQueryResponse(BaseModel):
    """Result of RAG question answering pipeline."""

    question: str
    answer: str = Field(description="Answer synthesized strictly from retrieved context or 'I don't know' statement")
    citations: list[SourceCitation] = Field(default_factory=list, description="Specific document chunks cited")
    confidence: float = Field(ge=0.0, le=1.0, description="Highest retrieval relevance confidence score")
    retrieval_count: int = Field(ge=0, description="Number of relevant chunks passed to context")
    latency_ms: float
    has_answer: bool = Field(description="False if answer is unknown due to weak or absent retrieval")


class IndexDocumentResponse(BaseModel):
    """Result of document indexing in RAG vector store."""

    document_id: int
    chunks_indexed: int
    status: str = "indexed"


class DeleteRAGResponse(BaseModel):
    """Result of removing document vectors and chunk records."""

    document_id: int
    vectors_deleted: int
    chunks_deleted: int
    status: str = "deleted"
