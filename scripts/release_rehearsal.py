#!/usr/bin/env python3
"""Run a retained clean-sdist v0.4.0 rehearsal without publishing anything."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


class RehearsalError(RuntimeError):
    """Raised when a rehearsal phase fails."""


@dataclass(frozen=True)
class Record:
    name: str
    command: tuple[str, ...]
    duration_seconds: float
    log: str


def _executable(venv: Path, name: str) -> Path:
    if os.name == "nt":
        suffix = ".exe" if name in {"python", "tasb"} else ""
        return venv / "Scripts" / f"{name}{suffix}"
    return venv / "bin" / name


def _run(records: list[Record], name: str, command: Sequence[str], *, cwd: Path, logs: Path) -> None:
    path = logs / f"{len(records) + 1:02d}-{name}.log"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    started = time.monotonic()
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    path.write_text(completed.stdout, encoding="utf-8")
    records.append(Record(name, tuple(command), round(time.monotonic() - started, 3), str(path)))
    if completed.returncode:
        raise RehearsalError(f"{name} exited {completed.returncode}; log: {path}")


def run_rehearsal(source_root: Path, output: Path, python: str) -> Path:
    source_root = source_root.resolve()
    python_path = Path(python)
    python = str(python_path.absolute()) if python_path.is_file() else shutil.which(python) or python
    output = output.resolve()
    if output == source_root or source_root in output.parents:
        raise RehearsalError(f"output directory must be outside the source root to prevent recursive copying: {output}")
    if output.exists() and any(output.iterdir()):
        raise RehearsalError(f"output directory must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    logs = output / "logs"
    logs.mkdir()
    build_source = output / "source"
    ignore = shutil.ignore_patterns(
        ".git",
        ".venv",
        ".audit",
        ".coverage",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
        "figures",
        "node_modules",
        "release-artifacts",
        "results",
        "runs",
        "*.egg-info",
        "*.pyc",
    )
    shutil.copytree(source_root, build_source, ignore=ignore)
    records: list[Record] = []
    failure: str | None = None
    try:
        dist = output / "sdist"
        dist.mkdir()
        _run(
            records,
            "build-sdist",
            [python, "-m", "build", "--sdist", "--outdir", str(dist)],
            cwd=build_source,
            logs=logs,
        )
        sdists = sorted(dist.glob("*.tar.gz"))
        if len(sdists) != 1:
            raise RehearsalError(f"expected one sdist, found {sdists}")
        venv = output / "venv"
        workspace = output / "installed-workspace"
        workspace.mkdir()
        _run(records, "create-clean-venv", [python, "-m", "venv", str(venv)], cwd=workspace, logs=logs)
        installed_python = _executable(venv, "python")
        tasb = _executable(venv, "tasb")
        _run(
            records,
            "install-locked-dependencies",
            [
                str(installed_python),
                "-m",
                "pip",
                "install",
                "--require-hashes",
                "-r",
                str(source_root / "requirements" / "development.txt"),
            ],
            cwd=workspace,
            logs=logs,
        )
        _run(
            records,
            "install-sdist",
            [str(installed_python), "-m", "pip", "install", "--no-deps", str(sdists[0])],
            cwd=workspace,
            logs=logs,
        )
        _run(records, "installed-version", [str(tasb), "--help"], cwd=workspace, logs=logs)
        _run(records, "suite-contracts", [str(tasb), "suite", "list"], cwd=workspace, logs=logs)
        _run(records, "challenge-structural-plan", [str(tasb), "suite", "plan", "challenge"], cwd=workspace, logs=logs)
        for name in ("smoke", "standard-a", "standard-b"):
            suite = "smoke" if name == "smoke" else "standard"
            run_dir = f"runs/{name}"
            _run(
                records,
                f"{name}-run",
                [str(tasb), "suite", "run", suite, "--run-name", name],
                cwd=workspace,
                logs=logs,
            )
            _run(records, f"{name}-analyze", [str(tasb), "analyze", "--run", run_dir], cwd=workspace, logs=logs)
            _run(records, f"{name}-plot", [str(tasb), "plot", "--run", run_dir], cwd=workspace, logs=logs)
            _run(
                records,
                f"{name}-report",
                [str(tasb), "report", "--run", run_dir, "--html"],
                cwd=workspace,
                logs=logs,
            )
            _run(
                records,
                f"{name}-golden-validate",
                [str(tasb), "suite", "validate", suite, "--run", run_dir],
                cwd=workspace,
                logs=logs,
            )
            _run(
                records,
                f"{name}-strict-verify",
                [str(tasb), "verify-run", run_dir, "--strict"],
                cwd=workspace,
                logs=logs,
            )
        comparison = (
            "from pathlib import Path; "
            "from tool_agent_shift_benchmark.release_verification import compare_deterministic_outputs; "
            "ok,detail=compare_deterministic_outputs(Path('runs/standard-a'),Path('runs/standard-b')); "
            "print(detail); raise SystemExit(0 if ok else 1)"
        )
        _run(
            records,
            "standard-canonical-comparison",
            [str(installed_python), "-c", comparison],
            cwd=workspace,
            logs=logs,
        )
        _run(
            records,
            "smoke-performance-budget",
            [str(tasb), "performance", "--suite", "smoke", "--output", "performance-evidence.json"],
            cwd=workspace,
            logs=logs,
        )
        _run(
            records,
            "standard-performance-budget",
            [
                str(tasb),
                "performance",
                "--suite",
                "standard",
                "--output",
                "standard-performance-evidence.json",
            ],
            cwd=workspace,
            logs=logs,
        )
        _run(
            records,
            "release-artifacts-checksums-sbom",
            [
                python,
                str(source_root / "scripts" / "build_release_artifacts.py"),
                "--source-root",
                str(source_root),
                "--output-dir",
                str(output / "release-artifacts"),
                "--python",
                python,
            ],
            cwd=source_root,
            logs=logs,
        )
        (output / "LOCAL_RELEASE_COMMANDS_NOT_EXECUTED.txt").write_text(
            "git tag -s v0.4.0 -m 'Tool-Agent Shift Benchmark v0.4.0'\n"
            "git push origin codex/phase-6-evidence-release\n"
            "git push origin v0.4.0\n"
            "python -m twine upload release-artifacts/*\n"
            "gh release create v0.4.0 release-artifacts/* --notes-file release-notes-v0.4.0.md\n",
            encoding="utf-8",
        )
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    report = output / "release-rehearsal.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": "release-rehearsal-v1",
                "status": "failed" if failure else "passed",
                "failure": failure,
                "source_root": str(source_root),
                "sdist_install_only": True,
                "challenge_outcomes_used_for_development": False,
                "remote_actions_executed": False,
                "records": [asdict(record) for record in records],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if failure:
        raise RehearsalError(f"{failure}; retained output: {output}")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    try:
        report = run_rehearsal(args.source_root, args.output, args.python)
    except RehearsalError as exc:
        print(f"release rehearsal failed: {exc}", file=sys.stderr)
        return 1
    print(f"release rehearsal passed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
