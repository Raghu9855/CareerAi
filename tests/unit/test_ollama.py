"""Unit tests for OllamaClient provider, factory resolution, error handling, and structured generation."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.client import LLMMessage
from app.ai.llm.factory import get_llm_client
from app.ai.llm.mock import MockLLMClient
from app.ai.llm.ollama import OllamaClient
from app.ai.llm.resilience import ResilientLLMClient
from app.ai.rag.pipeline import RAGPipeline
from app.ai.rag.vector_store import InMemoryVectorStore, VectorChunk
from app.core.errors import (
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
)
from app.models.analysis import Analysis
from app.models.user import User, UserRole
from app.schemas.ai import AnalysisExplanation
from app.services.ai_service import AIService


# ---------------------------------------------------------------------------
# 1. Provider factory selection tests
# ---------------------------------------------------------------------------
def test_factory_resolves_mock_client() -> None:
    """Verify get_llm_client with 'mock' provider returns MockLLMClient inside ResilientLLMClient."""
    client = get_llm_client("mock")
    assert isinstance(client, ResilientLLMClient)
    assert isinstance(client.inner_client, MockLLMClient)


def test_factory_resolves_ollama_client() -> None:
    """Verify get_llm_client with 'ollama' provider returns OllamaClient inside ResilientLLMClient."""
    client = get_llm_client("ollama")
    assert isinstance(client, ResilientLLMClient)
    assert isinstance(client.inner_client, OllamaClient)
    assert client.inner_client.base_url == "http://localhost:11434"
    assert client.inner_client.model in ("llama3.2", "llama3")


def test_factory_resolves_default_from_settings() -> None:
    """Verify get_llm_client without arguments respects settings.LLM_PROVIDER."""
    get_llm_client.cache_clear()
    client = get_llm_client()
    assert isinstance(client, ResilientLLMClient)


# ---------------------------------------------------------------------------
# 2. URL Normalization tests
# ---------------------------------------------------------------------------
def test_ollama_base_url_normalization() -> None:
    """Verify base URL normalization handles trailing slashes and extraneous paths."""
    c1 = OllamaClient(base_url="http://localhost:11434/")
    assert c1.base_url == "http://localhost:11434"

    c2 = OllamaClient(base_url="http://localhost:11434/v1")
    assert c2.base_url == "http://localhost:11434"

    c3 = OllamaClient(base_url="http://localhost:11434/api/")
    assert c3.base_url == "http://localhost:11434"


# ---------------------------------------------------------------------------
# 3. Successful Generation and Streaming tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_successful_generation() -> None:
    """Verify successful Ollama chat completion and metric extraction."""
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2")
    messages = [
        LLMMessage(role="system", content="You are CareerAI."),
        LLMMessage(role="user", content="Explain Python backend match."),
    ]

    mock_response_data = {
        "model": "llama3.2",
        "created_at": "2026-10-18T12:00:00Z",
        "message": {
            "role": "assistant",
            "content": '{"summary": "Strong backend candidate.", "match_verdict": "Strong Match"}',
        },
        "done": True,
        "prompt_eval_count": 35,
        "eval_count": 48,
    }

    mock_resp = httpx.Response(status_code=200, json=mock_response_data, request=httpx.Request("POST", "http://test"))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        resp = await client.generate(messages)

        assert resp.content == '{"summary": "Strong backend candidate.", "match_verdict": "Strong Match"}'
        assert resp.model == "llama3.2"
        assert resp.usage.prompt_tokens == 35
        assert resp.usage.completion_tokens == 48
        assert resp.usage.total_tokens == 83
        assert resp.latency_ms > 0
        assert resp.cached is False

        # Verify safe payload construction
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["model"] == "llama3.2"
        assert len(call_kwargs["json"]["messages"]) == 2
        assert call_kwargs["json"]["stream"] is False


@pytest.mark.asyncio
async def test_ollama_streaming() -> None:
    """Verify async token streaming from Ollama /api/chat NDJSON chunks."""
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2")
    messages = [LLMMessage(role="user", content="Stream this answer.")]

    ndjson_lines = [
        '{"model": "llama3.2", "message": {"role": "assistant", "content": "FastAPI "}, "done": false}',
        '{"model": "llama3.2", "message": {"role": "assistant", "content": "and "}, "done": false}',
        '{"model": "llama3.2", "message": {"role": "assistant", "content": "Docker."}, "done": true}',
    ]

    async def mock_aiter_lines() -> AsyncGenerator[str, None]:
        for line in ndjson_lines:
            yield line

    mock_stream_response = AsyncMock()
    mock_stream_response.status_code = 200
    mock_stream_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__.return_value = mock_stream_response
    mock_stream_ctx.__aexit__.return_value = None

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in client.generate_stream(messages):
            chunks.append(chunk)

        assert chunks == ["FastAPI ", "and ", "Docker."]
        assert "".join(chunks) == "FastAPI and Docker."


# ---------------------------------------------------------------------------
# 4. Error Handling and Mapping tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_connection_refusal_raises_service_unavailable() -> None:
    """Verify connection refusal maps to ServiceUnavailableError with clear instructions."""
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2")
    messages = [LLMMessage(role="user", content="Ping")]

    with patch(
        "httpx.AsyncClient.post",
        side_effect=httpx.ConnectError("Connection refused by target machine"),
    ):
        with pytest.raises(ServiceUnavailableError) as exc_info:
            await client.generate(messages)

        assert "Failed to connect to Ollama server" in exc_info.value.message
        assert exc_info.value.status_code == 503
        assert exc_info.value.details["provider"] == "ollama"


@pytest.mark.asyncio
async def test_ollama_request_timeout_raises_timeout_error() -> None:
    """Verify request timeout maps to TimeoutError."""
    client = OllamaClient(base_url="http://localhost:11434", timeout_seconds=5.0)
    messages = [LLMMessage(role="user", content="Long thinking prompt")]

    with patch(
        "httpx.AsyncClient.post",
        side_effect=httpx.ReadTimeout("Read timed out"),
    ):
        with pytest.raises(TimeoutError) as exc_info:
            await client.generate(messages)

        assert "timed out after 5.0s" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_http_404_model_not_found() -> None:
    """Verify HTTP 404 from Ollama maps to NotFoundError indicating how to pull model."""
    client = OllamaClient(base_url="http://localhost:11434", model="non-existent-model")
    messages = [LLMMessage(role="user", content="Test")]

    error_response = httpx.Response(
        status_code=404,
        json={"error": "model 'non-existent-model' not found, try pulling it first"},
        request=httpx.Request("POST", "http://test"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=error_response):
        with pytest.raises(NotFoundError) as exc_info:
            await client.generate(messages)

        assert "Pull it using 'ollama pull non-existent-model'" in exc_info.value.message
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_ollama_http_429_rate_limit() -> None:
    """Verify HTTP 429 maps to RateLimitError."""
    client = OllamaClient()
    messages = [LLMMessage(role="user", content="Test")]

    resp_429 = httpx.Response(
        status_code=429,
        json={"error": "Rate limit exceeded"},
        request=httpx.Request("POST", "http://test"),
    )
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp_429),
        pytest.raises(RateLimitError),
    ):
        await client.generate(messages)


@pytest.mark.asyncio
async def test_ollama_http_503_service_unavailable() -> None:
    """Verify HTTP 503 maps to ServiceUnavailableError."""
    client = OllamaClient()
    messages = [LLMMessage(role="user", content="Test")]

    resp_503 = httpx.Response(
        status_code=503,
        json={"error": "Ollama service unavailable"},
        request=httpx.Request("POST", "http://test"),
    )
    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=resp_503),
        pytest.raises(ServiceUnavailableError),
    ):
        await client.generate(messages)


@pytest.mark.asyncio
async def test_ollama_malformed_json_response() -> None:
    """Verify invalid non-JSON output from Ollama raises ExternalServiceError."""
    client = OllamaClient()
    messages = [LLMMessage(role="user", content="Test")]

    broken_resp = httpx.Response(
        status_code=200,
        content=b"<!DOCTYPE html><html>Gateway Error</html>",
        headers={"Content-Type": "text/html"},
        request=httpx.Request("POST", "http://test"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=broken_resp):
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.generate(messages)

        assert "invalid non-JSON" in exc_info.value.message


@pytest.mark.asyncio
async def test_ollama_missing_message_content() -> None:
    """Verify Ollama payload missing 'message.content' raises ExternalServiceError."""
    client = OllamaClient()
    messages = [LLMMessage(role="user", content="Test")]

    incomplete_resp = httpx.Response(
        status_code=200,
        json={"model": "llama3.2", "done": True},  # Missing "message"
        request=httpx.Request("POST", "http://test"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=incomplete_resp):
        with pytest.raises(ExternalServiceError) as exc_info:
            await client.generate(messages)

        assert "malformed response missing message content" in exc_info.value.message


# ---------------------------------------------------------------------------
# 5. Structured Output and Schema Validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_structured_response_and_pydantic_validation() -> None:
    """Verify structured response format sets format=json and validates against Pydantic schema."""
    client = OllamaClient(model="llama3.2")
    messages = [
        LLMMessage(role="system", content="Respond ONLY with a valid JSON object."),
        LLMMessage(role="user", content="Analyze candidate fit."),
    ]

    structured_content = (
        '{"summary": "Candidate matches backend requirements.", '
        '"strengths": ["FastAPI", "Python", "SQLAlchemy"], '
        '"areas_for_growth": ["Kubernetes"], '
        '"match_verdict": "Strong Match"}'
    )

    mock_resp = httpx.Response(
        status_code=200,
        json={
            "model": "llama3.2",
            "message": {"role": "assistant", "content": structured_content},
            "done": True,
            "prompt_eval_count": 50,
            "eval_count": 60,
        },
        request=httpx.Request("POST", "http://test"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        resp = await client.generate(messages, response_format={"type": "json_object"})

        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["format"] == "json"

        # Validate with target schema
        import json

        parsed = json.loads(resp.content)
        validated = AnalysisExplanation.model_validate(parsed)
        assert validated.summary == "Candidate matches backend requirements."
        assert "FastAPI" in validated.strengths
        assert validated.match_verdict == "Strong Match"


# ---------------------------------------------------------------------------
# 6. Health check and model list utility tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_check_health_and_list_models() -> None:
    """Verify check_health and list_models utilities."""
    client = OllamaClient(base_url="http://localhost:11434")

    # Health check success
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(
            status_code=200, json={"version": "0.3.14"}, request=httpx.Request("GET", "http://test")
        )
        assert await client.check_health() is True

    # Health check failure
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Refused")):
        assert await client.check_health() is False

    # List models
    tags_response = httpx.Response(
        status_code=200,
        json={"models": [{"name": "llama3.2:latest"}, {"name": "mistral:latest"}]},
        request=httpx.Request("GET", "http://test"),
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=tags_response):
        models = await client.list_models()
        assert models == ["llama3.2:latest", "mistral:latest"]


# ---------------------------------------------------------------------------
# 7. AIService and RAGPipeline integration with Ollama
# ---------------------------------------------------------------------------
@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """Fixture creating a test user in DB."""
    user = User(
        email="ollama_tester@example.com",
        hashed_password="hashed_pw_test",
        full_name="Ollama Tester",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_analysis(db_session: AsyncSession, sample_user: User) -> Analysis:
    """Fixture creating a test analysis in DB."""
    analysis = Analysis(
        user_id=sample_user.id,
        compatibility_score=92.0,
        skill_match_score=90.0,
        model_version="random-forest-v1.0",
        matched_skills=["Python", "FastAPI"],
        missing_skills=[{"skill": "Docker", "importance": "high"}],
        text_similarity_score=0.85,
    )
    db_session.add(analysis)
    await db_session.commit()
    await db_session.refresh(analysis)
    return analysis


@pytest.mark.asyncio
async def test_ai_service_with_ollama_client(
    db_session: AsyncSession, sample_analysis: Analysis, sample_user: User
) -> None:
    """Verify AIService routes through OllamaClient cleanly."""
    ollama = OllamaClient(model="llama3.2")
    ai_service = AIService(db_session, llm_client=ollama)

    structured_content = (
        '{"summary": "Top tier candidate for FastAPI stack.", '
        '"strengths": ["FastAPI", "Python"], '
        '"areas_for_growth": ["Docker"], '
        '"match_verdict": "Strong Match"}'
    )
    mock_resp = httpx.Response(
        status_code=200,
        json={
            "model": "llama3.2",
            "message": {"role": "assistant", "content": structured_content},
            "done": True,
        },
        request=httpx.Request("POST", "http://test"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await ai_service.explain_analysis(analysis_id=sample_analysis.id, user_id=sample_user.id)
        assert res.analysis_id == sample_analysis.id
        assert res.degraded is False
        assert res.explanation_status == "available"
        assert res.explanation is not None
        assert res.explanation.summary == "Top tier candidate for FastAPI stack."
        assert res.compatibility_score == 92.0  # Independent ML score preserved


@pytest.mark.asyncio
async def test_ai_service_graceful_degradation_when_ollama_unavailable(
    db_session: AsyncSession, sample_analysis: Analysis, sample_user: User
) -> None:
    """Verify AIService gracefully degrades when Ollama server is unreachable."""
    ollama = OllamaClient()
    ai_service = AIService(db_session, llm_client=ollama)

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Refused")):
        res = await ai_service.explain_analysis(
            analysis_id=sample_analysis.id,
            user_id=sample_user.id,
            force_refresh=True,
        )
        assert res.compatibility_score == 92.0  # ML score preserved!
        assert res.degraded is True
        assert res.explanation_status == "unavailable"
        assert res.explanation is None


@pytest.mark.asyncio
async def test_rag_pipeline_with_ollama_client(db_session: AsyncSession, sample_user: User) -> None:
    """Verify RAGPipeline synthesizes answers with source citations using OllamaClient."""
    vector_store = InMemoryVectorStore()
    chunk = VectorChunk(
        id="c1",
        vector=[1.0, 0.0, 0.0],
        text="Alice is a lead DevOps engineer with Kubernetes and Docker experience.",
        metadata={"user_id": sample_user.id, "document_id": 10, "filename": "alice_cv.pdf", "chunk_index": 0},
    )
    await vector_store.add_chunks([chunk])

    embedder = AsyncMock()
    embedder.embed_query.return_value = [1.0, 0.0, 0.0]

    ollama = OllamaClient(model="llama3.2")
    rag = RAGPipeline(session=db_session, vector_store=vector_store, embedder=embedder, llm_client=ollama)

    mock_resp = httpx.Response(
        status_code=200,
        json={
            "model": "llama3.2",
            "message": {
                "role": "assistant",
                "content": "Alice has extensive Kubernetes and Docker experience according to alice_cv.pdf.",
            },
            "done": True,
        },
        request=httpx.Request("POST", "http://test"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = await rag.query(user_id=sample_user.id, question="What is Alice's experience?")
        assert res.has_answer is True
        assert "Kubernetes and Docker" in res.answer
        assert len(res.citations) == 1
        assert res.citations[0].document_id == 10
        assert res.citations[0].filename == "alice_cv.pdf"


@pytest.mark.asyncio
async def test_rag_pipeline_fallback_when_ollama_unavailable(db_session: AsyncSession, sample_user: User) -> None:
    """Verify RAGPipeline graceful snippet fallback when Ollama is offline without hallucinating."""
    vector_store = InMemoryVectorStore()
    chunk = VectorChunk(
        id="c2",
        vector=[1.0, 0.0],
        text="Candidate profile: Python, FastAPI and SQLite.",
        metadata={"user_id": sample_user.id, "document_id": 20, "filename": "skills.txt", "chunk_index": 0},
    )
    await vector_store.add_chunks([chunk])

    embedder = AsyncMock()
    embedder.embed_query.return_value = [1.0, 0.0]

    ollama = OllamaClient()
    rag = RAGPipeline(session=db_session, vector_store=vector_store, embedder=embedder, llm_client=ollama)

    # When Ollama call fails:
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Refused")):
        res = await rag.query(user_id=sample_user.id, question="What skills does candidate have?")
        assert res.has_answer is True
        assert len(res.citations) == 1
        # Fallback snippet attribution is provided without crash:
        assert "Python, FastAPI and SQLite" in res.answer
