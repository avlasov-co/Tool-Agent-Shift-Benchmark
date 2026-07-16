"""The only runtime writer for self-contained benchmark run bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from tool_agent_shift_benchmark.core.run_artifacts import snapshot_outputs
from tool_agent_shift_benchmark.core.scenarios import ScenarioSpec, manifest_filename
from tool_agent_shift_benchmark.core.serialization import atomic_write_bytes, write_csv, write_json, write_jsonl

ARTIFACT_STORE_SCHEMA_VERSION = "artifact-store-v2"
ARTIFACT_SCHEMA_VERSIONS = {
    "config": "normalized-config-v1",
    "identity": "experiment-identity-v1",
    "plugins": "plugin-descriptors-v2",
    "scenario": "scenario-manifest-v3",
    "status": "run-status-v1",
    "failure": "orchestration-errors-v1",
    "trace": "episode-traces-v1",
    "analysis": "analysis-output-v1",
    "report": "report-output-v1",
}


class ArtifactStore:
    """Validate run-relative paths and own every materialized output.

    The store deliberately has no API for copying workspace ``results``,
    ``figures``, or ``docs`` directories.  Those historical locations are
    evidence inputs only and cannot contaminate a newly created bundle.
    """

    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "config",
            "identity",
            "plugins",
            "plan",
            "scenarios",
            "results",
            "traces/policy",
            "traces/evaluator",
            "analysis",
            "plots",
            "reports",
            "logs",
        ):
            (self.run_dir / name).mkdir(parents=True, exist_ok=True)

    def path(self, relative_path: str | Path) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
            raise ValueError(f"artifact path must be a non-empty run-relative path: {relative_path!r}")
        target = self.run_dir / relative
        if target.resolve().parent != self.run_dir.resolve() and self.run_dir.resolve() not in target.resolve().parents:
            raise ValueError(f"artifact path escapes run bundle: {relative_path!r}")
        return target

    def write_json(self, relative_path: str | Path, data: Any) -> Path:
        target = self.path(relative_path)
        write_json(target, data)
        return target

    def write_jsonl(self, relative_path: str | Path, rows: Iterable[Mapping[str, Any]]) -> Path:
        target = self.path(relative_path)
        write_jsonl(target, (dict(row) for row in rows))
        return target

    def write_csv(
        self,
        relative_path: str | Path,
        rows: Iterable[Mapping[str, Any]],
        fieldnames: list[str] | None = None,
    ) -> Path:
        target = self.path(relative_path)
        write_csv(target, [dict(row) for row in rows], fieldnames)
        return target

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        target = self.path(relative_path)
        atomic_write_bytes(target, content.encode("utf-8"))
        return target

    def write_bytes(self, relative_path: str | Path, content: bytes) -> Path:
        target = self.path(relative_path)
        atomic_write_bytes(target, content)
        return target

    def write_scenario_manifest(self, scenario: ScenarioSpec) -> Path:
        return self.write_json(
            Path("scenarios") / manifest_filename(scenario.scenario_id, scenario.content_hash), scenario.to_dict()
        )

    def write_trace(
        self,
        episode_id: str,
        *,
        policy: Mapping[str, Any],
        evaluator: Mapping[str, Any],
        failure_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.write_json(
            Path("traces/policy") / f"{episode_id}.json",
            {"artifact_schema_version": "episode-trace-v1", **dict(policy)},
        )
        if failure_injector is not None:
            failure_injector("during_trace_write")
        self.write_json(
            Path("traces/evaluator") / f"{episode_id}.json",
            {"artifact_schema_version": "episode-trace-v1", **dict(evaluator)},
        )

    def finalize(
        self,
        command: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return snapshot_outputs(self.run_dir, command=command, extra_metadata=metadata)
