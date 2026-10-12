"""SQLAlchemy 2.0 Job model and enums."""

import enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.user import User


class JobType(enum.StrEnum):
    """Employment type classifications."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    REMOTE = "remote"


class JobStatus(enum.StrEnum):
    """Job listing publication status."""

    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class Job(Base, TimestampMixin, SoftDeleteMixin):
    """Job posting entity."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    company: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), default="Remote", nullable=True)
    job_type: Mapped[JobType] = mapped_column(
        Enum(JobType, native_enum=False, length=20),
        default=JobType.FULL_TIME,
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=20),
        default=JobStatus.OPEN,
        nullable=False,
        index=True,
    )
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    applications: Mapped[list["Application"]] = relationship(
        "Application",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    created_by: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company}', status='{self.status}')>"
