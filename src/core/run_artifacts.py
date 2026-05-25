from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

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
    except Exception:
        return default


def prepare_run_dir(run_name: str | None = None, runs_dir: str | Path = RUNS_DIR, overwrite: bool = False) -> Path:
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


def snapshot_outputs(run_dir: str | Path, command: list[str] | None = None, extra_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    run_path = Path(run_dir)
    copied: list[str] = []
    copied += _copy_tree_contents(RESULTS_DIR, run_path / "results")
    copied += _copy_tree_contents(FIGURES_DIR, run_path / "figures", patterns=["*.png"])
    copied += _copy_tree_contents(DOCS_DIR, run_path / "docs", patterns=["experimental_report.md", "analysis_report.md", "analysis_report.html"])
    manifest = {
        "run_dir": str(run_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": command or [],
        "git_commit": get_git_commit(),
        "artifacts": copied,
        "metadata": extra_metadata or {},
    }
    write_manifest(run_path, manifest)
    return manifest


def write_manifest(run_dir: str | Path, manifest: dict[str, Any]) -> None:
    path = Path(run_dir) / "run_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")


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
