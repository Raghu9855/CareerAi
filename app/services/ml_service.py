"""Service orchestrating ML inference, input resolution, and database persistence."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.ml.inference import InferenceEngine
from app.ml.loader import get_model_loader
from app.models.analysis import Analysis
from app.models.document import DocumentStatus
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.repositories.profile_repo import ProfileRepository
from app.repositories.skill_repo import UserSkillRepository
from app.schemas.common import PaginationParams
from app.schemas.ml import AnalyzeRequest, ModelInfoResponse

logger = get_logger("careerai.services.ml")


class MLService:
    """Business logic for compatibility fit analysis and skill-gap exploration."""

    def __init__(
        self,
        session: AsyncSession,
        analysis_repo: AnalysisRepository | None = None,
        document_repo: DocumentRepository | None = None,
        job_repo: JobRepository | None = None,
        profile_repo: ProfileRepository | None = None,
        user_skill_repo: UserSkillRepository | None = None,
        inference_engine: InferenceEngine | None = None,
    ) -> None:
        self.session = session
        self.analysis_repo = analysis_repo or AnalysisRepository(session)
        self.document_repo = document_repo or DocumentRepository(session)
        self.job_repo = job_repo or JobRepository(session)
        self.profile_repo = profile_repo or ProfileRepository(session)
        self.user_skill_repo = user_skill_repo or UserSkillRepository(session)
        self.engine = inference_engine or InferenceEngine()

    async def analyze(self, request: AnalyzeRequest, user_id: int) -> Analysis:
        """Run ML compatibility analysis on specified inputs and persist result."""
        # 1. Resolve candidate text and skills
        candidate_text_parts: list[str] = []
        candidate_skills: list[str] = []

        if request.document_id:
            doc = await self.document_repo.get_by_id(request.document_id)
            if not doc:
                raise NotFoundError(message="Document not found", details={"document_id": request.document_id})
            if doc.user_id != user_id:
                raise NotFoundError(message="Document not found", details={"document_id": request.document_id})
            if doc.status != DocumentStatus.READY or not doc.extracted_text:
                raise ValidationError(
                    message=f"Document is not ready for analysis. Current status: {doc.status.value}",
                    details={"document_id": request.document_id, "status": doc.status.value},
                )
            candidate_text_parts.append(doc.extracted_text)

        if request.use_profile:
            profile = await self.profile_repo.get_by_user_id(user_id)
            if profile:
                if profile.headline:
                    candidate_text_parts.append(profile.headline)
                if profile.summary:
                    candidate_text_parts.append(profile.summary)
            user_skills = await self.user_skill_repo.list_by_user(user_id)
            for us in user_skills:
                if us.skill and us.skill.name:
                    candidate_skills.append(us.skill.name)

        if request.resume_text and request.resume_text.strip():
            candidate_text_parts.append(request.resume_text.strip())

        full_candidate_text = "\n\n".join(candidate_text_parts)
        if not full_candidate_text and not candidate_skills:
            raise ValidationError(message="No candidate text or profile content available for analysis")

        # 2. Resolve job description text
        job_text_parts: list[str] = []
        if request.job_id:
            job = await self.job_repo.get_by_id(request.job_id)
            if not job:
                raise NotFoundError(message="Job not found", details={"job_id": request.job_id})
            job_text_parts.append(f"Title: {job.title}")
            job_text_parts.append(job.description)

        if request.job_description and request.job_description.strip():
            job_text_parts.append(request.job_description.strip())

        full_job_text = "\n\n".join(job_text_parts)
        if not full_job_text:
            raise ValidationError(message="No job description text available for analysis")

        # 3. Execute ML inference pipeline
        result = self.engine.predict(
            resume_text=full_candidate_text,
            job_text=full_job_text,
            additional_candidate_skills=candidate_skills,
        )

        # 4. Persist analysis entity
        analysis = Analysis(
            user_id=user_id,
            job_id=request.job_id,
            document_id=request.document_id,
            compatibility_score=result.compatibility_score,
            skill_match_score=result.skill_match_score,
            text_similarity_score=result.text_similarity_score,
            matched_skills=result.matched_skills,
            missing_skills=result.missing_skills,
            model_version=result.model_version,
            latency_ms=result.latency_ms,
            status="completed",
        )

        saved = await self.analysis_repo.create(analysis)
        await self.session.commit()
        await self.session.refresh(saved)
        return saved

    async def list_analyses(
        self,
        user_id: int,
        params: PaginationParams,
    ) -> tuple[Sequence[Analysis], int]:
        """Fetch historical analyses for current user."""
        return await self.analysis_repo.list_by_user(user_id, params)

    async def get_analysis(
        self,
        analysis_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> Analysis:
        """Retrieve a specific analysis ensuring tenant ownership."""
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise NotFoundError(message="Analysis not found", details={"analysis_id": analysis_id})
        if not is_admin and analysis.user_id != user_id:
            raise NotFoundError(message="Analysis not found", details={"analysis_id": analysis_id})
        return analysis

    def get_model_info(self) -> ModelInfoResponse:
        """Return model metadata, operational status, and documented limitations."""
        loader = get_model_loader()
        meta = loader.metadata
        default_model = "HeuristicFallbackModel" if loader.is_fallback else "RandomForestRegressor"
        return ModelInfoResponse(
            model_name=meta.get("model_name", default_model),
            model_version=loader.model_version,
            is_fallback=loader.is_fallback,
            features=meta.get(
                "features",
                [
                    "tfidf_cosine_sim",
                    "skill_overlap_ratio",
                    "jaccard_similarity",
                    "candidate_skill_count",
                    "job_skill_count",
                    "matched_skill_count",
                    "log_candidate_words",
                    "log_job_words",
                ],
            ),
            metrics=meta.get("metrics", {}),
            limitations=meta.get(
                "limitations",
                [
                    "TF-IDF similarity and keyword matching can miss deep semantic equivalents not in vocabulary",
                    "Trained predominantly on technical, software, and professional resume/job descriptions in English",
                    "Does not evaluate interpersonal soft skills, cultural match, or verified work samples",
                ],
            ),
        )
