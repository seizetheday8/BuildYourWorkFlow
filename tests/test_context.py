"""Tests for ContextManager."""

import pytest

from code_harness.context.manager import ContextManager


def _fill_history(cm: ContextManager, n: int, content: str = "hello world") -> None:
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        cm.add_history(role, f"{content}-{i}")


def test_add_and_build_order() -> None:
    cm = ContextManager()
    cm.add_system("you are helpful")
    cm.add_task("do the thing")
    cm.add_history("user", "hi")
    cm.add_history("assistant", "hello")

    messages = cm.build(max_tokens=10_000)
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "user", "assistant"]
    assert messages[0]["content"] == "you are helpful"
    assert messages[1]["content"] == "do the thing"
    assert messages[2]["content"] == "hi"
    assert messages[3]["content"] == "hello"


def test_build_respects_max_tokens_by_dropping_history() -> None:
    cm = ContextManager()
    cm.add_system("sys")
    _fill_history(cm, 50, content="x" * 100)

    # With 50 history msgs of ~25 tokens each = ~1250 tokens.
    messages = cm.build(max_tokens=200)
    assert len(messages) < 50 + 1
    assert messages[0]["role"] == "system"


def test_build_preserves_system_even_when_oversized() -> None:
    cm = ContextManager()
    cm.add_system("s" * 400)  # ~100 tokens
    _fill_history(cm, 20)

    messages = cm.build(max_tokens=50)
    assert any(m["role"] == "system" for m in messages)
    assert messages[0]["role"] == "system"


def test_compact_drops_old_history() -> None:
    cm = ContextManager()
    cm.add_system("sys")
    _fill_history(cm, 20)

    report = cm.compact(keep_recent=5)
    assert report.dropped_history == 15
    assert report.kept_history == 5
    assert report.after_tokens < report.before_tokens
    assert report.strategy == "fifo"

    remaining = cm.build(max_tokens=10_000)
    # 1 system + 5 history
    assert len(remaining) == 6


def test_compact_empty_history_is_noop() -> None:
    cm = ContextManager()
    cm.add_system("sys")
    report = cm.compact(keep_recent=5)
    assert report.dropped_history == 0
    assert report.kept_history == 0
    assert report.before_tokens == report.after_tokens


def test_tick_expires_tasks() -> None:
    cm = ContextManager()
    cm.add_task("t1", ttl_turns=1)
    cm.add_task("t2", ttl_turns=2)

    cm.tick()
    messages = cm.build(max_tokens=10_000)
    contents = [m["content"] for m in messages]
    assert "t1" not in contents
    assert "t2" in contents

    cm.tick()
    messages = cm.build(max_tokens=10_000)
    assert len(messages) == 0


def test_invalid_role_rejected() -> None:
    cm = ContextManager()
    with pytest.raises(ValueError):
        cm.add_history("bogus", "x")  # type: ignore[arg-type]


def test_build_invalid_max_tokens() -> None:
    cm = ContextManager()
    with pytest.raises(ValueError):
        cm.build(max_tokens=0)
