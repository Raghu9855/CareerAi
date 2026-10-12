"""Application tracking and pipeline endpoints."""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_application_service
from app.models.application import ApplicationStatus
from app.schemas.application import (
    ApplicationCreate,
    ApplicationFilter,
    ApplicationResponse,
    ApplicationUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.application_service import ApplicationService

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit job application",
)
async def apply_to_job(
    payload: ApplicationCreate,
    user_id: int = Query(..., description="ID of the applying user"),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    """Submit a new job application and start pipeline tracking."""
    application = await service.apply_to_job(user_id=user_id, payload=payload)
    return ApplicationResponse.model_validate(application)


@router.get("", response_model=PaginatedResponse[ApplicationResponse], summary="List user applications")
async def list_applications(
    user_id: int = Query(..., description="ID of the user"),
    status_filter: ApplicationStatus | None = Query(default=None, alias="status", description="Filter by status"),
    job_id: int | None = Query(default=None, description="Filter by job ID"),
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    service: ApplicationService = Depends(get_application_service),
) -> PaginatedResponse[ApplicationResponse]:
    """Retrieve all job applications submitted by the user."""
    filters = ApplicationFilter(status=status_filter, job_id=job_id)
    params = PaginationParams(page=page, per_page=per_page)
    applications, total = await service.list_applications(user_id=user_id, filters=filters, params=params)
    items = [ApplicationResponse.model_validate(a) for a in applications]
    return PaginatedResponse.create(items=items, total=total, params=params)


@router.get("/{application_id}", response_model=ApplicationResponse, summary="Get application details")
async def get_application(
    application_id: int,
    user_id: int = Query(..., description="Requesting user ID"),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    """Retrieve full details of a specific job application."""
    application = await service.get_application(application_id=application_id, requesting_user_id=user_id)
    return ApplicationResponse.model_validate(application)


@router.put("/{application_id}", response_model=ApplicationResponse, summary="Update application")
async def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    user_id: int = Query(..., description="Requesting user ID"),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    """Update application pipeline status or notes."""
    application = await service.update_application(
        application_id=application_id,
        payload=payload,
        requesting_user_id=user_id,
    )
    return ApplicationResponse.model_validate(application)


@router.post(
    "/{application_id}/withdraw",
    response_model=ApplicationResponse,
    summary="Withdraw application",
)
async def withdraw_application(
    application_id: int,
    user_id: int = Query(..., description="Requesting user ID"),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    """Mark an application as withdrawn."""
    application = await service.withdraw_application(application_id=application_id, requesting_user_id=user_id)
    return ApplicationResponse.model_validate(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete application")
async def delete_application(
    application_id: int,
    user_id: int = Query(..., description="Requesting user ID"),
    service: ApplicationService = Depends(get_application_service),
) -> None:
    """Remove an application record."""
    await service.delete_application(application_id=application_id, requesting_user_id=user_id)
