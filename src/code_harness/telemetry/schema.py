"""Token log schema definitions."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TokenLog(BaseModel):
    """A single LLM call log entry."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    session_id: str
    task_id: str
    agent_name: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_hit_tokens: int = Field(default=0, ge=0)
    cache_miss_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    status: Literal["success", "error", "timeout"]
    error_msg: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
