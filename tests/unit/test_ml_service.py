"""Unit tests for MLService business logic, entity resolution, and error validation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.user import User, UserRole
from app.schemas.ml import AnalyzeRequest
from app.services.ml_service import MLService


@pytest.fixture
async def ml_test_user(db_session: AsyncSession) -> User:
    """Fixture creating user."""
    user = User(
        email="ml_tester@example.com",
        hashed_password="pw",
        full_name="ML Tester",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_ml_service_analyze_with_raw_text(
    db_session: AsyncSession, ml_test_user: User
) -> None:
    """Verify MLService analyze runs with raw text and persists analysis."""
    ml_service = MLService(db_session)
    req = AnalyzeRequest(
        resume_text="Senior Python Backend Developer with 5 years experience in FastAPI, MySQL, and Docker.",
        job_description="Seeking a Python Backend Engineer with strong expertise in FastAPI and MySQL.",
        job_skills=["Python", "FastAPI", "MySQL"],
    )

    analysis = await ml_service.analyze(req, user_id=ml_test_user.id)
    assert analysis.id is not None
    assert analysis.user_id == ml_test_user.id
    assert analysis.compatibility_score > 0
    assert "Python" in analysis.matched_skills
    assert analysis.model_version != ""


@pytest.mark.asyncio
async def test_ml_service_document_not_found(
    db_session: AsyncSession, ml_test_user: User
) -> None:
    """Verify non-existent document ID raises NotFoundError."""
    ml_service = MLService(db_session)
    req = AnalyzeRequest(document_id=99999, job_description="Job desc")
    with pytest.raises(NotFoundError) as exc:
        await ml_service.analyze(req, user_id=ml_test_user.id)
    assert "Document not found" in exc.value.message


@pytest.mark.asyncio
async def test_ml_service_document_cross_user_isolation(
    db_session: AsyncSession, ml_test_user: User
) -> None:
    """Verify document belonging to user 2 cannot be used by user 1."""
    # Create document for another user
    doc = Document(
        user_id=8888,
        filename="other.pdf",
        storage_path="path/other.pdf",
        mime_type="application/pdf",
        file_size=1024,
        doc_type=DocumentType.RESUME,
        status=DocumentStatus.READY,
        extracted_text="Some text",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    ml_service = MLService(db_session)
    req = AnalyzeRequest(document_id=doc.id, job_description="Job desc")
    with pytest.raises(NotFoundError):
        await ml_service.analyze(req, user_id=ml_test_user.id)


@pytest.mark.asyncio
async def test_ml_service_document_not_ready_raises_validation_error(
    db_session: AsyncSession, ml_test_user: User
) -> None:
    """Verify document with status=uploaded raises ValidationError."""
    doc = Document(
        user_id=ml_test_user.id,
        filename="pending.pdf",
        storage_path="path/pending.pdf",
        mime_type="application/pdf",
        file_size=1024,
        doc_type=DocumentType.RESUME,
        status=DocumentStatus.UPLOADED,
        extracted_text=None,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    ml_service = MLService(db_session)
    req = AnalyzeRequest(document_id=doc.id, job_description="Job desc")
    with pytest.raises(ValidationError) as exc:
        await ml_service.analyze(req, user_id=ml_test_user.id)
    assert "Document is not ready" in exc.value.message


@pytest.mark.asyncio
async def test_ml_service_job_not_found(
    db_session: AsyncSession, ml_test_user: User
) -> None:
    """Verify non-existent job ID raises NotFoundError."""
    ml_service = MLService(db_session)
    req = AnalyzeRequest(resume_text="Candidate text", job_id=99999)
    with pytest.raises(NotFoundError) as exc:
        await ml_service.analyze(req, user_id=ml_test_user.id)
    assert "Job not found" in exc.value.message


@pytest.mark.asyncio
async def test_ml_service_get_model_info(db_session: AsyncSession) -> None:
    """Verify get_model_info returns version, feature names, and metadata."""
    ml_service = MLService(db_session)
    info = ml_service.get_model_info()
    assert info.model_version != ""
    assert len(info.features) >= 1
