"""Run-scoped artifact store facade."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.core.run_artifacts import snapshot_outputs


class ArtifactStore:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        for name in ("results", "traces/policy", "traces/evaluator", "figures", "reports", "replay"):
            (self.run_dir / name).mkdir(parents=True, exist_ok=True)

    def write_jsonl(self, relative_path: str, rows: Iterable[Mapping[str, Any]]) -> Path:
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(dict(row), sort_keys=True, default=str) + "\n" for row in rows), encoding="utf-8")
        return path

    def finalize(self, command: list[str] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return snapshot_outputs(self.run_dir, command=command, extra_metadata=metadata)
