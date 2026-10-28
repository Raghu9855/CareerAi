"""Test data factories for CareerAI testing suite."""

import uuid
from dataclasses import dataclass, field


@dataclass
class UserFactory:
    """Generates user registration test payloads."""

    email: str = field(default_factory=lambda: f"user_{uuid.uuid4().hex[:8]}@example.com")
    password: str = "StrongPass123!"
    full_name: str = "Test Candidate"
    role: str = "user"

    def as_dict(self) -> dict[str, str]:
        return {
            "email": self.email,
            "password": self.password,
            "full_name": self.full_name,
            "role": self.role,
        }


@dataclass
class JobFactory:
    """Generates job posting test payloads."""

    title: str = "Senior Cloud Engineer"
    company: str = "CloudScale Tech"
    description: str = (
        "Seeking a Senior Cloud Engineer experienced in Kubernetes, Docker, Terraform, "
        "and MySQL. Redis caching knowledge and microservices design are required."
    )
    location: str = "Remote"
    required_skills: list[str] = field(default_factory=lambda: ["Kubernetes", "Docker", "Terraform", "MySQL", "Redis"])

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "description": self.description,
            "location": self.location,
            "required_skills": self.required_skills,
        }


@dataclass
class ProfileFactory:
    """Generates user profile test payloads."""

    headline: str = "Experienced Backend & Cloud Specialist"
    summary: str = "Over 6 years of experience building distributed systems in Python and FastAPI."
    location: str = "New York, NY"
    years_of_experience: int = 6

    def as_dict(self) -> dict:
        return {
            "headline": self.headline,
            "summary": self.summary,
            "location": self.location,
            "years_of_experience": self.years_of_experience,
        }
