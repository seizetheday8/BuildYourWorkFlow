"""Tests for AgentLoop (mocked LLM, no real API calls)."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from code_harness.agent.loop import AgentLoop
from code_harness.context.manager import ContextManager
from code_harness.llm.client import ChatResult
from code_harness.tools.base import Tools


def _make_chat_result(
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> ChatResult:
    return ChatResult(
        content=content,
        input_tokens=10,
        output_tokens=5,
        cache_hit_tokens=0,
        cache_miss_tokens=10,
        latency_ms=50,
        cost_usd=0.0,
        finish_reason="stop" if not tool_calls else "tool_calls",
        tool_calls=tool_calls or [],
    )


def _make_loop(
    tmp_path: Path, mock_llm: MagicMock, max_turns: int = 10
) -> AgentLoop:
    context = ContextManager()
    context.add_system("you are helpful")
    tools = Tools(workspace=tmp_path)
    return AgentLoop(
        llm=mock_llm,
        context=context,
        tools=tools,
        max_turns=max_turns,
        max_context_tokens=10_000,
    )


def _call(tc_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": tc_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def test_single_turn_no_tools(tmp_path: Path) -> None:
    mock_llm = MagicMock()
    mock_llm.chat.return_value = _make_chat_result(content="done")
    loop = _make_loop(tmp_path, mock_llm)

    result = loop.run("hello")

    assert result.finished
    assert result.answer == "done"
    assert result.turns == 1
    assert result.error is None
    assert mock_llm.chat.call_count == 1


def test_tool_then_finish(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("file-content", encoding="utf-8")
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        _make_chat_result(
            content=None,
            tool_calls=[_call("call_1", "read_file", '{"path": "x.txt"}')],
        ),
        _make_chat_result(content="read it"),
    ]
    loop = _make_loop(tmp_path, mock_llm)

    result = loop.run("read x.txt")

    assert result.finished
    assert result.answer == "read it"
    assert result.turns == 2
    assert mock_llm.chat.call_count == 2


def test_max_turns_exhausted(tmp_path: Path) -> None:
    mock_llm = MagicMock()
    mock_llm.chat.return_value = _make_chat_result(
        content=None,
        tool_calls=[_call("call_x", "read_file", '{"path": "nope.txt"}')],
    )
    loop = _make_loop(tmp_path, mock_llm, max_turns=3)

    result = loop.run("loop forever")

    assert not result.finished
    assert result.turns == 3
    assert result.error is not None
    assert "max_turns" in result.error
    assert mock_llm.chat.call_count == 3


def test_unknown_tool(tmp_path: Path) -> None:
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        _make_chat_result(
            content=None,
            tool_calls=[_call("c1", "bogus_tool", "{}")],
        ),
        _make_chat_result(content="after error"),
    ]
    loop = _make_loop(tmp_path, mock_llm)

    result = loop.run("try bogus")

    assert result.finished
    assert result.answer == "after error"
    assert result.turns == 2


def test_write_file_via_tool(tmp_path: Path) -> None:
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        _make_chat_result(
            content=None,
            tool_calls=[
                _call(
                    "w1",
                    "write_file",
                    '{"path": "out.txt", "content": "generated"}',
                )
            ],
        ),
        _make_chat_result(content="wrote"),
    ]
    loop = _make_loop(tmp_path, mock_llm)

    result = loop.run("write out.txt")

    assert result.finished
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "generated"


def test_bad_arguments_json(tmp_path: Path) -> None:
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [
        _make_chat_result(
            content=None,
            tool_calls=[_call("c1", "read_file", "not-json")],
        ),
        _make_chat_result(content="ok"),
    ]
    loop = _make_loop(tmp_path, mock_llm)

    result = loop.run("bad args")

    assert result.finished
    assert result.answer == "ok"
