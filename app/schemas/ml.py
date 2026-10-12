"""Pydantic v2 schemas for ML compatibility and skill-gap endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SkillGapItem(BaseModel):
    """Ranked skill gap representation."""

    skill: str
    importance: str = Field(description="Importance level: high, medium, or low")
    job_frequency: int = Field(ge=1, description="Number of occurrences in job description")


class AnalyzeRequest(BaseModel):
    """Request payload for compatibility fit analysis."""

    job_id: int | None = Field(default=None, description="Existing job ID to evaluate against")
    document_id: int | None = Field(default=None, description="Uploaded resume/document ID")
    job_description: str | None = Field(default=None, description="Raw job description text")
    resume_text: str | None = Field(default=None, description="Raw resume text")
    use_profile: bool = Field(default=False, description="Use current authenticated user's profile and skills")

    @model_validator(mode="after")
    def validate_inputs(self) -> "AnalyzeRequest":
        """Verify that at least one candidate source and one job source are specified."""
        has_candidate = bool(self.document_id or (self.resume_text and self.resume_text.strip()) or self.use_profile)
        has_job = bool(self.job_id or (self.job_description and self.job_description.strip()))

        if not has_candidate:
            raise ValueError(
                "Must provide at least one candidate source: 'document_id', 'resume_text', or 'use_profile=True'."
            )
        if not has_job:
            raise ValueError(
                "Must provide at least one job source: 'job_id' or 'job_description'."
            )
        return self


class AnalyzeResponse(BaseModel):
    """Detailed result of compatibility analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="Database record ID if persisted")
    user_id: int = Field(description="Owner user ID")
    job_id: int | None = Field(default=None)
    document_id: int | None = Field(default=None)
    compatibility_score: float = Field(ge=0.0, le=100.0, description="Overall fit score from 0 to 100")
    skill_match_score: float = Field(ge=0.0, le=100.0, description="Percentage of required skills matched")
    text_similarity_score: float = Field(ge=0.0, le=100.0, description="TF-IDF semantic similarity score")
    matched_skills: list[str] = Field(default_factory=list, description="Common skills identified")
    missing_skills: list[SkillGapItem] = Field(default_factory=list, description="Ranked missing skills")
    model_version: str = Field(description="ML model version used for scoring")
    latency_ms: float | None = Field(default=None, description="Execution time in milliseconds")
    llm_explanation: str | None = Field(default=None, description="AI explanation (populated in Phase 6)")
    interview_prep: dict[str, Any] | None = Field(default=None, description="Interview questions and guidance")
    created_at: datetime | None = Field(default=None)


class ModelInfoResponse(BaseModel):
    """Model registry metadata and operational status."""

    model_name: str
    model_version: str
    is_fallback: bool
    features: list[str]
    metrics: dict[str, Any]
    limitations: list[str]
