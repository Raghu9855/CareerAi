"""SQLAlchemy 2.0 Skill and UserSkill models."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ProficiencyLevel(enum.StrEnum):
    """Proficiency level for user skills."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class Skill(Base, TimestampMixin):
    """Global taxonomy of technical and soft skills."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="General", index=True, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # Relationships
    user_skills: Mapped[list["UserSkill"]] = relationship(
        "UserSkill",
        back_populates="skill",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name='{self.name}', category='{self.category}')>"


class UserSkill(Base, TimestampMixin):
    """Associative entity linking users to their skills with proficiency ratings."""

    __tablename__ = "user_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    proficiency: Mapped[ProficiencyLevel] = mapped_column(
        Enum(ProficiencyLevel, native_enum=False, length=20),
        default=ProficiencyLevel.INTERMEDIATE,
        nullable=False,
    )
    years_of_experience: Mapped[float | None] = mapped_column(Float, default=1.0, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="skills")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="user_skills")

    def __repr__(self) -> str:
        return (
            f"<UserSkill(id={self.id}, user_id={self.user_id}, "
            f"skill_id={self.skill_id}, proficiency='{self.proficiency}')>"
        )
