"""SQLAlchemy 2.0 Analysis model for ML job/candidate fit scoring."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.job import Job
    from app.models.user import User


class Analysis(Base, TimestampMixin, SoftDeleteMixin):
    """Stores compatibility scoring, skill gaps, model version, and AI explanations."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # ML fit metrics
    compatibility_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    skill_match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    text_similarity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Extracted skill lists
    matched_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    # Model metadata
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")

    # LLM explanations (populated in Phase 6)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    interview_prep: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="selectin")
    job: Mapped["Job | None"] = relationship("Job", lazy="selectin")
    document: Mapped["Document | None"] = relationship("Document", lazy="selectin")
