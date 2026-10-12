"""ApplicationService managing job application pipelines and ownership verification."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.application import Application, ApplicationStatus
from app.models.job import JobStatus
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.schemas.application import ApplicationCreate, ApplicationFilter, ApplicationUpdate
from app.schemas.common import PaginationParams


class ApplicationService:
    """Business operations for tracking job applications."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ApplicationRepository(session)
        self.job_repo = JobRepository(session)

    async def apply_to_job(self, user_id: int, payload: ApplicationCreate) -> Application:
        """Create a job application for a user, validating job status and duplicate applications."""
        job = await self.job_repo.get_by_id(payload.job_id)
        if not job:
            raise NotFoundError(
                message=f"Job with ID {payload.job_id} not found",
                details={"job_id": payload.job_id},
            )

        if job.status != JobStatus.OPEN:
            raise ValidationError(
                message="Cannot apply to a job that is not currently open",
                details={"job_id": payload.job_id, "job_status": job.status},
            )

        existing = await self.repo.get_by_user_and_job(user_id, payload.job_id)
        if existing:
            raise ConflictError(
                message="You have already submitted an application for this job",
                details={"job_id": payload.job_id, "application_id": existing.id},
            )

        application = Application(
            user_id=user_id,
            job_id=payload.job_id,
            status=ApplicationStatus.APPLIED,
            notes=payload.notes,
        )
        created = await self.repo.create(application)
        reloaded = await self.repo.get_with_job(created.id)
        return reloaded or created

    async def get_application(
        self,
        application_id: int,
        requesting_user_id: int,
        is_admin: bool = False,
    ) -> Application:
        """Fetch application details enforcing tenant ownership checks."""
        application = await self.repo.get_with_job(application_id)
        if not application:
            raise NotFoundError(
                message=f"Application with ID {application_id} not found",
                details={"application_id": application_id},
            )

        if not is_admin and application.user_id != requesting_user_id:
            raise ForbiddenError(
                message="You do not have permission to access this application",
                details={"application_id": application_id},
            )

        return application

    async def list_applications(
        self,
        user_id: int,
        filters: ApplicationFilter,
        params: PaginationParams,
    ) -> tuple[Sequence[Application], int]:
        """Fetch paginated applications strictly scoped to the requesting user."""
        return await self.repo.list_by_user(
            user_id=user_id,
            filters=filters,
            offset=params.offset,
            limit=params.per_page,
        )

    async def update_application(
        self,
        application_id: int,
        payload: ApplicationUpdate,
        requesting_user_id: int,
        is_admin: bool = False,
    ) -> Application:
        """Update an application status or notes with ownership validation."""
        application = await self.get_application(application_id, requesting_user_id, is_admin=is_admin)

        update_data = payload.model_dump(exclude_unset=True)
        updated = await self.repo.update(application, update_data)
        reloaded = await self.repo.get_with_job(updated.id)
        return reloaded or updated

    async def withdraw_application(self, application_id: int, requesting_user_id: int) -> Application:
        """Withdraw an application."""
        application = await self.get_application(application_id, requesting_user_id)
        if application.status in (ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN):
            raise ValidationError(
                message=f"Application cannot be withdrawn from state '{application.status}'",
                details={"status": application.status},
            )

        updated = await self.repo.update(application, {"status": ApplicationStatus.WITHDRAWN})
        reloaded = await self.repo.get_with_job(updated.id)
        return reloaded or updated

    async def delete_application(
        self,
        application_id: int,
        requesting_user_id: int,
        is_admin: bool = False,
    ) -> None:
        """Delete an application with ownership validation."""
        application = await self.get_application(application_id, requesting_user_id, is_admin=is_admin)
        await self.repo.delete(application, soft=True)
