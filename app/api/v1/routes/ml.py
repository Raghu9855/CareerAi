"""FastAPI router for ML compatibility scoring and skill-gap endpoints."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.ml import AnalyzeRequest, AnalyzeResponse, ModelInfoResponse
from app.services.ml_service import MLService

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(requests_per_minute=30))],
    summary="Compute Job Fit Compatibility & Skill-Gap Analysis",
    description=(
        "Extracts skills, computes TF-IDF semantic similarities, and predicts fit score (0-100) using trained ML model."
    ),
)
async def analyze_compatibility(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    """Analyze compatibility between candidate materials and job description."""
    service = MLService(db)
    analysis = await service.analyze(request=request, user_id=current_user.id)
    return AnalyzeResponse.model_validate(analysis)


@router.get(
    "/analyses",
    response_model=PaginatedResponse[AnalyzeResponse],
    summary="List Past Fit Analyses",
    description="Retrieve paginated history of ML fit analyses executed by the current user.",
)
async def list_analyses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AnalyzeResponse]:
    """List historical analyses for authenticated user."""
    service = MLService(db)
    params = PaginationParams(page=page, page_size=page_size)
    items, total = await service.list_analyses(user_id=current_user.id, params=params)
    return PaginatedResponse.create(
        items=[AnalyzeResponse.model_validate(i) for i in items],
        total=total,
        params=params,
    )


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalyzeResponse,
    summary="Get Fit Analysis by ID",
    description="Retrieve a specific compatibility analysis record with matched and missing skill rankings.",
)
async def get_analysis_by_id(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    """Retrieve specific analysis by ID with ownership enforcement."""
    service = MLService(db)
    is_admin = current_user.role.value == "admin"
    analysis = await service.get_analysis(analysis_id, current_user.id, is_admin=is_admin)
    return AnalyzeResponse.model_validate(analysis)


@router.get(
    "/model",
    response_model=ModelInfoResponse,
    summary="Model Registry Info & Limitations",
    description="Returns active ML model version, features, test performance metrics, and documented limitations.",
)
def get_model_info(
    db: AsyncSession = Depends(get_db),
) -> ModelInfoResponse:
    """Return model version, metrics, and documented limitations."""
    service = MLService(db)
    return service.get_model_info()
