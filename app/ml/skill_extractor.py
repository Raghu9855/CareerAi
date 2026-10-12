"""Skill and keyword extraction module with canonical taxonomy and gap ranking."""

import re
from typing import Any

# Canonical taxonomy mapping normalized forms to clean canonical representations
CANONICAL_SKILLS: dict[str, str] = {
    # Backend & Languages
    "python": "Python",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "golang": "Go",
    "go": "Go",
    "java": "Java",
    "c++": "C++",
    "c#": "C#",
    "rust": "Rust",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "ruby": "Ruby",
    "php": "PHP",
    # Databases & Caching
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "dynamodb": "DynamoDB",
    "cassandra": "Cassandra",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud",
    "azure": "Azure",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "ci/cd": "CI/CD",
    "github actions": "GitHub Actions",
    "jenkins": "Jenkins",
    "linux": "Linux",
    "bash": "Bash",
    # Architecture & APIs
    "rest": "REST API",
    "restful": "REST API",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "microservices": "Microservices",
    "event-driven": "Event-Driven Architecture",
    "system design": "System Design",
    "distributed systems": "Distributed Systems",
    "mvc": "MVC",
    "tdd": "TDD",
    "clean code": "Clean Architecture",
    # AI & ML
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "artificial intelligence": "AI",
    "ai": "AI",
    "scikit-learn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "nlp": "NLP",
    "llm": "LLM",
    "rag": "RAG",
    "vector search": "Vector Search",
    "chromadb": "ChromaDB",
    "qdrant": "Qdrant",
    # Frontend
    "react": "React",
    "reactjs": "React",
    "vue": "Vue.js",
    "next.js": "Next.js",
    "tailwind": "Tailwind CSS",
    "html": "HTML",
    "css": "CSS",
    # Engineering Practices & Soft Skills
    "git": "Git",
    "agile": "Agile",
    "scrum": "Scrum",
    "leadership": "Leadership",
    "communication": "Communication",
    "problem solving": "Problem Solving",
    "mentorship": "Mentorship",
    "code review": "Code Review",
}


def _compile_skill_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Precompile regex patterns for skill extraction respecting word boundaries and special symbols."""
    patterns = []
    # Sort skills by descending length so multi-word skills (e.g. 'amazon web services') match before single words
    sorted_skills = sorted(CANONICAL_SKILLS.keys(), key=len, reverse=True)

    for skill in sorted_skills:
        escaped = re.escape(skill)
        # Handle word boundary: if skill starts/ends with alphanumeric, require word boundary
        left_boundary = r"\b" if re.match(r"^\w", skill) else r""
        right_boundary = r"\b" if re.match(r"\w$", skill) else r""
        pattern = re.compile(rf"{left_boundary}{escaped}{right_boundary}", re.IGNORECASE)
        patterns.append((pattern, CANONICAL_SKILLS[skill]))

    return patterns


COMPILED_PATTERNS = _compile_skill_patterns()


class SkillExtractor:
    """Extracts verified skills and keywords from resume and job texts."""

    def __init__(self) -> None:
        self.patterns = COMPILED_PATTERNS

    def extract_skills_with_counts(self, text: str) -> dict[str, int]:
        """Extract canonical skills from text along with frequency counts."""
        if not text:
            return {}

        counts: dict[str, int] = {}
        for pattern, canonical_name in self.patterns:
            matches = pattern.findall(text)
            if matches:
                counts[canonical_name] = counts.get(canonical_name, 0) + len(matches)

        return counts

    def extract_skills(self, text: str) -> list[str]:
        """Extract unique canonical skills found in text, sorted alphabetically."""
        counts = self.extract_skills_with_counts(text)
        return sorted(counts.keys())

    def analyze_skill_gaps(
        self,
        resume_text: str,
        job_text: str,
        additional_candidate_skills: list[str] | None = None,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """
        Identify matched skills and ranked missing skill gaps.
        Returns:
            matched_skills: list of skill names present in both candidate and job.
            missing_skills: ranked list of missing skills with importance and occurrence metrics.
        """
        job_counts = self.extract_skills_with_counts(job_text)
        resume_counts = self.extract_skills_with_counts(resume_text)

        candidate_skills = set(resume_counts.keys())
        if additional_candidate_skills:
            candidate_skills.update(additional_candidate_skills)

        job_skills = set(job_counts.keys())

        matched = sorted(candidate_skills.intersection(job_skills))
        missing = job_skills.difference(candidate_skills)

        # Rank missing skills by importance (frequency in job description)
        ranked_missing: list[dict[str, Any]] = []
        for skill in missing:
            freq = job_counts.get(skill, 1)
            # Assign importance tier
            if freq >= 3:
                importance = "high"
            elif freq >= 2:
                importance = "medium"
            else:
                importance = "low"

            ranked_missing.append(
                {
                    "skill": skill,
                    "importance": importance,
                    "job_frequency": freq,
                }
            )

        # Sort missing skills: high importance first, then by frequency descending, then alphabetically
        importance_weights = {"high": 3, "medium": 2, "low": 1}
        ranked_missing.sort(
            key=lambda x: (
                -importance_weights.get(str(x["importance"]), 0),
                -int(x["job_frequency"]),
                str(x["skill"]),
            )
        )

        return matched, ranked_missing
