"""Inference engine executing compatibility scoring and skill-gap ranking."""

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.ml.loader import ModelLoader, get_model_loader

logger = get_logger("careerai.ml.inference")


@dataclass
class InferenceResult:
    """Structured result of an ML candidate-job fit analysis."""

    compatibility_score: float
    skill_match_score: float
    text_similarity_score: float
    matched_skills: list[str]
    missing_skills: list[dict[str, Any]]
    model_version: str
    feature_breakdown: dict[str, Any]
    latency_ms: float


class InferenceEngine:
    """Executes feature extraction and model inference for job compatibility."""

    def __init__(self, loader: ModelLoader | None = None) -> None:
        self.loader = loader or get_model_loader()

    def predict(
        self,
        resume_text: str,
        job_text: str,
        additional_candidate_skills: list[str] | None = None,
    ) -> InferenceResult:
        """Run inference pipeline on resume and job description text."""
        start_time = time.perf_counter()

        extractor = self.loader.feature_extractor
        if not extractor:
            # Fallback re-init
            from app.ml.features import FeatureExtractor
            from app.ml.skill_extractor import SkillExtractor

            extractor = FeatureExtractor(vectorizer=None, skill_extractor=SkillExtractor())

        # 1. Extract feature vector and metadata
        feature_vector, metadata = extractor.extract_features(
            resume_text=resume_text,
            job_text=job_text,
            additional_skills=additional_candidate_skills,
        )

        # 2. Reshape to (1, n_features) for scikit-learn
        X = np.expand_dims(feature_vector, axis=0)

        # 3. Model prediction
        model = self.loader.model
        raw_pred = float(model.predict(X)[0])
        clamped_score = round(max(0.0, min(100.0, raw_pred)), 1)

        # 4. Component scores
        tfidf_sim = float(metadata.get("tfidf_cosine_sim", 0.0))
        text_sim_score = round(tfidf_sim * 100.0, 1)

        skill_overlap = float(metadata.get("skill_overlap_ratio", 0.0))
        skill_match_score = round(skill_overlap * 100.0, 1)

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        logger.info(
            f"Executed ML analysis: score={clamped_score}, model={self.loader.model_version}, latency={latency_ms}ms"
        )

        return InferenceResult(
            compatibility_score=clamped_score,
            skill_match_score=skill_match_score,
            text_similarity_score=text_sim_score,
            matched_skills=metadata.get("matched_skills", []),
            missing_skills=metadata.get("missing_skills", []),
            model_version=self.loader.model_version,
            feature_breakdown=metadata,
            latency_ms=latency_ms,
        )
