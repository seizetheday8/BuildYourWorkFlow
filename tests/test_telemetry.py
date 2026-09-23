"""Tests for TokenLogger."""

import threading
from pathlib import Path

from code_harness.telemetry.logger import TokenLogger
from code_harness.telemetry.schema import TokenLog


def _make_entry(
    session_id: str = "s1",
    task_id: str = "t1",
    agent_name: str = "supervisor",
    input_tokens: int = 100,
    output_tokens: int = 50,
    latency_ms: int = 1000,
    cost_usd: float = 0.001,
) -> TokenLog:
    return TokenLog(
        session_id=session_id,
        task_id=task_id,
        agent_name=agent_name,
        model="deepseek-chat",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        status="success",
    )


def test_log_and_read_back(tmp_path: Path) -> None:
    logger = TokenLogger(tmp_path)
    entry = _make_entry()
    logger.log(entry)
    files = list(tmp_path.glob("tokens-*.jsonl"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8").strip()
    parsed = TokenLog.model_validate_json(content)
    assert parsed.session_id == entry.session_id
    assert parsed.task_id == entry.task_id
    assert parsed.agent_name == entry.agent_name
    assert parsed.input_tokens == entry.input_tokens
    assert parsed.output_tokens == entry.output_tokens


def test_session_summary(tmp_path: Path) -> None:
    logger = TokenLogger(tmp_path)
    logger.log(_make_entry(session_id="s1", agent_name="supervisor", input_tokens=100, output_tokens=50))
    logger.log(_make_entry(session_id="s1", agent_name="code_worker", input_tokens=200, output_tokens=80))
    logger.log(_make_entry(session_id="s2", agent_name="supervisor", input_tokens=300, output_tokens=20))
    s1 = logger.session_summary("s1")
    assert s1["request_count"] == 2
    assert s1["total_input_tokens"] == 300
    assert s1["total_output_tokens"] == 130
    assert "supervisor" in s1["by_agent"]
    assert "code_worker" in s1["by_agent"]
    assert s1["by_agent"]["supervisor"]["input_tokens"] == 100
    s2 = logger.session_summary("s2")
    assert s2["request_count"] == 1
    assert s2["total_input_tokens"] == 300


def test_task_summary(tmp_path: Path) -> None:
    logger = TokenLogger(tmp_path)
    logger.log(_make_entry(task_id="task-A", input_tokens=100))
    logger.log(_make_entry(task_id="task-A", input_tokens=200))
    logger.log(_make_entry(task_id="task-B", input_tokens=300))
    a = logger.task_summary("task-A")
    assert a["request_count"] == 2
    assert a["total_input_tokens"] == 300
    b = logger.task_summary("task-B")
    assert b["request_count"] == 1
    assert b["total_input_tokens"] == 300


def test_concurrent_write(tmp_path: Path) -> None:
    logger = TokenLogger(tmp_path)
    n_threads = 10
    n_per_thread = 10

    def worker(worker_id: int) -> None:
        for i in range(n_per_thread):
            logger.log(
                _make_entry(
                    session_id=f"worker-{worker_id}",
                    task_id=f"t-{i}",
                    input_tokens=i,
                    output_tokens=1,
                )
            )

    threads = [threading.Thread(target=worker, args=(wid,)) for wid in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_lines = 0
    for path in tmp_path.glob("tokens-*.jsonl"):
        total_lines += sum(
            1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    assert total_lines == n_threads * n_per_thread
    for path in tmp_path.glob("tokens-*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                TokenLog.model_validate_json(line)


def test_empty_summary(tmp_path: Path) -> None:
    logger = TokenLogger(tmp_path)
    result = logger.session_summary("nonexistent")
    assert result["request_count"] == 0
