"""LLM client abstractions and protocol specifications."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMMessage:
    """Chat completion message."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMUsage:
    """Token consumption statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Unified LLM completion response."""

    content: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    model: str = "mock-llm-v1"
    latency_ms: float = 0.0
    cached: bool = False


class LLMClient(Protocol):
    """Provider-agnostic interface for Large Language Model generation."""

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute text or structured completion against the LLM."""
        ...

    def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens asynchronously."""
        ...
