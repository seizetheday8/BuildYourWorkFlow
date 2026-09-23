"""LLM client wrapper around DeepSeek (OpenAI-compatible) API."""

import time
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from code_harness.telemetry.logger import TokenLogger
from code_harness.telemetry.schema import TokenLog


@dataclass
class ChatResult:
    """Result of a single chat call."""

    content: str | None
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int
    latency_ms: int
    cost_usd: float
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMClient:
    """Thin wrapper over DeepSeek chat completions with token logging."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        logger: TokenLogger,
        price_input_per_million: float,
        price_cache_hit_per_million: float,
        price_output_per_million: float,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.logger = logger
        self._price_input = price_input_per_million
        self._price_cache_hit = price_cache_hit_per_million
        self._price_output = price_output_per_million
        self._client: Any = (
            client
            if client is not None
            else OpenAI(api_key=api_key, base_url=base_url)
        )

    def _compute_cost(self, cache_hit: int, cache_miss: int, output: int) -> float:
        return (
            cache_miss * self._price_input / 1_000_000
            + cache_hit * self._price_cache_hit / 1_000_000
            + output * self._price_output / 1_000_000
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        session_id: str,
        task_id: str,
        agent_name: str = "default",
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Send a chat completion request and log token usage.

        Raises the original exception after logging an error entry if the
        underlying API call fails.
        """
        start = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.logger.log(
                TokenLog(
                    session_id=session_id,
                    task_id=task_id,
                    agent_name=agent_name,
                    model=self.model,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    status="error",
                    error_msg=str(exc),
                )
            )
            raise

        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = response.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        cache_hit = int(getattr(usage, "prompt_cache_hit_tokens", 0) or 0)
        cache_miss_default = prompt_tokens - cache_hit
        cache_miss = int(
            getattr(usage, "prompt_cache_miss_tokens", cache_miss_default)
            or 0
        )

        cost = self._compute_cost(cache_hit, cache_miss, completion_tokens)

        choice = response.choices[0]
        message = choice.message
        content = getattr(message, "content", None)
        tool_calls_raw = getattr(message, "tool_calls", None)
        tool_calls: list[dict[str, Any]] = []
        if tool_calls_raw:
            for tc in tool_calls_raw:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        self.logger.log(
            TokenLog(
                session_id=session_id,
                task_id=task_id,
                agent_name=agent_name,
                model=self.model,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cache_hit_tokens=cache_hit,
                cache_miss_tokens=cache_miss,
                latency_ms=latency_ms,
                cost_usd=cost,
                status="success",
            )
        )

        return ChatResult(
            content=content,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            cache_hit_tokens=cache_hit,
            cache_miss_tokens=cache_miss,
            latency_ms=latency_ms,
            cost_usd=cost,
            finish_reason=getattr(choice, "finish_reason", None),
            tool_calls=tool_calls,
        )
