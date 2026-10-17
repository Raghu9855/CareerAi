"""Central SQLAlchemy models registry."""

from app.models.analysis import Analysis
from app.models.application import Application, ApplicationStatus
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus, DocumentType
from app.models.job import Job, JobStatus, JobType
from app.models.profile import Profile
from app.models.skill import ProficiencyLevel, Skill, UserSkill
from app.models.token import RefreshToken
from app.models.user import User, UserRole
from app.models.webhook import WebhookDelivery, WebhookDeliveryStatus, WebhookEndpoint, WebhookEvent

__all__ = [
    "User",
    "UserRole",
    "Profile",
    "Skill",
    "UserSkill",
    "ProficiencyLevel",
    "Job",
    "JobType",
    "JobStatus",
    "Application",
    "ApplicationStatus",
    "RefreshToken",
    "Document",
    "DocumentStatus",
    "DocumentType",
    "DocumentChunk",
    "Analysis",
    "WebhookEndpoint",
    "WebhookDelivery",
    "WebhookEvent",
    "WebhookDeliveryStatus",
]
