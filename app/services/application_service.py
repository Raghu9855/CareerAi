"""ApplicationService managing job application pipelines and ownership verification."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.application import Application, ApplicationStatus
from app.models.job import JobStatus
from app.models.webhook import WebhookEvent
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.schemas.application import ApplicationCreate, ApplicationFilter, ApplicationUpdate
from app.schemas.common import PaginationParams

logger = get_logger("careerai.services.application")


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
        result = reloaded or created

        # Dispatch webhook event (non-blocking; swallow errors)
        await self._fire_webhook(
            user_id=user_id,
            event=WebhookEvent.APPLICATION_CREATED,
            data={
                "application_id": result.id,
                "job_id": result.job_id,
                "status": result.status,
            },
        )
        return result

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
        previous_status = application.status

        update_data = payload.model_dump(exclude_unset=True)
        updated = await self.repo.update(application, update_data)
        reloaded = await self.repo.get_with_job(updated.id)
        result = reloaded or updated

        # Dispatch webhook if status changed
        new_status = result.status
        if payload.status is not None and new_status != previous_status:
            await self._fire_webhook(
                user_id=requesting_user_id,
                event=WebhookEvent.APPLICATION_STATUS_CHANGED,
                data={
                    "application_id": result.id,
                    "job_id": result.job_id,
                    "previous_status": previous_status,
                    "new_status": new_status,
                },
            )
        return result

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
        result = reloaded or updated

        await self._fire_webhook(
            user_id=requesting_user_id,
            event=WebhookEvent.APPLICATION_WITHDRAWN,
            data={
                "application_id": result.id,
                "job_id": result.job_id,
                "status": ApplicationStatus.WITHDRAWN,
            },
        )
        return result

    async def delete_application(
        self,
        application_id: int,
        requesting_user_id: int,
        is_admin: bool = False,
    ) -> None:
        """Delete an application with ownership validation."""
        application = await self.get_application(application_id, requesting_user_id, is_admin=is_admin)
        job_id = application.job_id
        await self.repo.delete(application, soft=True)

        await self._fire_webhook(
            user_id=requesting_user_id,
            event=WebhookEvent.APPLICATION_DELETED,
            data={"application_id": application_id, "job_id": job_id},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fire_webhook(self, user_id: int, event: str, data: dict) -> None:
        """Dispatch a webhook event with graceful error swallowing.

        Webhook delivery failures must NEVER break the application API, so all
        exceptions are caught and logged here.
        """
        try:
            from app.services.webhook_service import WebhookService

            wh_service = WebhookService(self.session)
            await wh_service.dispatch_event(user_id=user_id, event=event, data=data)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Webhook dispatch failed silently for event '{event}' user_id={user_id}: {exc}")
