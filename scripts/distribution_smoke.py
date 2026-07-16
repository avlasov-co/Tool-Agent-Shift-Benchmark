#!/usr/bin/env python3
"""Build, inspect, and exercise sdist and wheel artifacts outside the checkout.

The driver deliberately copies the source into a temporary directory before
building. That keeps build products out of the developer's checkout and makes
archive inspection meaningful even when a workstation has stale ignored files.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PACKAGE_NAME = "tool_agent_shift_benchmark"
REQUIRED_RESOURCES = {
    f"src/{PACKAGE_NAME}/resources/configs/small.yaml",
    f"src/{PACKAGE_NAME}/resources/policies/offline_llm_policy.json",
    f"src/{PACKAGE_NAME}/resources/templates/report.html",
}
FORBIDDEN_COMPONENTS = {
    ".git",
    ".venv",
    ".audit",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "results",
    "figures",
    "runs",
}
COPY_IGNORES = FORBIDDEN_COMPONENTS | {"build", "dist", "htmlcov"}


class DistributionSmokeError(RuntimeError):
    """Raised when a distribution violates the release smoke contract."""


@dataclass(frozen=True)
class CommandRecord:
    name: str
    command: tuple[str, ...]
    duration_seconds: float
    log_path: Path


def archive_names(path: Path) -> list[str]:
    """Return normalized member names from either supported distribution type."""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            return archive.getnames()
    raise DistributionSmokeError(f"unsupported distribution artifact: {path}")


def _strip_sdist_root(names: Iterable[str]) -> list[str]:
    stripped: list[str] = []
    for name in names:
        parts = Path(name).parts
        if len(parts) > 1:
            stripped.append(Path(*parts[1:]).as_posix())
    return stripped


def archive_content_errors(path: Path) -> list[str]:
    """Return any archive-content contract violations without raising."""
    names = archive_names(path)
    errors: list[str] = []
    for name in names:
        parts = Path(name).parts
        if any(part in FORBIDDEN_COMPONENTS for part in parts):
            errors.append(f"forbidden path component in archive: {name}")
        if name.endswith((".pyc", ".pyo")):
            errors.append(f"bytecode in archive: {name}")
        if Path(name).name == ".DS_Store":
            errors.append(f"macOS metadata in archive: {name}")

    relative_names = names if path.suffix == ".whl" else _strip_sdist_root(names)
    for name in relative_names:
        parts = Path(name).parts
        egg_info_parts = [part for part in parts if part.endswith(".egg-info")]
        if not egg_info_parts:
            continue
        expected_source_metadata = (
            path.suffix != ".whl"
            and len(parts) >= 2
            and parts[0] == "src"
            and parts[1] == f"{PACKAGE_NAME}.egg-info"
        )
        if not expected_source_metadata:
            errors.append(f"stale egg-info in archive: {name}")
    expected_resources = (
        {resource.removeprefix("src/") for resource in REQUIRED_RESOURCES}
        if path.suffix == ".whl"
        else REQUIRED_RESOURCES
    )
    missing = sorted(resource for resource in expected_resources if resource not in relative_names)
    errors.extend(f"missing required package resource: {resource}" for resource in missing)

    if path.suffix == ".whl":
        package_roots = {
            Path(name).parts[0]
            for name in relative_names
            if len(Path(name).parts) > 1 and name.endswith((".py", ".pyi"))
        }
        undeclared = sorted(root for root in package_roots if root != PACKAGE_NAME)
    else:
        source_packages = {
            Path(name).parts[1]
            for name in relative_names
            if len(Path(name).parts) > 2
            and Path(name).parts[0] == "src"
            and name.endswith((".py", ".pyi"))
        }
        undeclared = sorted(package for package in source_packages if package != PACKAGE_NAME)
    errors.extend(f"undeclared Python package in archive: {package}" for package in undeclared)
    return sorted(set(errors))


def validate_archive(path: Path) -> None:
    errors = archive_content_errors(path)
    if errors:
        raise DistributionSmokeError(f"archive inspection failed for {path.name}:\n" + "\n".join(errors))


def _source_ignore(_: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in COPY_IGNORES
        or name.endswith((".egg-info", ".pyc", ".pyo"))
        or name == ".DS_Store"
    }


def copy_build_source(source_root: Path, work_dir: Path) -> Path:
    """Copy only source inputs so normal builds cannot mutate the checkout."""
    destination = work_dir / "source"
    shutil.copytree(source_root, destination, ignore=_source_ignore)
    return destination


def executable(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        suffix = ".exe" if name in {"python", "tasb"} else ""
        return venv_dir / "Scripts" / f"{name}{suffix}"
    return venv_dir / "bin" / name


class SmokeRunner:
    def __init__(self, work_dir: Path, *, python: str, timeout_seconds: int):
        self.work_dir = work_dir
        self.python = python
        self.timeout_seconds = timeout_seconds
        self.logs_dir = work_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._command_index = 0

    def run(self, name: str, command: Sequence[str], *, cwd: Path) -> CommandRecord:
        self._command_index += 1
        log_path = self.logs_dir / f"{self._command_index:02d}-{name}.log"
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["PYTHONNOUSERSITE"] = "1"
        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(command),
                cwd=cwd,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            log_path.write_text(f"{output}\nTimed out after {self.timeout_seconds} seconds.\n", encoding="utf-8")
            raise DistributionSmokeError(f"{name} timed out; log: {log_path}") from exc
        duration = round(time.monotonic() - started, 3)
        log_path.write_text(completed.stdout, encoding="utf-8")
        if completed.returncode:
            raise DistributionSmokeError(f"{name} exited {completed.returncode}; log: {log_path}")
        return CommandRecord(name, tuple(command), duration, log_path)


def _exercise_installed_artifact(
    runner: SmokeRunner,
    artifact: Path,
    development_lock: Path,
) -> list[CommandRecord]:
    label = artifact.name.removesuffix(".tar.gz").removesuffix(".whl")
    venv_dir = runner.work_dir / f"venv-{label}"
    empty_cwd = runner.work_dir / f"empty-{label}"
    empty_cwd.mkdir()
    records = [runner.run(f"{label}-venv", [runner.python, "-m", "venv", str(venv_dir)], cwd=empty_cwd)]
    python = executable(venv_dir, "python")
    tasb = executable(venv_dir, "tasb")
    records.append(
        runner.run(
            f"{label}-locked-dependencies",
            [str(python), "-m", "pip", "install", "--require-hashes", "-r", str(development_lock)],
            cwd=empty_cwd,
        )
    )
    records.append(
        runner.run(
            f"{label}-install",
            [str(python), "-m", "pip", "install", "--no-deps", str(artifact)],
            cwd=empty_cwd,
        )
    )
    resource_check = (
        "from importlib.resources import files; "
        "import tool_agent_shift_benchmark as package; "
        "location=Path(package.__file__).resolve(); "
        "assert 'site-packages' in str(location); "
        "assert files('tool_agent_shift_benchmark').joinpath('resources/configs/small.yaml').is_file()"
    )
    records.extend(
        [
            runner.run(
                f"{label}-import-and-resources",
                [str(python), "-c", f"from pathlib import Path; {resource_check}"],
                cwd=empty_cwd,
            ),
            runner.run(f"{label}-tasb-help", [str(tasb), "--help"], cwd=empty_cwd),
            runner.run(
                f"{label}-module-help",
                [str(python), "-m", PACKAGE_NAME, "--help"],
                cwd=empty_cwd,
            ),
            runner.run(f"{label}-config-list", [str(tasb), "config", "list"], cwd=empty_cwd),
            runner.run(
                f"{label}-config-validate",
                [str(tasb), "validate-config", "small"],
                cwd=empty_cwd,
            ),
            runner.run(
                f"{label}-planning",
                [str(tasb), "plan", "--config", "small", "--scenario-index", "0"],
                cwd=empty_cwd,
            ),
            runner.run(
                f"{label}-minimal-run",
                [
                    str(tasb),
                    "run",
                    "--config",
                    "small",
                    "--env",
                    "file_ops",
                    "--agent",
                    "naive",
                    "--scenario-index",
                    "0",
                    "--seed",
                    "42",
                    "--run-name",
                    "distribution-smoke",
                    "--overwrite",
                ],
                cwd=empty_cwd,
            ),
            runner.run(
                f"{label}-analysis",
                [str(tasb), "analyze", "--run", "runs/distribution-smoke"],
                cwd=empty_cwd,
            ),
            runner.run(
                f"{label}-report",
                [str(tasb), "report", "--run", "runs/distribution-smoke", "--html"],
                cwd=empty_cwd,
            ),
            runner.run(
                f"{label}-verify-run",
                [str(tasb), "verify-run", "runs/distribution-smoke", "--strict"],
                cwd=empty_cwd,
            ),
            runner.run(f"{label}-pip-check", [str(python), "-m", "pip", "check"], cwd=empty_cwd),
        ]
    )
    report = empty_cwd / "runs" / "distribution-smoke" / "reports" / "analysis_report.html"
    if not report.is_file() or report.stat().st_size == 0:
        raise DistributionSmokeError(f"{label} report command did not produce {report}")
    return records


def run_distribution_smoke(
    *,
    source_root: Path,
    python: str,
    timeout_seconds: int,
    keep_work_dir: bool = False,
) -> list[CommandRecord]:
    source_root = source_root.resolve()
    python_path = Path(python)
    if python_path.is_file():
        # Preserve a virtualenv's executable path instead of resolving its
        # symlink to the base interpreter, which would discard installed tools.
        python = str(python_path.absolute())
    else:
        python = shutil.which(python) or python
    development_lock = source_root / "requirements" / "development.txt"
    if not development_lock.is_file():
        raise DistributionSmokeError(f"missing development lockfile: {development_lock}")
    work_dir = Path(tempfile.mkdtemp(prefix="tasb-distribution-smoke-"))
    records: list[CommandRecord] = []
    try:
        build_source = copy_build_source(source_root, work_dir)
        dist_dir = work_dir / "dist"
        dist_dir.mkdir()
        runner = SmokeRunner(work_dir, python=python, timeout_seconds=timeout_seconds)
        records.append(
            runner.run(
                "build-distributions",
                [python, "-m", "build", "--sdist", "--wheel", "--outdir", str(dist_dir)],
                cwd=build_source,
            )
        )
        artifacts = sorted(dist_dir.glob("*.tar.gz")) + sorted(dist_dir.glob("*.whl"))
        if len(artifacts) != 2:
            raise DistributionSmokeError(f"expected one sdist and one wheel, found: {[path.name for path in artifacts]}")
        for artifact in artifacts:
            validate_archive(artifact)
            records.extend(_exercise_installed_artifact(runner, artifact, development_lock))
    except Exception:
        print(f"distribution smoke failed; retained diagnostic work directory: {work_dir}", file=sys.stderr)
        raise
    if keep_work_dir:
        print(f"distribution smoke passed; retained work directory: {work_dir}")
    else:
        shutil.rmtree(work_dir)
        print("distribution smoke passed")
    return records


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and independently smoke-test sdist and wheel artifacts")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python", default=sys.executable, help="interpreter used to build and create test environments")
    parser.add_argument("--timeout", type=int, default=300, help="per-command timeout in seconds")
    parser.add_argument("--keep-work-dir", action="store_true", help="retain temporary artifacts and command logs on success")
    args = parser.parse_args(argv)
    try:
        records = run_distribution_smoke(
            source_root=args.source_root,
            python=args.python,
            timeout_seconds=args.timeout,
            keep_work_dir=args.keep_work_dir,
        )
    except DistributionSmokeError as exc:
        print(f"distribution smoke failed: {exc}", file=sys.stderr)
        return 1
    print(f"completed {len(records)} distribution checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
