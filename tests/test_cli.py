"""Tests for the CLI."""

import json
from pathlib import Path

import pytest

from code_harness.cli.main import build_parser, main
from code_harness.telemetry.logger import TokenLogger
from code_harness.telemetry.schema import TokenLog


def _write_entry(logger: TokenLogger, **overrides: object) -> None:
    defaults: dict[str, object] = {
        "session_id": "s1",
        "task_id": "t1",
        "agent_name": "agent",
        "model": "deepseek-chat",
        "input_tokens": 100,
        "output_tokens": 50,
        "latency_ms": 100,
        "cost_usd": 0.001,
        "status": "success",
    }
    defaults.update(overrides)
    logger.log(TokenLog(**defaults))  # type: ignore[arg-type]


def test_main_version(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["version"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "code-harness" in captured.out


def test_stats_requires_session_or_task(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["stats", "--log-dir", str(tmp_path)])
    assert rc == 2
    captured = capsys.readouterr()
    assert "ERROR" in captured.err


def test_stats_with_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logger = TokenLogger(tmp_path)
    _write_entry(logger, session_id="s1", input_tokens=100)
    _write_entry(logger, session_id="s1", input_tokens=200)
    _write_entry(logger, session_id="s2", input_tokens=300)

    rc = main(["stats", "--log-dir", str(tmp_path), "--session", "s1"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["request_count"] == 2
    assert data["total_input_tokens"] == 300


def test_stats_with_task(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logger = TokenLogger(tmp_path)
    _write_entry(logger, task_id="tA", input_tokens=50)
    _write_entry(logger, task_id="tB", input_tokens=70)

    rc = main(["stats", "--log-dir", str(tmp_path), "--task", "tA"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["request_count"] == 1
    assert data["total_input_tokens"] == 50


def test_parser_rejects_no_subcommand() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_run_requires_task() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run"])
