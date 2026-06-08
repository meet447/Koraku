"""Per-run audit logs under ``.koraku/runs/<run_id>/``."""
from __future__ import annotations

import json
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from koraku.workspace.paths import workspace_dir

_artifact_logger: ContextVar[RunArtifactLogger | None] = ContextVar(
    "koraku_run_artifact_logger",
    default=None,
)


def runs_dir(workspace: str | None = None) -> Path:
    root = Path(workspace or workspace_dir()).resolve()
    return root / ".koraku" / "runs"


class RunArtifactLogger:
    """Append-only transcript and structured tool call logs for one agent run."""

    def __init__(self, run_id: str, workspace: str | None = None) -> None:
        self.run_id = (run_id or "").strip()
        self.workspace = workspace
        self._dir = runs_dir(workspace) / self.run_id if self.run_id else None
        self._transcript: Path | None = None
        self._tool_calls: Path | None = None
        if self._dir is not None:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._transcript = self._dir / "transcript.jsonl"
            self._tool_calls = self._dir / "tool_calls.jsonl"
            meta = {
                "run_id": self.run_id,
                "started_at": _now_iso(),
                "workspace": str(Path(workspace or workspace_dir()).resolve()),
            }
            (self._dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @property
    def path(self) -> str | None:
        return str(self._dir) if self._dir is not None else None

    def record_event(self, event: dict[str, Any]) -> None:
        if self._transcript is None:
            return
        row = {"ts": _now_iso(), **event}
        with self._transcript.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        et = str(event.get("type") or "")
        if et == "tool_execution" and self._tool_calls is not None:
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            tool_row = {
                "ts": _now_iso(),
                "phase": "started",
                "tool": data.get("tool"),
                "input": data.get("input"),
                "tool_use_id": data.get("id"),
            }
            with self._tool_calls.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(tool_row, ensure_ascii=False) + "\n")

    def record_tool_result(
        self,
        *,
        tool_name: str,
        tool_use_id: str,
        tool_input: dict[str, Any],
        result: str,
        is_error: bool,
    ) -> None:
        if self._tool_calls is None:
            return
        row = {
            "ts": _now_iso(),
            "phase": "completed",
            "tool": tool_name,
            "input": tool_input,
            "tool_use_id": tool_use_id,
            "is_error": is_error,
            "result_preview": result[:4000],
        }
        with self._tool_calls.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def finalize(self, *, status: str, error: str | None = None) -> None:
        if self._dir is None:
            return
        meta_path = self._dir / "meta.json"
        meta: dict[str, Any] = {}
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                meta = {}
        meta["finished_at"] = _now_iso()
        meta["status"] = status
        if error:
            meta["error"] = error[:2000]
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def bind_run_artifact_logger(logger: RunArtifactLogger | None) -> Token[RunArtifactLogger | None]:
    return _artifact_logger.set(logger)


def reset_run_artifact_logger(token: Token[RunArtifactLogger | None]) -> None:
    _artifact_logger.reset(token)


def get_run_artifact_logger() -> RunArtifactLogger | None:
    return _artifact_logger.get()


def log_tool_result(
    *,
    tool_name: str,
    tool_use_id: str,
    tool_input: dict[str, Any],
    result: str,
    is_error: bool,
) -> None:
    logger = get_run_artifact_logger()
    if logger is not None:
        logger.record_tool_result(
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            tool_input=tool_input,
            result=result,
            is_error=is_error,
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
