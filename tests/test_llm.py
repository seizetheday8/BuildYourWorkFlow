"""Tests for LLMClient (mocked, no real API calls)."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from code_harness.llm.client import LLMClient
from code_harness.telemetry.logger import TokenLogger
from code_harness.telemetry.schema import TokenLog


def _make_fake_response(
    content: str | None = "hello",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cache_hit: int = 0,
    finish_reason: str = "stop",
    tool_calls: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prompt_cache_hit_tokens=cache_hit,
        prompt_cache_miss_tokens=prompt_tokens - cache_hit,
    )
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=usage)


def _make_client(
    tmp_path: Path, mock_client: MagicMock
) -> tuple[LLMClient, TokenLogger]:
    logger = TokenLogger(tmp_path)
    client = LLMClient(
        api_key="fake-key",
        base_url="http://fake",
        model="deepseek-chat",
        logger=logger,
        price_input_per_million=0.43,
        price_cache_hit_per_million=0.0036,
        price_output_per_million=0.86,
        client=mock_client,
    )
    return client, logger


def _read_log(tmp_path: Path) -> TokenLog:
    files = list(tmp_path.glob("tokens-*.jsonl"))
    assert len(files) == 1
    return TokenLog.model_validate_json(files[0].read_text(encoding="utf-8").strip())


def test_chat_returns_content(tmp_path: Path) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_fake_response(
        content="world"
    )
    client, _ = _make_client(tmp_path, mock_client)

    result = client.chat(
        messages=[{"role": "user", "content": "hi"}],
        session_id="s1",
        task_id="t1",
        agent_name="code_worker",
    )
    assert result.content == "world"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.finish_reason == "stop"


def test_chat_logs_token_usage(tmp_path: Path) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_fake_response(
        prompt_tokens=200, completion_tokens=80
    )
    client, _ = _make_client(tmp_path, mock_client)

    client.chat(
        messages=[{"role": "user", "content": "hi"}],
        session_id="sess-A",
        task_id="task-A",
        agent_name="supervisor",
    )

    entry = _read_log(tmp_path)
    assert entry.session_id == "sess-A"
    assert entry.task_id == "task-A"
    assert entry.agent_name == "supervisor"
    assert entry.input_tokens == 200
    assert entry.output_tokens == 80
    assert entry.status == "success"


def test_chat_computes_cost_with_cache(tmp_path: Path) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_fake_response(
        prompt_tokens=1000, completion_tokens=200, cache_hit=600
    )
    client, _ = _make_client(tmp_path, mock_client)

    result = client.chat(
        messages=[{"role": "user", "content": "hi"}],
        session_id="s1",
        task_id="t1",
    )

    assert result.cache_hit_tokens == 600
    assert result.cache_miss_tokens == 400
    expected = (
        400 * 0.43 / 1_000_000
        + 600 * 0.0036 / 1_000_000
        + 200 * 0.86 / 1_000_000
    )
    assert result.cost_usd == pytest.approx(expected, rel=1e-9)


def test_chat_logs_error_on_exception(tmp_path: Path) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("api down")
    client, _ = _make_client(tmp_path, mock_client)

    with pytest.raises(RuntimeError, match="api down"):
        client.chat(
            messages=[{"role": "user", "content": "hi"}],
            session_id="s1",
            task_id="t1",
            agent_name="code_worker",
        )

    entry = _read_log(tmp_path)
    assert entry.status == "error"
    assert entry.error_msg is not None
    assert "api down" in entry.error_msg
    assert entry.input_tokens == 0
    assert entry.output_tokens == 0


def test_chat_passes_tools(tmp_path: Path) -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_fake_response()
    client, _ = _make_client(tmp_path, mock_client)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "read a file",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    client.chat(
        messages=[{"role": "user", "content": "hi"}],
        session_id="s1",
        task_id="t1",
        tools=tools,
        temperature=0.2,
    )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["tools"] == tools
    assert call_kwargs["temperature"] == 0.2
    assert call_kwargs["model"] == "deepseek-chat"
