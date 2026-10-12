"""Repositories registry."""

from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.application_repo import ApplicationRepository
from app.repositories.base import BaseRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.repositories.profile_repo import ProfileRepository
from app.repositories.skill_repo import SkillRepository, UserSkillRepository
from app.repositories.token_repo import TokenRepository
from app.repositories.user_repo import UserRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "ProfileRepository",
    "SkillRepository",
    "UserSkillRepository",
    "JobRepository",
    "ApplicationRepository",
    "TokenRepository",
    "DocumentRepository",
    "AnalysisRepository",
]
