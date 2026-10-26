"""Service orchestrating LLM prompt construction, structured output parsing, and graceful degradation."""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.client import LLMClient, LLMMessage
from app.ai.llm.factory import get_llm_client
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.repositories.analysis_repo import AnalysisRepository
from app.schemas.ai import (
    AIAnalysisResult,
    AnalysisExplanation,
    InterviewPrepRecommendation,
)

logger = get_logger("careerai.services.ai")


class AIService:
    """Orchestrates AI prompt engineering, structured LLM generation, and resilient fallback."""

    def __init__(
        self,
        session: AsyncSession,
        llm_client: LLMClient | None = None,
        analysis_repo: AnalysisRepository | None = None,
    ) -> None:
        self.session = session
        self.llm_client = llm_client or get_llm_client()
        self.analysis_repo = analysis_repo or AnalysisRepository(session)

    async def explain_analysis(
        self,
        analysis_id: int,
        user_id: int,
        force_refresh: bool = False,
    ) -> AIAnalysisResult:
        """Generate structured LLM explanation for an existing ML fit analysis with graceful degradation."""
        # 1. Fetch analysis and enforce ownership
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis or analysis.user_id != user_id:
            raise NotFoundError(message="Analysis record not found", details={"analysis_id": analysis_id})

        # 2. Check if cached explanation exists in database
        if analysis.llm_explanation and not force_refresh:
            try:
                parsed = json.loads(analysis.llm_explanation)
                cached_explanation = AnalysisExplanation.model_validate(parsed)
                prep_obj = None
                if analysis.interview_prep:
                    prep_obj = InterviewPrepRecommendation.model_validate(analysis.interview_prep)

                return AIAnalysisResult(
                    analysis_id=analysis.id,
                    compatibility_score=analysis.compatibility_score,
                    skill_match_score=analysis.skill_match_score,
                    matched_skills=analysis.matched_skills or [],
                    missing_skills=analysis.missing_skills or [],
                    model_version=analysis.model_version,
                    explanation=cached_explanation,
                    interview_prep=prep_obj,
                    explanation_status="cached",
                    degraded=False,
                )
            except Exception as exc:
                logger.warning(f"Failed parsing cached explanation for analysis {analysis_id}: {exc}")

        # 3. Build structured prompt
        missing_names = [m.get("skill", "") for m in (analysis.missing_skills or [])]
        messages = [
            LLMMessage(
                role="system",
                content=(
                    "You are CareerAI, an expert technical recruiter and talent advisor. "
                    "Analyze the candidate's compatibility score, matched skills, and skill gaps for the role. "
                    "Respond ONLY with a valid JSON object matching the following schema:\n"
                    "{\n"
                    '  "summary": "High-level 2-3 sentence overview of candidate match",\n'
                    '  "strengths": ["Strength 1", "Strength 2", "Strength 3"],\n'
                    '  "areas_for_growth": ["Targeted gap or improvement area 1", "area 2"],\n'
                    '  "match_verdict": "Strong Match" | "Moderate Match" | "Growth Opportunity"\n'
                    "}"
                ),
            ),
            LLMMessage(
                role="user",
                content=(
                    f"Overall Compatibility Score: {analysis.compatibility_score}/100\n"
                    f"Skill Match Percentage: {analysis.skill_match_score}%\n"
                    f"Matched Skills: {', '.join(analysis.matched_skills or ['None identified'])}\n"
                    f"Ranked Skill Gaps: {', '.join(missing_names or ['None identified'])}\n"
                    "Please provide the structured fit explanation."
                ),
            ),
        ]

        # 4. Invoke LLM with Graceful Degradation Fallback
        explanation_obj: AnalysisExplanation | None = None
        degraded = False
        status_label = "available"

        try:
            response = await self.llm_client.generate(
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            parsed_json = self._extract_json(response.content)
            explanation_obj = AnalysisExplanation.model_validate(parsed_json)

            # Persist explanation to database
            analysis.llm_explanation = json.dumps(explanation_obj.model_dump())
            await self.session.commit()
            logger.info(f"Generated and saved LLM explanation for analysis {analysis_id}")

        except Exception as exc:
            logger.error(
                f"LLM explanation generation failed for analysis {analysis_id}: {exc}. "
                "Engaging graceful degradation: returning ML results only."
            )
            degraded = True
            status_label = "unavailable"
            explanation_obj = None

        prep_obj = None
        if analysis.interview_prep:
            try:
                prep_obj = InterviewPrepRecommendation.model_validate(analysis.interview_prep)
            except Exception:
                prep_obj = None

        return AIAnalysisResult(
            analysis_id=analysis.id,
            compatibility_score=analysis.compatibility_score,
            skill_match_score=analysis.skill_match_score,
            matched_skills=analysis.matched_skills or [],
            missing_skills=analysis.missing_skills or [],
            model_version=analysis.model_version,
            explanation=explanation_obj,
            interview_prep=prep_obj,
            explanation_status=status_label,
            degraded=degraded,
        )

    async def generate_interview_prep(
        self,
        analysis_id: int,
        user_id: int,
    ) -> AIAnalysisResult:
        """Generate structured interview preparation questions and guidance."""
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis or analysis.user_id != user_id:
            raise NotFoundError(message="Analysis record not found", details={"analysis_id": analysis_id})

        missing_names = [m.get("skill", "") for m in (analysis.missing_skills or [])]
        messages = [
            LLMMessage(
                role="system",
                content=(
                    "You are an expert technical interviewer. Based on the candidate fit profile and skill gaps, "
                    "produce tailored interview questions and preparation advice. Respond ONLY with valid JSON:\n"
                    "{\n"
                    '  "technical_questions": [{"question": "...", "expected_key_concepts": "...", "tip": "..."}],\n'
                    '  "behavioral_questions": [{"question": "...", "star_focus": "..."}],\n'
                    '  "preparation_tips": ["tip 1", "tip 2"]\n'
                    "}"
                ),
            ),
            LLMMessage(
                role="user",
                content=(
                    f"Fit Score: {analysis.compatibility_score}/100\n"
                    f"Verified Skills: {', '.join(analysis.matched_skills or [])}\n"
                    f"Missing Skills to Test: {', '.join(missing_names or [])}\n"
                    "Generate rigorous interview questions targeting both verified skills and growth areas."
                ),
            ),
        ]

        prep_obj: InterviewPrepRecommendation | None = None
        degraded = False
        status_label = "available"

        try:
            response = await self.llm_client.generate(
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            parsed_json = self._extract_json(response.content)
            prep_obj = InterviewPrepRecommendation.model_validate(parsed_json)

            analysis.interview_prep = prep_obj.model_dump()
            await self.session.commit()
            logger.info(f"Saved interview prep recommendations for analysis {analysis_id}")
        except Exception as exc:
            logger.error(f"Interview prep generation failed for analysis {analysis_id}: {exc}")
            degraded = True
            status_label = "unavailable"
            prep_obj = None

        explanation_obj = None
        if analysis.llm_explanation:
            try:
                explanation_obj = AnalysisExplanation.model_validate(json.loads(analysis.llm_explanation))
            except Exception:
                explanation_obj = None

        return AIAnalysisResult(
            analysis_id=analysis.id,
            compatibility_score=analysis.compatibility_score,
            skill_match_score=analysis.skill_match_score,
            matched_skills=analysis.matched_skills or [],
            missing_skills=analysis.missing_skills or [],
            model_version=analysis.model_version,
            explanation=explanation_obj,
            interview_prep=prep_obj,
            explanation_status=status_label,
            degraded=degraded,
        )

    def _extract_json(self, raw_text: str) -> dict[str, Any]:
        """Strip thinking tags, markdown fences, and preambles to reliably decode JSON object."""
        import re

        text = raw_text.strip()
        # Strip reasoning model thinking tags if present (e.g. DeepSeek/Qwen)
        text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

        # Locate outer JSON curly braces
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Fallback to markdown fence stripping
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)
        if not isinstance(result, dict):
            raise ValueError("Expected JSON object, got non-dict JSON")
        return result
