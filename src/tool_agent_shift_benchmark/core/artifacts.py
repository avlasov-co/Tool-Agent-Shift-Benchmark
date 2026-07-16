"""Run-scoped artifact store facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from tool_agent_shift_benchmark.core.run_artifacts import snapshot_outputs
from tool_agent_shift_benchmark.core.serialization import write_jsonl


class ArtifactStore:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        for name in (
            "results",
            "traces/policy",
            "traces/evaluator",
            "figures",
            "reports",
            "replay",
        ):
            (self.run_dir / name).mkdir(parents=True, exist_ok=True)

    def write_jsonl(self, relative_path: str, rows: Iterable[Mapping[str, Any]]) -> Path:
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(path, (dict(row) for row in rows))
        return path

    def finalize(self, command: list[str] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return snapshot_outputs(self.run_dir, command=command, extra_metadata=metadata)
