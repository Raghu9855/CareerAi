"""Unit tests for AIService business logic, caching, isolation, and graceful degradation."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.mock import MockLLMClient
from app.core.errors import NotFoundError
from app.models.analysis import Analysis
from app.models.user import User, UserRole
from app.services.ai_service import AIService


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """Fixture creating a test user in DB."""
    user = User(
        email="ai_test_candidate@example.com",
        hashed_password="hashed_pw_test",
        full_name="AI Candidate",
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
        compatibility_score=88.5,
        skill_match_score=85.0,
        model_version="random-forest-v1.0",
        matched_skills=["Python", "FastAPI", "MySQL"],
        missing_skills=[{"skill": "Kubernetes", "importance": "high"}],
        text_similarity_score=0.8,
    )
    db_session.add(analysis)
    await db_session.commit()
    await db_session.refresh(analysis)
    return analysis


@pytest.mark.asyncio
async def test_ai_service_explain_analysis_happy_path(
    db_session: AsyncSession, sample_analysis: Analysis, sample_user: User
) -> None:
    """Verify AIService generates structured explanation and persists it."""
    mock_llm = MockLLMClient()
    ai_service = AIService(db_session, llm_client=mock_llm)

    res = await ai_service.explain_analysis(analysis_id=sample_analysis.id, user_id=sample_user.id)
    assert res.analysis_id == sample_analysis.id
    assert res.compatibility_score == 88.5
    assert res.explanation is not None
    assert res.explanation.summary != ""
    assert res.explanation_status == "available"
    assert res.degraded is False

    # Second call should fetch cached version
    cached_res = await ai_service.explain_analysis(analysis_id=sample_analysis.id, user_id=sample_user.id)
    assert cached_res.explanation_status == "cached"


@pytest.mark.asyncio
async def test_ai_service_cross_user_isolation(
    db_session: AsyncSession, sample_analysis: Analysis
) -> None:
    """Verify other user cannot request explanation for foreign analysis."""
    mock_llm = MockLLMClient()
    ai_service = AIService(db_session, llm_client=mock_llm)

    with pytest.raises(NotFoundError):
        await ai_service.explain_analysis(analysis_id=sample_analysis.id, user_id=99999)


@pytest.mark.asyncio
async def test_ai_service_interview_prep_happy_path(
    db_session: AsyncSession, sample_analysis: Analysis, sample_user: User
) -> None:
    """Verify AIService generates interview prep recommendations."""
    mock_llm = MockLLMClient()
    ai_service = AIService(db_session, llm_client=mock_llm)

    res = await ai_service.generate_interview_prep(analysis_id=sample_analysis.id, user_id=sample_user.id)
    assert res.interview_prep is not None
    assert len(res.interview_prep.technical_questions) >= 1
    assert len(res.interview_prep.preparation_tips) >= 1


@pytest.mark.asyncio
async def test_ai_service_graceful_degradation_when_llm_fails(
    db_session: AsyncSession, sample_analysis: Analysis, sample_user: User
) -> None:
    """Verify that when LLM encounters failure, ML compatibility score is returned with degraded=True."""
    faulty_llm = AsyncMock()
    faulty_llm.generate.side_effect = RuntimeError("OpenAI 503 Service Unavailable")

    ai_service = AIService(db_session, llm_client=faulty_llm)

    res = await ai_service.explain_analysis(
        analysis_id=sample_analysis.id, user_id=sample_user.id, force_refresh=True
    )
    assert res.compatibility_score == 88.5
    assert res.explanation_status == "unavailable"
    assert res.degraded is True
    assert res.explanation is None
