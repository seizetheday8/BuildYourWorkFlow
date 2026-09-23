"""Token logger - JSONL append + aggregation."""

import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from code_harness.telemetry.schema import TokenLog


class TokenLogger:
    """Append-only JSONL logger with in-process locking."""

    def __init__(self, log_dir: Path) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _file_for(self, dt: datetime) -> Path:
        return self.log_dir / f"tokens-{dt.strftime('%Y-%m-%d')}.jsonl"

    def log(self, entry: TokenLog) -> None:
        """Append one entry to today's JSONL file. Thread-safe."""
        path = self._file_for(entry.timestamp)
        line = entry.model_dump_json() + "\n"
        with self._lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line)

    def _iter_all(self) -> list[TokenLog]:
        entries: list[TokenLog] = []
        for path in sorted(self.log_dir.glob("tokens-*.jsonl")):
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entries.append(TokenLog.model_validate_json(line))
        return entries

    @staticmethod
    def _aggregate(entries: list[TokenLog]) -> dict[str, Any]:
        if not entries:
            return {
                "request_count": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": 0.0,
                "avg_latency_ms": 0.0,
                "by_agent": {},
            }
        total_latency = sum(e.latency_ms for e in entries)
        by_agent: dict[str, dict[str, int | float]] = defaultdict(
            lambda: {
                "request_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }
        )
        for e in entries:
            bucket = by_agent[e.agent_name]
            bucket["request_count"] += 1
            bucket["input_tokens"] += e.input_tokens
            bucket["output_tokens"] += e.output_tokens
            bucket["cost_usd"] += e.cost_usd
        return {
            "request_count": len(entries),
            "total_input_tokens": sum(e.input_tokens for e in entries),
            "total_output_tokens": sum(e.output_tokens for e in entries),
            "total_cost_usd": round(sum(e.cost_usd for e in entries), 6),
            "avg_latency_ms": round(total_latency / len(entries), 2),
            "by_agent": dict(by_agent),
        }

    def session_summary(self, session_id: str) -> dict[str, Any]:
        entries = [e for e in self._iter_all() if e.session_id == session_id]
        return self._aggregate(entries)

    def task_summary(self, task_id: str) -> dict[str, Any]:
        entries = [e for e in self._iter_all() if e.task_id == task_id]
        return self._aggregate(entries)
