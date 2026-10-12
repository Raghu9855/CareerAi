"""Unit tests verifying edge cases and domain exceptions in Service layers."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.application import ApplicationStatus
from app.models.job import JobStatus
from app.schemas.application import ApplicationCreate
from app.schemas.job import JobCreate, JobUpdate
from app.schemas.profile import ProfileCreate
from app.schemas.skill import SkillCreate, SkillUpdate, UserSkillCreate, UserSkillUpdate
from app.schemas.user import UserCreate, UserUpdate
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.profile_service import ProfileService
from app.services.skill_service import SkillService
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_user_service_edge_cases(db_session: AsyncSession) -> None:
    """Verifies UserService conflict and not found validations."""
    service = UserService(db_session)

    # 1. User not found
    with pytest.raises(NotFoundError):
        await service.get_user_by_id(999999)

    # 2. Create users
    u1 = await service.create_user(UserCreate(email="user1@domain.com", password="Password123!", full_name="User 1"))
    u2 = await service.create_user(UserCreate(email="user2@domain.com", password="Password123!", full_name="User 2"))

    # 3. Duplicate email on update
    with pytest.raises(ConflictError):
        await service.update_user(u2.id, UserUpdate(email="user1@domain.com"))

    # 4. Get by email
    found = await service.get_user_by_email("user1@domain.com")
    assert found is not None
    assert found.id == u1.id


@pytest.mark.asyncio
async def test_profile_service_edge_cases(db_session: AsyncSession) -> None:
    """Verifies ProfileService validations."""
    service = ProfileService(db_session)

    # User does not exist
    with pytest.raises(NotFoundError):
        await service.create_or_update_profile(999999, ProfileCreate(headline="Non-existent user"))


@pytest.mark.asyncio
async def test_skill_service_edge_cases(db_session: AsyncSession) -> None:
    """Verifies SkillService validations."""
    service = SkillService(db_session)
    user_svc = UserService(db_session)
    user = await user_svc.create_user(
        UserCreate(email="skilltester@domain.com", password="Password123!", full_name="Skill Tester")
    )

    # Create skill
    skill = await service.create_skill(SkillCreate(name="Docker", category="DevOps"))

    # Update skill
    updated_skill = await service.update_skill(skill.id, SkillUpdate(name="Docker Engine"))
    assert updated_skill.name == "Docker Engine"

    # Skill not found on update
    with pytest.raises(NotFoundError):
        await service.update_skill(999999, SkillUpdate(name="Ghost"))

    # Add skill to non-existent user
    with pytest.raises(NotFoundError):
        await service.add_user_skill(999999, UserSkillCreate(skill_id=skill.id))

    # Add non-existent skill to user
    with pytest.raises(NotFoundError):
        await service.add_user_skill(user.id, UserSkillCreate(skill_id=999999))

    # Update non-existent user skill
    with pytest.raises(NotFoundError):
        await service.update_user_skill(user.id, 999999, UserSkillUpdate(years_of_experience=2.0))

    # Delete non-existent user skill
    with pytest.raises(NotFoundError):
        await service.remove_user_skill(user.id, 999999)


@pytest.mark.asyncio
async def test_job_service_edge_cases(db_session: AsyncSession) -> None:
    """Verifies JobService salary range validation on update."""
    service = JobService(db_session)

    job = await service.create_job(
        JobCreate(
            title="SRE Lead",
            company="Cloud Corp",
            description="Leading SRE site reliability operations.",
            salary_min=100000.0,
            salary_max=150000.0,
        )
    )

    # Job not found
    with pytest.raises(NotFoundError):
        await service.get_job(999999)

    # Update with invalid salary range (min > max)
    with pytest.raises(ValidationError):
        await service.update_job(job.id, JobUpdate(salary_min=200000.0))


@pytest.mark.asyncio
async def test_application_service_edge_cases(db_session: AsyncSession) -> None:
    """Verifies ApplicationService status transition and validation errors."""
    app_svc = ApplicationService(db_session)
    user_svc = UserService(db_session)
    job_svc = JobService(db_session)

    user = await user_svc.create_user(
        UserCreate(email="candidate@domain.com", password="Password123!", full_name="Candidate")
    )
    job = await job_svc.create_job(
        JobCreate(
            title="ML Engineer",
            company="DeepAI",
            description="Developing transformer architectures.",
            status=JobStatus.OPEN,
        )
    )

    # Job not found
    with pytest.raises(NotFoundError):
        await app_svc.apply_to_job(user.id, ApplicationCreate(job_id=999999))

    # Apply
    app = await app_svc.apply_to_job(user.id, ApplicationCreate(job_id=job.id))

    # Withdraw application
    withdrawn = await app_svc.withdraw_application(app.id, user.id)
    assert withdrawn.status == ApplicationStatus.WITHDRAWN

    # Withdrawing again raises ValidationError
    with pytest.raises(ValidationError):
        await app_svc.withdraw_application(app.id, user.id)
