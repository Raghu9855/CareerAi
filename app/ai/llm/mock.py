"""Mock LLM client with realistic prompt-driven generation and test fault injection."""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any

from app.ai.llm.client import LLMClient, LLMMessage, LLMResponse, LLMUsage
from app.core.errors import RateLimitError


class MockLLMClient(LLMClient):
    """Deterministic, mock LLM client supporting fault injection for comprehensive testing."""

    def __init__(
        self,
        model_name: str = "mock-careerai-gpt-4o",
        simulate_timeout: bool = False,
        simulate_rate_limit: bool = False,
        simulate_malformed_json: bool = False,
        simulate_server_error: bool = False,
        simulated_latency: float = 0.01,
    ) -> None:
        self.model_name = model_name
        self.simulate_timeout = simulate_timeout
        self.simulate_rate_limit = simulate_rate_limit
        self.simulate_malformed_json = simulate_malformed_json
        self.simulate_server_error = simulate_server_error
        self.simulated_latency = simulated_latency

        # Metrics for test verification
        self.call_count = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Generate response or inject simulated faults."""
        self.call_count += 1
        start_time = time.perf_counter()

        if self.simulated_latency > 0:
            await asyncio.sleep(self.simulated_latency)

        # 1. Fault injection branches
        if self.simulate_timeout:
            raise TimeoutError("Simulated LLM provider request timeout")

        if self.simulate_rate_limit:
            raise RateLimitError(
                message="Simulated LLM rate limit exceeded (HTTP 429: TPM/RPM threshold breached)",
                details={"retry_after": 2.0},
            )

        if self.simulate_server_error:
            raise RuntimeError("Simulated LLM provider 503 Service Unavailable")

        if self.simulate_malformed_json:
            return LLMResponse(
                content='{"summary": "Incomplete and malformed payload...',
                usage=LLMUsage(prompt_tokens=150, completion_tokens=25, total_tokens=175),
                model=self.model_name,
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        # 2. Inspect prompt content to synthesize realistic structured responses
        user_content = " ".join(m.content for m in messages if m.role == "user")

        if "interview" in user_content.lower() or "prep" in user_content.lower():
            structured_data = {
                "technical_questions": [
                    {
                        "question": (
                            "How do you design scalable async endpoints in FastAPI and manage DB connection pools?"
                        ),
                        "expected_key_concepts": "AsyncSession, SQLAlchemy 2.0, pool_size, max_overflow, event loops",
                        "tip": (
                            "Highlight separation of concerns between repositories, services, and lifespan management."
                        ),
                    },
                    {
                        "question": (
                            "Explain your approach to Docker containerization and Kubernetes pod orchestration."
                        ),
                        "expected_key_concepts": (
                            "Multi-stage builds, non-root users, liveness/readiness probes, secrets"
                        ),
                        "tip": "Emphasize security hardening and horizontal pod autoscaling.",
                    },
                ],
                "behavioral_questions": [
                    {
                        "question": (
                            "Describe a scenario where you diagnosed a production performance bottleneck under SLA "
                            "pressure."
                        ),
                        "star_focus": (
                            "Situation: DB latency spike; Task: root cause; Action: query profiling; Result: 85% "
                            "latency reduction."
                        ),
                    }
                ],
                "preparation_tips": [
                    "Review database indexing strategies and explain execution plans using EXPLAIN.",
                    "Be prepared to discuss multi-tenant authorization security boundaries.",
                ],
            }
        else:
            # Default to Analysis Explanation
            structured_data = {
                "summary": (
                    "The candidate demonstrates strong alignment with backend microservices, typed API development, "
                    "and relational database management. Core competencies directly match required tech stacks."
                ),
                "strengths": [
                    "Demonstrated production experience with Python, FastAPI, and relational databases.",
                    "Solid understanding of Docker containerization and CI/CD pipelines.",
                    "Clean architecture patterns and structured error handling.",
                ],
                "areas_for_growth": [
                    "Deeper hands-on exposure to Kubernetes cluster management and Helm charts.",
                    "Cloud infrastructure automation with Terraform and Linux containers.",
                ],
                "match_verdict": "Strong Match",
            }

        response_text = json.dumps(structured_data, indent=2)
        p_tokens = len(user_content.split()) * 2
        c_tokens = len(response_text.split()) * 2
        self.total_prompt_tokens += p_tokens
        self.total_completion_tokens += c_tokens

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return LLMResponse(
            content=response_text,
            usage=LLMUsage(prompt_tokens=p_tokens, completion_tokens=c_tokens, total_tokens=p_tokens + c_tokens),
            model=self.model_name,
            latency_ms=latency_ms,
            cached=False,
        )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> AsyncGenerator[str, None]:
        """Stream simulated completion chunks."""
        resp = await self.generate(messages, temperature=temperature, max_tokens=max_tokens)
        chunks = resp.content.split("\n")
        for chunk in chunks:
            if self.simulated_latency > 0:
                await asyncio.sleep(self.simulated_latency / len(chunks))
            yield chunk + "\n"
