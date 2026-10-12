"""Feature extraction pipeline for ML compatibility scoring."""

import math
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ml.skill_extractor import SkillExtractor


class FeatureExtractor:
    """Extracts numeric feature vectors from candidate resume and job description texts."""

    FEATURE_NAMES: list[str] = [
        "tfidf_cosine_sim",
        "skill_overlap_ratio",
        "jaccard_similarity",
        "candidate_skill_count",
        "job_skill_count",
        "matched_skill_count",
        "log_candidate_words",
        "log_job_words",
    ]

    def __init__(
        self,
        vectorizer: TfidfVectorizer | None = None,
        skill_extractor: SkillExtractor | None = None,
    ) -> None:
        self.vectorizer = vectorizer or TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=1500,
            sublinear_tf=True,
            stop_words="english",
        )
        self.skill_extractor = skill_extractor or SkillExtractor()

    def extract_features(
        self,
        resume_text: str,
        job_text: str,
        additional_skills: list[str] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Extract numeric feature vector and return metadata breakdown.
        Returns:
            feature_vector: 1D numpy array of shape (8,)
            metadata: dictionary of human-readable feature values and skill matches
        """
        # 1. Clean texts
        r_text = resume_text.strip() if resume_text else ""
        j_text = job_text.strip() if job_text else ""

        # 2. Skill overlap features
        candidate_skills = set(self.skill_extractor.extract_skills(r_text))
        if additional_skills:
            candidate_skills.update(additional_skills)

        job_skills = set(self.skill_extractor.extract_skills(j_text))
        matched_skills = sorted(candidate_skills.intersection(job_skills))
        _, ranked_missing = self.skill_extractor.analyze_skill_gaps(r_text, j_text, additional_skills)

        job_skill_len = len(job_skills)
        candidate_skill_len = len(candidate_skills)
        matched_len = len(matched_skills)

        skill_overlap_ratio = matched_len / max(job_skill_len, 1)
        union_len = len(candidate_skills | job_skills)
        jaccard_sim = matched_len / max(union_len, 1)

        # 3. TF-IDF Cosine Similarity
        tfidf_sim = 0.0
        if r_text and j_text:
            try:
                tfidf_matrix = self.vectorizer.transform([r_text, j_text])
                sim_matrix = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
                tfidf_sim = float(sim_matrix[0][0])
            except Exception:
                # If vectorizer is not fitted yet or empty vocabulary
                tfidf_sim = 0.0

        # 4. Text length metrics
        r_words = len(r_text.split())
        j_words = len(j_text.split())
        log_candidate_words = math.log1p(r_words)
        log_job_words = math.log1p(j_words)

        features = np.array(
            [
                tfidf_sim,
                skill_overlap_ratio,
                jaccard_sim,
                float(candidate_skill_len),
                float(job_skill_len),
                float(matched_len),
                log_candidate_words,
                log_job_words,
            ],
            dtype=np.float64,
        )

        metadata = {
            "tfidf_cosine_sim": round(tfidf_sim, 4),
            "skill_overlap_ratio": round(skill_overlap_ratio, 4),
            "jaccard_similarity": round(jaccard_sim, 4),
            "candidate_skill_count": candidate_skill_len,
            "job_skill_count": job_skill_len,
            "matched_skills": matched_skills,
            "missing_skills": ranked_missing,
        }

        return features, metadata
