"""Locust load testing suite for CareerAI performance, throughput, and latency benchmarking."""

import uuid

from locust import HttpUser, between, task


class CareerAIUser(HttpUser):
    """Simulates realistic concurrent job seekers interacting with the CareerAI API."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        """Authenticate user upon test start."""
        self.email = f"load_user_{uuid.uuid4().hex[:8]}@example.com"
        self.password = "StressTestPass123!"

        reg_resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "full_name": "Load Test Candidate",
            },
        )
        if reg_resp.status_code == 201:
            token = reg_resp.json()["tokens"]["access_token"]
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            self.headers = {}

    @task(4)
    def check_health(self) -> None:
        """High-frequency health and metrics probes."""
        self.client.get("/health")
        self.client.get("/metrics")

    @task(3)
    def run_ml_compatibility_analysis(self) -> None:
        """Run ML compatibility scoring."""
        if not self.headers:
            return

        payload = {
            "resume_text": (
                "Senior Software Engineer with 6 years experience specializing in "
                "Python, FastAPI, MySQL, Redis, Docker, and AWS microservices."
            ),
            "job_description": (
                "Looking for a Senior Backend Engineer proficient in Python, FastAPI, MySQL, and Docker architecture."
            ),
            "job_skills": ["Python", "FastAPI", "MySQL", "Docker"],
        }
        self.client.post(
            "/api/v1/ml/analyze",
            json=payload,
            headers=self.headers,
            name="/api/v1/ml/analyze",
        )

    @task(2)
    def query_rag_document_intelligence(self) -> None:
        """Query document RAG system."""
        if not self.headers:
            return

        self.client.post(
            "/api/v1/rag/query",
            json={
                "question": "What databases and cloud architectures has the candidate worked on?",
                "top_k": 3,
            },
            headers=self.headers,
            name="/api/v1/rag/query",
        )

    @task(1)
    def browse_jobs(self) -> None:
        """Browse paginated job postings."""
        self.client.get("/api/v1/jobs?page=1&per_page=10", headers=self.headers, name="/api/v1/jobs")
