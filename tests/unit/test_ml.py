"""Unit tests for ML skill extractor, features, model loader, and inference engine."""

from unittest.mock import patch

import numpy as np

from app.ml.features import FeatureExtractor
from app.ml.inference import InferenceEngine
from app.ml.loader import HeuristicFallbackModel, ModelLoader
from app.ml.skill_extractor import SkillExtractor


def test_skill_extractor_canonical_mapping() -> None:
    """Verify that skill extractor canonicalizes common variants and aliases."""
    extractor = SkillExtractor()
    text = (
        "Senior software engineer with expertise in python, FastAPI, postgres, k8s, "
        "AWS, and scikit-learn. Familiar with ci/cd and Docker."
    )
    skills = extractor.extract_skills(text)
    assert "Python" in skills
    assert "FastAPI" in skills
    assert "PostgreSQL" in skills
    assert "Kubernetes" in skills
    assert "AWS" in skills
    assert "Scikit-Learn" in skills
    assert "CI/CD" in skills
    assert "Docker" in skills


def test_skill_extractor_gap_analysis_and_ranking() -> None:
    """Verify matched skills and ranked missing skills by job description frequency."""
    extractor = SkillExtractor()
    resume_text = "Proficient in Python, MySQL, Git, and Docker."
    job_text = (
        "Looking for a Python developer. Must know Python very well. Python is key. "
        "Kubernetes is mandatory, Kubernetes clusters must be maintained. "
        "Also needs Redis, Docker, and Terraform."
    )

    matched, missing = extractor.analyze_skill_gaps(resume_text, job_text)
    assert "Python" in matched
    assert "Docker" in matched

    missing_names = [m["skill"] for m in missing]
    assert "Kubernetes" in missing_names
    assert "Redis" in missing_names
    assert "Terraform" in missing_names

    # Kubernetes occurs twice -> medium or high importance
    k8s_item = next(m for m in missing if m["skill"] == "Kubernetes")
    assert k8s_item["job_frequency"] >= 2


def test_feature_extractor_output_shape_and_metadata() -> None:
    """Verify feature extractor generates expected vector dimensions and metadata."""
    extractor = FeatureExtractor()
    resume_text = "Experienced Python developer with FastAPI and PostgreSQL background."
    job_text = "Senior Python engineer needed with FastAPI, PostgreSQL, and Docker."

    features, metadata = extractor.extract_features(resume_text, job_text)
    assert isinstance(features, np.ndarray)
    assert features.shape == (8,)
    assert "tfidf_cosine_sim" in metadata
    assert "matched_skills" in metadata
    assert "missing_skills" in metadata
    assert "Python" in metadata["matched_skills"]


def test_heuristic_fallback_model() -> None:
    """Verify HeuristicFallbackModel produces deterministic bounded scores."""
    fallback = HeuristicFallbackModel()
    dummy_features = np.array(
        [
            [0.5, 0.6, 0.4, 3.0, 5.0, 3.0, 4.0, 4.0],  # medium fit
            [0.9, 1.0, 0.9, 8.0, 8.0, 8.0, 5.0, 5.0],  # high fit
            [0.0, 0.0, 0.0, 1.0, 5.0, 0.0, 3.0, 3.0],  # zero fit
        ]
    )
    predictions = fallback.predict(dummy_features)
    assert len(predictions) == 3
    for p in predictions:
        assert 0.0 <= p <= 100.0

    # High fit score should exceed zero fit score
    assert predictions[1] > predictions[2]


def test_model_loader_graceful_fallback_when_file_missing() -> None:
    """Verify ModelLoader engages HeuristicFallbackModel gracefully when artifact is missing."""
    with patch("os.path.exists", return_value=False):
        loader = ModelLoader()
        loader.load(force_reload=True)
        assert loader.is_fallback is True
        assert loader.model_version == HeuristicFallbackModel.VERSION
        assert isinstance(loader.model, HeuristicFallbackModel)


def test_inference_engine_execution() -> None:
    """Verify inference engine returns complete InferenceResult with latency and version."""
    engine = InferenceEngine()
    resume = "Senior Python developer with FastAPI, MySQL, Redis, and Docker."
    job = "Python developer needed. Requirements: Python, FastAPI, MySQL, Redis."

    result = engine.predict(resume, job)
    assert 0.0 <= result.compatibility_score <= 100.0
    assert result.latency_ms > 0
    assert len(result.matched_skills) >= 3
    assert result.model_version != ""
    assert isinstance(result.missing_skills, list)
