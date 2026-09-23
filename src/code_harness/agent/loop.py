"""ReAct-style agent loop.

Cycle: LLM decides -> tools execute -> observation appended -> repeat
until the model returns a message with no tool calls, or max_turns reached.
"""

import json
from dataclasses import dataclass
from typing import Any, cast

from code_harness.context.manager import ContextManager, Message
from code_harness.llm.client import LLMClient
from code_harness.tools.base import Tools

DEFAULT_MAX_TURNS = 10
DEFAULT_MAX_CONTEXT_TOKENS = 32_000

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a UTF-8 text file within the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the workspace root.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Overwrites existing files; a backup is made.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to the workspace root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for a regex pattern in workspace files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Python regex pattern.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Subdirectory to search. Defaults to workspace root.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a whitelisted shell command inside the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "Command to execute. Must match a whitelist prefix.",
                    }
                },
                "required": ["cmd"],
            },
        },
    },
]


@dataclass
class LoopResult:
    """Result of a full agent loop run."""

    finished: bool
    answer: str
    turns: int
    error: str | None = None


class AgentLoop:
    """ReAct-style agent loop."""

    def __init__(
        self,
        llm: LLMClient,
        context: ContextManager,
        tools: Tools,
        max_turns: int = DEFAULT_MAX_TURNS,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        session_id: str = "default",
        task_id: str = "default",
        agent_name: str = "agent",
    ) -> None:
        self.llm = llm
        self.context = context
        self.tools = tools
        self.max_turns = max_turns
        self.max_context_tokens = max_context_tokens
        self.session_id = session_id
        self.task_id = task_id
        self.agent_name = agent_name

    def run(self, user_input: str) -> LoopResult:
        """Run the loop until the model stops calling tools or max_turns hit."""
        self.context.add_history("user", user_input)

        for turn in range(1, self.max_turns + 1):
            messages = cast(
                list[dict[str, Any]],
                self.context.build(max_tokens=self.max_context_tokens),
            )
            result = self.llm.chat(
                messages=messages,
                session_id=self.session_id,
                task_id=self.task_id,
                agent_name=self.agent_name,
                tools=TOOL_SPECS,
            )

            assistant_msg = Message(role="assistant", content=result.content or "")
            if result.tool_calls:
                assistant_msg["tool_calls"] = result.tool_calls
            self.context.add_message(assistant_msg)

            if not result.tool_calls:
                return LoopResult(
                    finished=True,
                    answer=result.content or "",
                    turns=turn,
                )

            for tc in result.tool_calls:
                output = self._dispatch(tc)
                self.context.add_message(
                    Message(
                        role="tool",
                        content=output,
                        tool_call_id=str(tc.get("id", "")),
                    )
                )

        return LoopResult(
            finished=False,
            answer="",
            turns=self.max_turns,
            error=f"reached max_turns={self.max_turns}",
        )

    def _dispatch(self, tool_call: dict[str, Any]) -> str:
        fn = tool_call.get("function") or {}
        name = str(fn.get("name", ""))
        raw_args = fn.get("arguments", "{}")
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError as exc:
            return f"ERROR: bad arguments JSON: {exc}"
        if not isinstance(args, dict):
            return "ERROR: arguments must be a JSON object"
        try:
            if name == "read_file":
                r = self.tools.read_file(str(args["path"]))
            elif name == "write_file":
                r = self.tools.write_file(str(args["path"]), str(args["content"]))
            elif name == "search_code":
                r = self.tools.search_code(
                    str(args["pattern"]), str(args.get("path", "."))
                )
            elif name == "run_shell":
                r = self.tools.run_shell(str(args["cmd"]))
            else:
                return f"ERROR: unknown tool '{name}'"
        except KeyError as exc:
            return f"ERROR: missing argument {exc}"
        if r.success:
            return r.output
        return f"ERROR: {r.error or 'unknown'}"
