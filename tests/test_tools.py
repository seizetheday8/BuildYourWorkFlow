"""Tests for Tools."""

import subprocess
from pathlib import Path

import pytest

from code_harness.tools import base
from code_harness.tools.base import Tools


def _make(tmp_path: Path) -> Tools:
    return Tools(workspace=tmp_path)


def test_read_file_ok(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hi there", encoding="utf-8")
    tools = _make(tmp_path)
    r = tools.read_file("hello.txt")
    assert r.success
    assert "hi there" in r.output


def test_read_file_missing(tmp_path: Path) -> None:
    tools = _make(tmp_path)
    r = tools.read_file("nope.txt")
    assert not r.success
    assert r.error is not None
    assert "not found" in r.error


def test_path_escape_rejected(tmp_path: Path) -> None:
    tools = _make(tmp_path)
    r = tools.read_file("../etc/passwd")
    assert not r.success
    assert r.error is not None
    assert "escapes workspace" in r.error


def test_write_file_creates_and_backs_up(tmp_path: Path) -> None:
    tools = _make(tmp_path)
    r1 = tools.write_file("a/b/c.txt", "v1")
    assert r1.success
    assert (tmp_path / "a" / "b" / "c.txt").read_text(encoding="utf-8") == "v1"

    r2 = tools.write_file("a/b/c.txt", "v2")
    assert r2.success
    assert (tmp_path / "a" / "b" / "c.txt").read_text(encoding="utf-8") == "v2"

    backups = list((tmp_path / ".harness" / "backup").glob("*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "v1"


def test_search_code_finds_matches(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("def foo():\n    pass\n", encoding="utf-8")
    (tmp_path / "y.py").write_text("def bar():\n    pass\n", encoding="utf-8")
    tools = _make(tmp_path)
    r = tools.search_code(r"def \w+")
    assert r.success
    assert "x.py:1" in r.output
    assert "y.py:1" in r.output


def test_search_code_bad_regex(tmp_path: Path) -> None:
    tools = _make(tmp_path)
    r = tools.search_code("[unclosed")
    assert not r.success
    assert r.error is not None
    assert "bad regex" in r.error


def test_run_shell_whitelist_allows_git_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=["git status"], returncode=0, stdout="clean\n", stderr=""
        )

    monkeypatch.setattr(base.subprocess, "run", fake_run)
    tools = _make(tmp_path)
    r = tools.run_shell("git status")
    assert r.success
    assert "clean" in r.output
    call_args = captured["args"]
    assert isinstance(call_args, tuple)
    assert call_args[0] == "git status"


def test_run_shell_blocks_non_whitelist(tmp_path: Path) -> None:
    tools = _make(tmp_path)
    r = tools.run_shell("rm -rf /")
    assert not r.success
    assert r.error is not None
    assert "whitelist" in r.error


def test_run_shell_empty_command(tmp_path: Path) -> None:
    tools = _make(tmp_path)
    r = tools.run_shell("   ")
    assert not r.success
    assert r.error is not None
    assert "empty" in r.error
