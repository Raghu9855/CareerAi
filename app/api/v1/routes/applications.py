"""Application tracking and pipeline endpoints with tenant ownership checks."""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_application_service, get_requesting_user_or_id
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
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    """Submit a new job application and start pipeline tracking."""
    uid, _ = user_auth
    application = await service.apply_to_job(user_id=uid, payload=payload)
    return ApplicationResponse.model_validate(application)


@router.get("", response_model=PaginatedResponse[ApplicationResponse], summary="List user applications")
async def list_applications(
    status_filter: ApplicationStatus | None = Query(default=None, alias="status", description="Filter by status"),
    job_id: int | None = Query(default=None, description="Filter by job ID"),
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: ApplicationService = Depends(get_application_service),
) -> PaginatedResponse[ApplicationResponse]:
    """Retrieve all job applications submitted by the user."""
    uid, _ = user_auth
    filters = ApplicationFilter(status=status_filter, job_id=job_id)
    params = PaginationParams(page=page, per_page=per_page)
    applications, total = await service.list_applications(user_id=uid, filters=filters, params=params)
    items = [ApplicationResponse.model_validate(a) for a in applications]
    return PaginatedResponse.create(items=items, total=total, params=params)


@router.get("/{application_id}", response_model=ApplicationResponse, summary="Get application details")
async def get_application(
    application_id: int,
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    """Retrieve full details of a specific job application."""
    uid, is_admin = user_auth
    application = await service.get_application(
        application_id=application_id,
        requesting_user_id=uid,
        is_admin=is_admin,
    )
    return ApplicationResponse.model_validate(application)


@router.put("/{application_id}", response_model=ApplicationResponse, summary="Update application")
async def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    """Update application pipeline status or notes."""
    uid, is_admin = user_auth
    application = await service.update_application(
        application_id=application_id,
        payload=payload,
        requesting_user_id=uid,
        is_admin=is_admin,
    )
    return ApplicationResponse.model_validate(application)


@router.post(
    "/{application_id}/withdraw",
    response_model=ApplicationResponse,
    summary="Withdraw application",
)
async def withdraw_application(
    application_id: int,
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    """Mark an application as withdrawn."""
    uid, _ = user_auth
    application = await service.withdraw_application(application_id=application_id, requesting_user_id=uid)
    return ApplicationResponse.model_validate(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete application")
async def delete_application(
    application_id: int,
    user_auth: tuple[int, bool] = Depends(get_requesting_user_or_id),
    service: ApplicationService = Depends(get_application_service),
) -> None:
    """Remove an application record."""
    uid, is_admin = user_auth
    await service.delete_application(
        application_id=application_id,
        requesting_user_id=uid,
        is_admin=is_admin,
    )
