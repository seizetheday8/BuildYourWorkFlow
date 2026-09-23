"""Command-line interface for code-harness.

Subcommands:
- run:     execute a natural-language coding task
- stats:   show aggregated token usage
- version: print package version
"""

import argparse
import json
import sys
from pathlib import Path

from code_harness import __version__
from code_harness.agent.loop import AgentLoop
from code_harness.config import load_settings
from code_harness.context.manager import ContextManager
from code_harness.llm.client import LLMClient
from code_harness.telemetry.logger import TokenLogger
from code_harness.tools.base import Tools

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful coding assistant working inside a single project "
    "workspace. Use the provided tools to read, search, and write files. "
    "When the task is complete, reply with a short summary and stop "
    "calling tools."
)


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"code-harness {__version__}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    log_dir = Path(args.log_dir)
    logger = TokenLogger(log_dir)
    if args.session:
        summary = logger.session_summary(args.session)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.task:
        summary = logger.task_summary(args.task)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    print("ERROR: specify --session <id> or --task <id>", file=sys.stderr)
    return 2


def cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    log_dir = Path(args.log_dir) if args.log_dir else settings.log_dir
    logger = TokenLogger(log_dir)

    llm = LLMClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        logger=logger,
        price_input_per_million=settings.price_input_per_million,
        price_cache_hit_per_million=settings.price_cache_hit_per_million,
        price_output_per_million=settings.price_output_per_million,
    )

    context = ContextManager()
    context.add_system(DEFAULT_SYSTEM_PROMPT)

    workspace = Path(args.workspace).resolve() if args.workspace else Path.cwd()
    tools = Tools(workspace=workspace)

    loop = AgentLoop(
        llm=llm,
        context=context,
        tools=tools,
        max_turns=args.max_turns,
        session_id=args.session_id,
        task_id=args.task_id,
        agent_name="agent",
    )

    result = loop.run(args.task)
    print(result.answer)
    if not result.finished:
        print(f"[loop ended: {result.error}]", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Personal AI workflow CLI for coding tasks.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="Show package version.")
    p_version.set_defaults(func=cmd_version)

    p_stats = sub.add_parser("stats", help="Show aggregated token usage.")
    p_stats.add_argument("--session", help="Filter by session id.")
    p_stats.add_argument("--task", help="Filter by task id.")
    p_stats.add_argument(
        "--log-dir",
        default="./logs",
        help="Directory containing tokens-*.jsonl files.",
    )
    p_stats.set_defaults(func=cmd_stats)

    p_run = sub.add_parser("run", help="Run a coding task.")
    p_run.add_argument("task", help="Task description in natural language.")
    p_run.add_argument(
        "--workspace",
        help="Workspace directory. Defaults to current working directory.",
    )
    p_run.add_argument("--log-dir", help="Override log directory.")
    p_run.add_argument("--session-id", default="cli", help="Session id.")
    p_run.add_argument("--task-id", default="cli", help="Task id.")
    p_run.add_argument(
        "--max-turns", type=int, default=10, help="Maximum ReAct turns."
    )
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
