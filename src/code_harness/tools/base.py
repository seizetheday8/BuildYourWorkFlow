"""Workspace-scoped filesystem and shell tools.

Safety model:
- All paths are resolved relative to workspace; escape attempts are rejected.
- write_file backs up existing targets before overwriting.
- run_shell only executes commands matching SHELL_WHITELIST prefixes.
- Output is truncated at MAX_OUTPUT_CHARS.
- Shell commands have SHELL_TIMEOUT_SECONDS limit.
"""

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

SHELL_WHITELIST: tuple[str, ...] = (
    "go build",
    "go test",
    "go vet",
    "go fmt",
    "ls",
    "cat",
    "head",
    "tail",
    "git status",
    "git diff",
    "git log",
)

MAX_OUTPUT_CHARS = 10_000
SHELL_TIMEOUT_SECONDS = 30
MAX_SEARCH_MATCHES = 200


@dataclass
class ToolResult:
    """Result of a tool invocation."""

    success: bool
    output: str
    error: str | None = None


class Tools:
    """Workspace-scoped filesystem and shell tools."""

    def __init__(self, workspace: Path, backup_dir: Path | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        if not self.workspace.exists():
            raise ValueError(f"workspace does not exist: {self.workspace}")
        self.backup_dir = (
            Path(backup_dir).resolve()
            if backup_dir is not None
            else self.workspace / ".harness" / "backup"
        )

    def _safe_path(self, path: str) -> Path:
        """Resolve path relative to workspace; reject escape attempts."""
        target = (self.workspace / path).resolve()
        try:
            target.relative_to(self.workspace)
        except ValueError:
            raise ValueError(f"path escapes workspace: {path}") from None
        return target

    def read_file(self, path: str) -> ToolResult:
        try:
            target = self._safe_path(path)
        except ValueError as exc:
            return ToolResult(success=False, output="", error=str(exc))
        if not target.exists():
            return ToolResult(success=False, output="", error=f"not found: {path}")
        if not target.is_file():
            return ToolResult(success=False, output="", error=f"not a file: {path}")
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            return ToolResult(success=False, output="", error=f"not utf-8: {exc}")
        if len(content) > MAX_OUTPUT_CHARS:
            content = content[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
        return ToolResult(success=True, output=content)

    def write_file(self, path: str, content: str) -> ToolResult:
        try:
            target = self._safe_path(path)
        except ValueError as exc:
            return ToolResult(success=False, output="", error=str(exc))
        if target.exists() and target.is_file():
            self._backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True,
            output=f"wrote {len(content)} chars to {path}",
        )

    def _backup(self, target: Path) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        relative = target.relative_to(self.workspace)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        flat = relative.as_posix().replace("/", "__")
        backup_name = f"{flat}.{stamp}.bak"
        shutil.copy2(target, self.backup_dir / backup_name)

    def search_code(self, pattern: str, path: str = ".") -> ToolResult:
        try:
            root = self._safe_path(path)
        except ValueError as exc:
            return ToolResult(success=False, output="", error=str(exc))
        if not root.exists():
            return ToolResult(success=False, output="", error=f"not found: {path}")
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return ToolResult(success=False, output="", error=f"bad regex: {exc}")

        matches: list[str] = []
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        truncated = False
        for f in files:
            if not f.is_file():
                continue
            if any(p in f.parts for p in (".git", ".venv", ".harness", "__pycache__")):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    rel = f.relative_to(self.workspace).as_posix()
                    matches.append(f"{rel}:{lineno}: {line.strip()}")
                    if len(matches) >= MAX_SEARCH_MATCHES:
                        truncated = True
                        break
            if truncated:
                break
        if truncated:
            matches.append("...[truncated]")
        return ToolResult(success=True, output="\n".join(matches))

    def run_shell(self, cmd: str) -> ToolResult:
        stripped = cmd.strip()
        if not stripped:
            return ToolResult(success=False, output="", error="empty command")
        if not self._is_whitelisted(stripped):
            return ToolResult(
                success=False,
                output="",
                error=f"command not in whitelist: {stripped}",
            )
        try:
            proc = subprocess.run(
                stripped,
                shell=True,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=SHELL_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="timeout")
        out = (proc.stdout or "") + (proc.stderr or "")
        if len(out) > MAX_OUTPUT_CHARS:
            out = out[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
        if proc.returncode == 0:
            return ToolResult(success=True, output=out)
        return ToolResult(success=False, output=out, error=f"exit code {proc.returncode}")

    @staticmethod
    def _is_whitelisted(cmd: str) -> bool:
        return any(cmd == w or cmd.startswith(w + " ") for w in SHELL_WHITELIST)
