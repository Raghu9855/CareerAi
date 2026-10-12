"""Embedder interface, MockEmbedder with semantic term hashing, and OpenAIEmbedder."""

import hashlib
import math
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("careerai.ai.rag.embedder")


class Embedder(Protocol):
    """Protocol for generating dense text vector embeddings."""

    dimension: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document chunks."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query string."""
        ...


STOP_WORDS: set[str] = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "what", "when", "where", "which", "who", "will", "with", "did", "does",
}


class MockEmbedder(Embedder):
    """Deterministic, fast mock embedder producing L2-normalized vectors based on token hashing.

    Words present in both texts map to identical vector dimensions, preserving cosine similarity.
    """

    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension

    def _embed_single(self, text: str) -> list[float]:
        """Compute L2-normalized 128-dimensional embedding from words in text."""
        vec = [0.0] * self.dimension
        if not text:
            return vec

        # Tokenize by alphanumeric words and clean punctuation
        tokens = text.lower().split()
        if not tokens:
            return vec

        meaningful_count = 0
        for token in tokens:
            cleaned = "".join(ch for ch in token if ch.isalnum() or ch == "-")
            if not cleaned or cleaned in STOP_WORDS or len(cleaned) < 2:
                continue

            meaningful_count += 1
            # Deterministic bucket via MD5
            digest = hashlib.md5(cleaned.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimension
            vec[idx] += 1.0

        # Fallback if text contained only stopwords
        if meaningful_count == 0:
            for token in tokens:
                digest = hashlib.md5(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % self.dimension
                vec[idx] += 1.0

        # L2 Normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Batch embedding of documents."""
        return [self._embed_single(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        """Embed single query string."""
        return self._embed_single(text)


class OpenAIEmbedder(Embedder):
    """Real HTTP embedder calling OpenAI text-embedding-3-small or compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model
        self.dimension = dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Request embeddings for batch of texts."""
        if not self.api_key:
            # Fall back to mock embedder if API key not present
            fallback = MockEmbedder(dimension=self.dimension)
            return await fallback.embed_documents(texts)

        endpoint = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": texts}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    async def embed_query(self, text: str) -> list[float]:
        """Embed single query string."""
        results = await self.embed_documents([text])
        return results[0]


@lru_cache
def get_embedder() -> Embedder:
    """Dependency helper returning configured Embedder instance."""
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER.lower() == "mock" or not settings.LLM_API_KEY:
        return MockEmbedder(dimension=128)
    return OpenAIEmbedder(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
