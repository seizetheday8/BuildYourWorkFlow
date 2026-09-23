"""Layered context manager.

Structure:
- L1 System: fixed prompts and tool definitions. Never dropped.
- L2 Task: task-scoped context with a TTL in turns.
- L3 History: dialogue history, FIFO-dropped first.

Token estimation uses a coarse 4-chars-per-token heuristic.
Precision is deferred to Phase 1.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


class Message(TypedDict, total=False):
    """A chat message in OpenAI-compatible format."""

    role: str
    content: str
    tool_calls: list[dict[str, Any]]
    tool_call_id: str


Role = Literal["system", "user", "assistant", "tool"]


def _estimate_tokens(text: str) -> int:
    """Coarse token estimate: 4 characters per token."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _message_tokens(msg: Message) -> int:
    return _estimate_tokens(msg.get("content") or "")


@dataclass
class CompactReport:
    """Report of a compact operation."""

    before_tokens: int
    after_tokens: int
    dropped_history: int
    dropped_tasks: int
    kept_history: int
    kept_tasks: int
    strategy: str = "fifo"


@dataclass
class _TaskItem:
    message: Message
    ttl: int


@dataclass
class ContextManager:
    """Layered context manager.

    Messages are stored in three buckets and assembled in priority order:
    system > task > history.
    """

    _system: list[Message] = field(default_factory=list)
    _tasks: list[_TaskItem] = field(default_factory=list)
    _history: list[Message] = field(default_factory=list)

    # ---- add ----

    def add_system(self, content: str) -> None:
        """Add a system message. Never dropped."""
        self._system.append(Message(role="system", content=content))

    def add_task(self, content: str, ttl_turns: int = 10) -> None:
        """Add a task-scoped message with TTL in turns."""
        if ttl_turns < 0:
            raise ValueError("ttl_turns must be >= 0")
        self._tasks.append(_TaskItem(message=Message(role="user", content=content), ttl=ttl_turns))

    def add_history(self, role: Role, content: str) -> None:
        """Add a dialogue history message."""
        if role not in ("system", "user", "assistant", "tool"):
            raise ValueError(f"invalid role: {role}")
        self._history.append(Message(role=role, content=content))

    def add_message(self, msg: Message) -> None:
        """Add a raw message without role validation.

        Used by AgentLoop to append assistant messages with tool_calls
        and tool result messages with tool_call_id.
        """
        self._history.append(msg)

    # ---- decay ----

    def tick(self) -> None:
        """Advance one turn: decrement task TTLs and drop expired tasks."""
        kept: list[_TaskItem] = []
        for item in self._tasks:
            item.ttl -= 1
            if item.ttl > 0:
                kept.append(item)
        self._tasks = kept

    # ---- build ----

    def _all_messages(self) -> list[Message]:
        return (
            list(self._system)
            + [item.message for item in self._tasks]
            + list(self._history)
        )

    def _total_tokens(self, messages: list[Message]) -> int:
        return sum(_message_tokens(m) for m in messages)

    def build(self, max_tokens: int) -> list[Message]:
        """Assemble messages within a token budget.

        Does NOT mutate internal state. Drops oldest history first, then
        lowest-TTL tasks. Never drops system messages.
        """
        if max_tokens <= 0:
            raise ValueError("max_tokens must be > 0")

        system_msgs = list(self._system)
        task_msgs = [item.message for item in self._tasks]
        history_msgs = list(self._history)

        messages = system_msgs + task_msgs + history_msgs
        while self._total_tokens(messages) > max_tokens and history_msgs:
            history_msgs.pop(0)
            messages = system_msgs + task_msgs + history_msgs

        while self._total_tokens(messages) > max_tokens and task_msgs:
            task_msgs.pop(0)
            messages = system_msgs + task_msgs + history_msgs

        return messages

    # ---- compact ----

    def compact(self, keep_recent: int = 5) -> CompactReport:
        """Drop oldest history entries beyond keep_recent. Mutates state."""
        if keep_recent < 0:
            raise ValueError("keep_recent must be >= 0")

        before = self._total_tokens(self._all_messages())
        before_history = len(self._history)

        if keep_recent == 0:
            kept_history: list[Message] = []
        else:
            kept_history = list(self._history[-keep_recent:])

        self._history = kept_history
        after = self._total_tokens(self._all_messages())

        return CompactReport(
            before_tokens=before,
            after_tokens=after,
            dropped_history=before_history - len(kept_history),
            dropped_tasks=0,
            kept_history=len(kept_history),
            kept_tasks=len(self._tasks),
            strategy="fifo",
        )

    # ---- introspection ----

    def stats(self) -> dict[str, int]:
        """Return counts and token estimates per layer."""
        return {
            "system_count": len(self._system),
            "task_count": len(self._tasks),
            "history_count": len(self._history),
            "system_tokens": self._total_tokens(self._system),
            "task_tokens": self._total_tokens([item.message for item in self._tasks]),
            "history_tokens": self._total_tokens(self._history),
        }
