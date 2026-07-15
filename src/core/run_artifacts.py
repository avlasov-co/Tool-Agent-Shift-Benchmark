from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.core.types import json_default, stable_hash

RUNS_DIR = Path("runs")
RESULTS_DIR = Path("results")
FIGURES_DIR = Path("figures")
DOCS_DIR = Path("docs")


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
    root = Path(runs_dir)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / timestamped_run_name(run_name)
    if run_dir.exists():
        if not overwrite:
            raise FileExistsError(f"run directory already exists: {run_dir}")
        shutil.rmtree(run_dir)
    (run_dir / "results").mkdir(parents=True, exist_ok=True)
    (run_dir / "figures").mkdir(parents=True, exist_ok=True)
    (run_dir / "docs").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "replay").mkdir(parents=True, exist_ok=True)
    return run_dir


def _copy_tree_contents(src: Path, dst: Path, patterns: Iterable[str] | None = None) -> list[str]:
    copied: list[str] = []
    if not src.exists():
        return copied
    dst.mkdir(parents=True, exist_ok=True)
    files: Iterable[Path]
    if patterns:
        seen: set[Path] = set()
        selected: list[Path] = []
        for pattern in patterns:
            for path in src.glob(pattern):
                if path.is_file() and path not in seen:
                    seen.add(path)
                    selected.append(path)
        files = selected
    else:
        files = [p for p in src.rglob("*") if p.is_file()]
    for path in files:
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(str(target))
    return copied


def snapshot_outputs(
    run_dir: str | Path,
    command: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_path = Path(run_dir)
    copied: list[str] = []
    copied += _copy_tree_contents(RESULTS_DIR, run_path / "results")
    copied += _copy_tree_contents(FIGURES_DIR, run_path / "figures", patterns=["*.png"])
    copied += _copy_tree_contents(
        DOCS_DIR,
        run_path / "docs",
        patterns=[
            "experimental_report.md",
            "analysis_report.md",
            "analysis_report.html",
        ],
    )
    config_source = run_path / "results" / "config.json"
    if config_source.exists():
        shutil.copy2(config_source, run_path / "config.json")
    # The run bundle is self-describing and retains structured traces in
    # addition to the legacy CSV export.
    (run_path / "traces" / "policy").mkdir(parents=True, exist_ok=True)
    (run_path / "traces" / "evaluator").mkdir(parents=True, exist_ok=True)
    legacy_trace = run_path / "results" / "multistep_traces.jsonl"
    if legacy_trace.exists():
        for line in legacy_trace.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            episode_id = item.get("episode_id", "episode")
            (run_path / "traces" / "policy" / f"{episode_id}.json").write_text(
                json.dumps(
                    {
                        "episode_id": episode_id,
                        "step_trace": item.get("step_trace", []),
                    },
                    sort_keys=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
    evaluator_source = run_path / "results" / "evaluator_traces.jsonl"
    if evaluator_source.exists():
        for line in evaluator_source.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            episode_id = item.get("episode_id", "episode")
            (run_path / "traces" / "evaluator" / f"{episode_id}.json").write_text(
                json.dumps(item, sort_keys=True, indent=2), encoding="utf-8"
            )
    files = sorted(p for p in run_path.rglob("*") if p.is_file() and p.name != "run_manifest.json")
    checksums = {str(p.relative_to(run_path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    metadata = extra_metadata or {}
    config_payload = {}
    config_path = run_path / "config.json"
    if config_path.exists():
        try:
            config_payload = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config_payload = {}
    episode_count = config_payload.get("episodes")
    seed_list = []
    episode_stream = run_path / "results" / "episodes.jsonl"
    if episode_stream.exists():
        for line in episode_stream.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    seed_list.append(json.loads(line).get("seed"))
                except json.JSONDecodeError:
                    pass
    finished_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "artifact_schema_version": "1",
        "run_dir": str(run_path),
        "created_at_utc": finished_at,
        "started_at_utc": metadata.get("started_at_utc", finished_at),
        "ended_at_utc": finished_at,
        "command": command or [],
        "git_commit": get_git_commit(),
        "config_digest": stable_hash(config_payload.get("config", config_payload), prefix="cfg")
        if config_payload
        else "unknown",
        "episode_count": episode_count,
        "seed_list": sorted({seed for seed in seed_list if seed is not None}),
        "plugin_catalog": metadata.get("plugin_catalog", []),
        "contract_version": metadata.get("contract_version", "1"),
        "checkpoint": {
            "parent": metadata.get("parent_run"),
            "path": str(run_path / "checkpoint.json") if (run_path / "checkpoint.json").exists() else None,
        },
        "artifacts": sorted(checksums),
        "checksums": checksums,
        "reproducibility": {"deterministic_ordering": True, "legacy_exports": True},
        "metadata": metadata,
    }
    write_manifest(run_path, manifest)
    return manifest


def write_manifest(run_dir: str | Path, manifest: dict[str, Any]) -> None:
    path = Path(run_dir) / "run_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=json_default), encoding="utf-8")


def latest_run(runs_dir: str | Path = RUNS_DIR) -> Path | None:
    root = Path(runs_dir)
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def resolve_run(run: str | Path | None = None) -> Path | None:
    if run:
        path = Path(run)
        if not path.exists():
            raise FileNotFoundError(f"run directory not found: {path}")
        return path
    return latest_run()


def run_results_dir(run: str | Path | None = None) -> Path:
    path = resolve_run(run)
    if path is None:
        return RESULTS_DIR
    candidate = path / "results"
    return candidate if candidate.exists() else path


def restore_run_to_workspace(run: str | Path) -> None:
    run_path = Path(run)
    results_src = run_path / "results"
    figures_src = run_path / "figures"
    docs_src = run_path / "docs"
    if results_src.exists():
        if RESULTS_DIR.exists():
            shutil.rmtree(RESULTS_DIR)
        shutil.copytree(results_src, RESULTS_DIR)
    if figures_src.exists():
        FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        for file in figures_src.glob("*.png"):
            shutil.copy2(file, FIGURES_DIR / file.name)
    if docs_src.exists():
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        for file in docs_src.glob("*.md"):
            shutil.copy2(file, DOCS_DIR / file.name)
        for file in docs_src.glob("*.html"):
            shutil.copy2(file, DOCS_DIR / file.name)
