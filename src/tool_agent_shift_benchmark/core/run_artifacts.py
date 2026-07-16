"""Run-bundle lifecycle helpers.

This module never imports, copies, restores, or deletes workspace-global
benchmark outputs.  Every path it returns is relative to one explicit run
bundle.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tool_agent_shift_benchmark.core.contracts import CONTRACT_VERSION
from tool_agent_shift_benchmark.core.serialization import canonical_loads, stable_hash, write_json

RUNS_DIR = Path("runs")


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return slug or "run"


def timestamped_run_name(name: str | None = None, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    return slugify(name) if name else f"run-{stamp}"


def get_git_commit(default: str = "unknown") -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        return result.stdout.strip() or default
    except (OSError, subprocess.CalledProcessError):
        return default


def prepare_run_dir(
    run_name: str | None = None,
    runs_dir: str | Path = RUNS_DIR,
    overwrite: bool = False,
) -> Path:
    """Create a fresh bundle without replacing a previous one.

    ``overwrite`` is retained only for call compatibility and always rejects a
    pre-existing bundle.  Replacing evidence would make stale/partial files
    indistinguishable from fresh results and is therefore unsafe.
    """

    root = Path(runs_dir)
    root.mkdir(parents=True, exist_ok=True)
    base = timestamped_run_name(run_name)
    candidate = root / base
    if run_name is None:
        counter = 2
        while candidate.exists():
            candidate = root / f"{base}-{counter}"
            counter += 1
    if candidate.exists():
        suffix = "; --overwrite cannot replace a run bundle" if overwrite else ""
        raise FileExistsError(f"run directory already exists: {candidate}{suffix}")
    candidate.mkdir(parents=False)
    return candidate


def _bundle_payload(run_path: Path, relative: str) -> dict[str, Any]:
    path = run_path / relative
    if not path.exists():
        return {}
    value = canonical_loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def snapshot_outputs(
    run_dir: str | Path,
    command: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Finalize only files already written into ``run_dir``.

    The historical name is a thin compatibility wrapper.  It intentionally no
    longer snapshots workspace-global output directories.
    """

    run_path = Path(run_dir)
    if not run_path.is_dir():
        raise FileNotFoundError(f"run bundle does not exist: {run_path}")
    config_payload = _bundle_payload(run_path, "config/normalized_config.json")
    result_config = _bundle_payload(run_path, "results/config.json")
    identity_payload = _bundle_payload(run_path, "identity/experiment_identity.json")
    metadata = dict(extra_metadata or {})
    status_payload = _bundle_payload(run_path, "status.json")
    files = sorted(
        path
        for path in run_path.rglob("*")
        if path.is_file() and path.name not in {"run_manifest.json", "finalization.json"}
    )
    checksums = {str(path.relative_to(run_path)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    effective_config = result_config or config_payload
    identity = identity_payload or effective_config.get("identity", {})
    finished_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "artifact_schema_version": "2",
        "bundle_layout_version": "run-bundle-v2",
        "created_at_utc": metadata.get("started_at_utc", finished_at),
        "ended_at_utc": finished_at,
        "command": command or [],
        "git_commit": get_git_commit(),
        "run_id": effective_config.get("run_id", metadata.get("run_id", "unknown")),
        "identity_schema_version": identity.get("schema_version", "unknown"),
        "config_digest": effective_config.get("config_digest")
        or (stable_hash(config_payload, prefix="cfg") if config_payload else "unknown"),
        "episode_record_version": effective_config.get("episode_record_version", "unknown"),
        "action_record_contract": effective_config.get("action_record_contract", "unknown"),
        "counterfactual_evaluation_contract": effective_config.get("counterfactual_evaluation_contract", "unknown"),
        "scenario_manifest_contract": effective_config.get("scenario_manifest_contract", "unknown"),
        "scenario_family_contract": effective_config.get("scenario_family_contract", "unknown"),
        "scenario_split_contract": effective_config.get("scenario_split_contract", "unknown"),
        "scenario_coverage_hash": effective_config.get("scenario_coverage_hash"),
        "normalized_semantic_identity": identity.get("semantic"),
        "operational_settings": identity.get("operational"),
        "plugin_catalog": metadata.get("plugin_catalog", _bundle_payload(run_path, "plugins/descriptors.json")),
        "contract_version": metadata.get("contract_version", CONTRACT_VERSION),
        "status": status_payload,
        "artifacts": sorted(checksums),
        "checksums": checksums,
        "reproducibility": {"deterministic_ordering": True, "global_workspace_inputs": False},
        "metadata": metadata,
    }
    write_manifest(run_path, manifest)
    return manifest


def write_manifest(run_dir: str | Path, manifest: dict[str, Any]) -> None:
    write_json(Path(run_dir) / "run_manifest.json", manifest)


def latest_run(runs_dir: str | Path = RUNS_DIR) -> Path | None:
    root = Path(runs_dir)
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir()]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def resolve_run(run: str | Path | None = None) -> Path | None:
    if run is None:
        return None
    path = Path(run)
    if not path.is_dir():
        raise FileNotFoundError(f"run bundle not found: {path}")
    return path


def run_results_dir(run: str | Path) -> Path:
    path = resolve_run(run)
    if path is None:
        raise ValueError("an explicit run bundle is required")
    return path / "results"


def restore_run_to_workspace(run: str | Path) -> None:
    raise RuntimeError(
        "restoring a run bundle to workspace-global results/ is unsupported; "
        "pass explicit bundle paths to analysis, plotting, or reporting instead"
    )
