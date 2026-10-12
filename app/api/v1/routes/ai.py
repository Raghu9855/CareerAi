"""FastAPI router for AI / LLM explanations and interview preparation endpoints."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import AIAnalysisResult
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI & LLM Services"])


@router.post(
    "/explain/{analysis_id}",
    response_model=AIAnalysisResult,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit(requests_per_minute=20))],
    summary="Generate LLM Analysis Explanation",
    description=(
        "Synthesizes candidate compatibility, highlights verified strengths, diagnoses critical skill gaps, "
        "and provides an actionable match verdict with graceful degradation."
    ),
)
async def explain_analysis(
    analysis_id: int,
    force_refresh: bool = Query(default=False, description="Bypass cache and regenerate with LLM"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIAnalysisResult:
    """Produce or retrieve structured LLM explanation for an existing analysis."""
    service = AIService(db)
    return await service.explain_analysis(
        analysis_id=analysis_id,
        user_id=current_user.id,
        force_refresh=force_refresh,
    )


@router.post(
    "/interview-prep/{analysis_id}",
    response_model=AIAnalysisResult,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit(requests_per_minute=20))],
    summary="Generate Tailored Interview Questions & Guidance",
    description=(
        "Generates role-specific technical questions, STAR-focused behavioral prompts, and preparation tips "
        "targeting identified skill gaps."
    ),
)
async def generate_interview_prep(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIAnalysisResult:
    """Generate interview prep recommendations tailored to analysis results."""
    service = AIService(db)
    return await service.generate_interview_prep(
        analysis_id=analysis_id,
        user_id=current_user.id,
    )
