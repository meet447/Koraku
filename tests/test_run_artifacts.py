"""Run artifact logging."""
from __future__ import annotations

import json
from pathlib import Path

from koraku.agent.run_artifacts import RunArtifactLogger, runs_dir


def test_run_artifact_logger_writes_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    logger = RunArtifactLogger("run-abc", str(tmp_path))
    assert logger.path is not None
    logger.record_event({"type": "agent.mode", "data": {"mode": "standard"}})
    logger.record_tool_result(
        tool_name="Read",
        tool_use_id="tu-1",
        tool_input={"path": "foo.txt"},
        result="hello",
        is_error=False,
    )
    logger.finalize(status="completed")
    run_dir = runs_dir(str(tmp_path)) / "run-abc"
    assert (run_dir / "transcript.jsonl").is_file()
    assert (run_dir / "tool_calls.jsonl").is_file()
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "completed"
