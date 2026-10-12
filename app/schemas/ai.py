"""Pydantic v2 schemas for structured LLM explanations and interview-prep recommendations."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalysisExplanation(BaseModel):
    """Structured LLM analysis explanation of compatibility and skill gaps."""

    summary: str = Field(description="High-level synthesis of candidate qualifications and fit")
    strengths: list[str] = Field(default_factory=list, description="Key candidate strengths relative to the role")
    areas_for_growth: list[str] = Field(
        default_factory=list,
        description="Targeted skill gaps and improvement recommendations",
    )
    match_verdict: str = Field(description="Match verdict classification, e.g. Strong Match, Moderate Match")


class InterviewQuestion(BaseModel):
    """Specific technical or behavioral interview question tailored to the role."""

    question: str
    expected_key_concepts: str | None = None
    tip: str | None = None
    star_focus: str | None = None


class InterviewPrepRecommendation(BaseModel):
    """Structured interview preparation guidance."""

    technical_questions: list[InterviewQuestion] = Field(default_factory=list)
    behavioral_questions: list[InterviewQuestion] = Field(default_factory=list)
    preparation_tips: list[str] = Field(default_factory=list)


class ExplainRequest(BaseModel):
    """Request to generate LLM explanation for an existing analysis."""

    analysis_id: int
    force_refresh: bool = False


class InterviewPrepRequest(BaseModel):
    """Request to generate interview prep for an existing analysis."""

    analysis_id: int


class AIAnalysisResult(BaseModel):
    """Unified response combining ML score and structured LLM outputs."""

    model_config = ConfigDict(from_attributes=True)

    analysis_id: int
    compatibility_score: float
    skill_match_score: float
    matched_skills: list[str]
    missing_skills: list[dict[str, Any]]
    model_version: str
    explanation: AnalysisExplanation | None = None
    interview_prep: InterviewPrepRecommendation | None = None
    explanation_status: str = Field(
        default="available",
        description="Status of LLM explanation: 'available', 'cached', or 'unavailable' (graceful degradation)",
    )
    degraded: bool = Field(default=False, description="True if LLM failed and response degraded to ML only")
