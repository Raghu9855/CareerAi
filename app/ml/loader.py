"""ModelLoader singleton with startup loading, thread safety, and graceful degradation."""

import json
import os
import threading
from typing import Any

import joblib
import numpy as np

from app.core.logging import get_logger
from app.ml.features import FeatureExtractor
from app.ml.skill_extractor import SkillExtractor

logger = get_logger("careerai.ml.loader")

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
MODEL_PATH = os.path.join(ARTIFACTS_DIR, "model.joblib")
METADATA_PATH = os.path.join(ARTIFACTS_DIR, "metadata.json")


class HeuristicFallbackModel:
    """Deterministic fallback model used when the primary ML artifact is unavailable."""

    VERSION = "heuristic-fallback-v1.0"

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Estimate compatibility score (0-100) using weighted skill overlap and similarity features.
        Features expected:
            0: tfidf_cosine_sim
            1: skill_overlap_ratio
            2: jaccard_similarity
            3: candidate_skill_count
            4: job_skill_count
            5: matched_skill_count
            6: log_candidate_words
            7: log_job_words
        """
        scores = []
        for row in X:
            tfidf_sim = float(row[0])
            skill_overlap = float(row[1])
            jaccard = float(row[2])

            # Composite heuristic score: 60% skill overlap + 30% text similarity + 10% Jaccard
            raw_score = (skill_overlap * 60.0) + (tfidf_sim * 30.0) + (jaccard * 10.0)
            clamped = max(5.0, min(98.0, raw_score))
            scores.append(round(clamped, 2))

        return np.array(scores, dtype=np.float64)


class ModelLoader:
    """Thread-safe singleton managing the ML model lifecycle, caching, and graceful fallback."""

    _instance: "ModelLoader | None" = None
    _lock = threading.RLock()

    def __init__(self) -> None:
        self.model: Any = None
        self.vectorizer: Any = None
        self.metadata: dict[str, Any] = {}
        self.model_version: str = "unknown"
        self.feature_extractor: FeatureExtractor | None = None
        self.is_fallback: bool = False
        self._loaded: bool = False

    @classmethod
    def get_instance(cls) -> "ModelLoader":
        """Access singleton ModelLoader instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance.load()
        return cls._instance

    def load(self, force_reload: bool = False) -> None:
        """Load model artifact and metadata from disk once at startup, falling back gracefully if missing."""
        if self._loaded and not force_reload:
            return

        with self._lock:
            if self._loaded and not force_reload:
                return

            # 1. Attempt loading metadata
            if os.path.exists(METADATA_PATH):
                try:
                    with open(METADATA_PATH, encoding="utf-8") as f:
                        self.metadata = json.load(f)
                    self.model_version = self.metadata.get("model_version", "v1.0.0")
                except Exception as exc:
                    logger.warning(f"Could not load ML metadata from {METADATA_PATH}: {exc}")
                    self.metadata = {}
                    self.model_version = "v1.0.0-unversioned"
            else:
                self.metadata = {}
                self.model_version = "v1.0.0-unversioned"

            # 2. Attempt loading model bundle artifact
            if os.path.exists(MODEL_PATH):
                try:
                    logger.info(f"Loading trained ML model bundle from {MODEL_PATH}...")
                    bundle = joblib.load(MODEL_PATH)
                    self.model = bundle["regressor"]
                    self.vectorizer = bundle["vectorizer"]
                    self.feature_extractor = FeatureExtractor(
                        vectorizer=self.vectorizer,
                        skill_extractor=SkillExtractor(),
                    )
                    self.is_fallback = False
                    self._loaded = True
                    logger.info(f"Successfully loaded ML model version '{self.model_version}'")
                    return
                except Exception as exc:
                    logger.error(f"Failed loading ML artifact from {MODEL_PATH}: {exc}. Engaging heuristic fallback.")

            # 3. Graceful degradation: heuristic fallback
            logger.warning("Operating in fallback mode: using HeuristicFallbackModel")
            self.model = HeuristicFallbackModel()
            self.model_version = HeuristicFallbackModel.VERSION
            self.feature_extractor = FeatureExtractor(
                vectorizer=None,
                skill_extractor=SkillExtractor(),
            )
            self.is_fallback = True
            self._loaded = True


def get_model_loader() -> ModelLoader:
    """Dependency helper returning the loaded ModelLoader singleton."""
    return ModelLoader.get_instance()
