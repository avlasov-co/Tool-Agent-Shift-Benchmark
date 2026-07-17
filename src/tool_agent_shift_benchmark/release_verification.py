"""Non-destructive release verification in an isolated temporary workspace.

This module is intentionally shipped with the package so ``tasb
verify-release`` has a stable implementation. Verification itself requires a
source checkout, which is copied before any command that might create build or
benchmark outputs is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from tool_agent_shift_benchmark.core.serialization import canonical_dumps

DEFAULT_TIMEOUT_SECONDS = 300
PINNED_BROWSER = "chrome-headless-shell@131.0.6778.204"
COPY_IGNORES = {
    ".git",
    ".venv",
    ".audit",
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".puppeteer-cache",
    "__pycache__",
    "build",
    "dist",
    "figures",
    "htmlcov",
    "node_modules",
    "results",
    "runs",
}
DETERMINISTIC_OUTPUT_DIRECTORIES = (
    "config",
    "identity",
    "plugins",
    "plan",
    "scenarios",
    "results",
    "traces",
    "analysis",
    "plots",
    "reports",
)
DETERMINISTIC_ROOT_FILES = ("checkpoint.json", "status.json")
VOLATILE_OUTPUT_EXCLUSIONS = {
    "run_manifest.json": "contains created/started/ended timestamps and the run-specific path",
    "analysis/plot_source_evidence_snapshot.json": "binds a pre-plot manifest with run-lifecycle timestamps",
    "reports/analysis_source_evidence_snapshot.json": "binds a pre-analysis manifest with run-lifecycle timestamps",
    "reports/source_evidence_snapshot.json": "binds a pre-report manifest with run-lifecycle timestamps",
    "reports/report_provenance.json": "contains source manifest and finalization checksums that bind timestamps",
    "reports/report_validation.json": "validates the run-specific provenance record",
    "reports/experimental_report.md": "renders run-specific provenance checksums",
    "reports/analysis_report.md": "renders run-specific source metadata",
    "reports/analysis_report.html": "renders run-specific provenance checksums",
}


class ReleaseVerificationError(RuntimeError):
    """Raised after a release-verification phase fails."""


@dataclass
class PhaseResult:
    name: str
    status: str
    duration_seconds: float
    timeout_seconds: int
    command: list[str]
    log_path: str
    detail: str | None = None


def _copy_ignore(_: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in COPY_IGNORES or name.endswith((".egg-info", ".pyc", ".pyo")) or name == ".DS_Store"
    }


def _python_executable(value: str) -> str:
    path = Path(value)
    if path.is_file():
        # Preserve a virtualenv executable symlink rather than resolving to the
        # base interpreter and losing its installed release tools.
        return str(path.absolute())
    return shutil.which(value) or value


def _venv_executable(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        suffix = ".exe" if name in {"python", "tasb"} else ""
        return venv_dir / "Scripts" / f"{name}{suffix}"
    return venv_dir / "bin" / name


def extract_pinned_browser(browser_cache: str | Path) -> Path:
    """Safely repair the pinned browser cache and return its executable path.

    The locked browser installer writes the cache directory itself. Some Node
    runtime/archive combinations leave its macOS headless-shell extraction
    partial, so we validate and extract the already-downloaded, version-pinned
    ZIP without accepting links or paths outside the cache.
    """
    browser_root = Path(browser_cache) / "chrome-headless-shell"
    archives = sorted(browser_root.glob("131.0.6778.204-*.zip"))
    install_roots = sorted(path for path in browser_root.iterdir() if path.is_dir()) if browser_root.is_dir() else []
    if len(archives) != 1 or len(install_roots) != 1:
        raise ReleaseVerificationError(
            f"expected one pinned browser archive and install directory below {browser_root}; "
            f"found archives={archives}, directories={install_roots}"
        )
    archive = archives[0]
    destination = install_roots[0].resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            relative = Path(member.filename)
            target = (destination / relative).resolve()
            mode = member.external_attr >> 16
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or destination not in target.parents
                and target != destination
            ):
                raise ReleaseVerificationError(f"unsafe browser archive member: {member.filename}")
            if mode and (mode & 0o170000) == 0o120000:
                raise ReleaseVerificationError(f"browser archive link is not permitted: {member.filename}")
        for member in bundle.infolist():
            target = destination / member.filename
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            mode = member.external_attr >> 16
            if mode:
                target.chmod(mode & 0o777)
    executables = sorted(path for path in destination.rglob("chrome-headless-shell") if path.is_file())
    if len(executables) != 1:
        raise ReleaseVerificationError(f"expected one extracted headless-shell executable below {destination}")
    executable = executables[0]
    if not os.access(executable, os.X_OK):
        raise ReleaseVerificationError(f"pinned browser is not executable: {executable}")
    return executable


def _canonical_file_digest(path: Path) -> str:
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        content = canonical_dumps(payload).encode("utf-8")
    elif path.suffix == ".jsonl":
        payload = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        content = canonical_dumps(payload).encode("utf-8")
    else:
        content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def canonical_output_tree(run_dir: Path) -> dict[str, str]:
    """Digest deterministic bundle artifacts while excluding volatile manifests."""
    digests: dict[str, str] = {}
    for directory_name in DETERMINISTIC_OUTPUT_DIRECTORIES:
        directory = run_dir / directory_name
        if not directory.is_dir():
            raise ReleaseVerificationError(f"missing deterministic output directory: {directory}")
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            relative = path.relative_to(run_dir).as_posix()
            if relative in VOLATILE_OUTPUT_EXCLUSIONS:
                continue
            digests[relative] = _canonical_file_digest(path)
    for name in DETERMINISTIC_ROOT_FILES:
        path = run_dir / name
        if not path.is_file():
            raise ReleaseVerificationError(f"missing deterministic run artifact: {path}")
        digests[name] = _canonical_file_digest(path)
    return digests


def compare_deterministic_outputs(first_run: Path, second_run: Path) -> tuple[bool, str]:
    """Compare canonical output files from two fixed-seed executions."""
    first = canonical_output_tree(first_run)
    second = canonical_output_tree(second_run)
    if first == second:
        return True, f"{len(first)} deterministic files matched exactly"
    all_paths = sorted(set(first) | set(second))
    differences = [
        f"{path}: {first.get(path, '<missing>')} != {second.get(path, '<missing>')}"
        for path in all_paths
        if first.get(path) != second.get(path)
    ]
    return False, "deterministic output mismatch:\n" + "\n".join(differences)


class PhaseRunner:
    def __init__(self, work_dir: Path, *, timeout_seconds: int):
        self.work_dir = work_dir
        self.timeout_seconds = timeout_seconds
        self.logs_dir = work_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[PhaseResult] = []
        self._index = 0

    def _log_path(self, name: str) -> Path:
        self._index += 1
        return self.logs_dir / f"{self._index:02d}-{name}.log"

    def command(
        self,
        name: str,
        command: Sequence[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> PhaseResult:
        timeout = timeout_seconds or self.timeout_seconds
        log_path = self._log_path(name)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["PYTHONNOUSERSITE"] = "1"
        if env:
            environment.update(env)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(command),
                cwd=cwd,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )
            output = completed.stdout
            detail = None if completed.returncode == 0 else f"command exited with status {completed.returncode}"
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            detail = f"timed out after {timeout} seconds"
        except OSError as exc:
            output = f"could not start command: {exc}\n"
            detail = f"could not start command: {exc}"
        log_path.write_text(output, encoding="utf-8")
        result = PhaseResult(
            name=name,
            status="passed" if detail is None else "failed",
            duration_seconds=round(time.monotonic() - started, 3),
            timeout_seconds=timeout,
            command=list(command),
            log_path=str(log_path),
            detail=detail,
        )
        self.results.append(result)
        if detail:
            raise ReleaseVerificationError(f"{name}: {detail}; log: {log_path}")
        return result

    def check(self, name: str, description: str, check: Callable[[], tuple[bool, str]]) -> PhaseResult:
        log_path = self._log_path(name)
        started = time.monotonic()
        try:
            passed, detail = check()
        except Exception as exc:
            passed, detail = False, f"{type(exc).__name__}: {exc}"
        log_path.write_text(detail + "\n", encoding="utf-8")
        result = PhaseResult(
            name=name,
            status="passed" if passed else "failed",
            duration_seconds=round(time.monotonic() - started, 3),
            timeout_seconds=self.timeout_seconds,
            command=[description],
            log_path=str(log_path),
            detail=None if passed else detail,
        )
        self.results.append(result)
        if not passed:
            raise ReleaseVerificationError(f"{name}: {detail}; log: {log_path}")
        return result


def _write_report(work_dir: Path, results: list[PhaseResult], failure: str | None) -> Path:
    report = {
        "schema_version": 1,
        "status": "failed" if failure else "passed",
        "failure": failure,
        "determinism_policy": {
            "compared_directories": list(DETERMINISTIC_OUTPUT_DIRECTORIES),
            "compared_root_files": list(DETERMINISTIC_ROOT_FILES),
            "volatile_exclusions": VOLATILE_OUTPUT_EXCLUSIONS,
        },
        "phases": [asdict(result) for result in results],
    }
    path = work_dir / "release-verification.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _print_table(results: Sequence[PhaseResult], report: Path) -> None:
    print("status   phase                              duration   log")
    for result in results:
        print(f"{result.status.upper():7} {result.name:34} {result.duration_seconds:8.3f}s {result.log_path}")
    print(f"JSON report: {report}")


def run_release_verification(
    *,
    source_root: Path,
    python: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    output_dir: Path | None = None,
) -> tuple[list[PhaseResult], Path]:
    source_root = source_root.resolve()
    if not (source_root / "pyproject.toml").is_file():
        raise ReleaseVerificationError(f"source root must contain pyproject.toml: {source_root}")
    work_dir = Path(
        tempfile.mkdtemp(prefix="tasb-release-verification-", dir=str(output_dir) if output_dir is not None else None)
    )
    runner = PhaseRunner(work_dir, timeout_seconds=timeout_seconds)
    failure: str | None = None
    try:
        temporary_checkout = work_dir / "repository"
        started = time.monotonic()
        shutil.copytree(source_root, temporary_checkout, ignore=_copy_ignore)
        prepare_log = runner._log_path("prepare-temporary-checkout")
        prepare_log.write_text(
            f"Copied {source_root} to {temporary_checkout}. No active-checkout cleanup commands were run.\n",
            encoding="utf-8",
        )
        runner.results.append(
            PhaseResult(
                name="prepare-temporary-checkout",
                status="passed",
                duration_seconds=round(time.monotonic() - started, 3),
                timeout_seconds=timeout_seconds,
                command=["copytree", str(source_root), str(temporary_checkout)],
                log_path=str(prepare_log),
            )
        )
        python = _python_executable(python)
        venv_dir = temporary_checkout / ".venv"
        runner.command("create-venv", [python, "-m", "venv", str(venv_dir)], cwd=temporary_checkout)
        venv_python = _venv_executable(venv_dir, "python")
        tasb = _venv_executable(venv_dir, "tasb")
        runner.command(
            "install-locked-dependencies",
            [str(venv_python), "-m", "pip", "install", "--require-hashes", "-r", "requirements/development.txt"],
            cwd=temporary_checkout,
        )
        runner.command(
            "install-checkout",
            [str(venv_python), "-m", "pip", "install", "--no-deps", "-e", "."],
            cwd=temporary_checkout,
        )
        common_env = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        runner.command(
            "byte-compilation",
            [str(venv_python), "-m", "compileall", "-q", "src", "tests"],
            cwd=temporary_checkout,
        )
        runner.command("lint", [str(venv_python), "-m", "ruff", "check", "src", "tests"], cwd=temporary_checkout)
        runner.command(
            "format-check",
            [str(venv_python), "-m", "ruff", "format", "--check", "src", "tests"],
            cwd=temporary_checkout,
        )
        runner.command("type-check", [str(venv_python), "-m", "mypy"], cwd=temporary_checkout)
        runner.command(
            "unit-tests",
            [str(venv_python), "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=temporary_checkout,
            env=common_env,
        )
        coverage_env = {**common_env, "COVERAGE_FILE": str(work_dir / ".coverage")}
        runner.command(
            "branch-coverage",
            [str(venv_python), "-m", "coverage", "run", "--branch", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=temporary_checkout,
            env=coverage_env,
        )
        runner.command(
            "coverage-report",
            [str(venv_python), "-m", "coverage", "report"],
            cwd=temporary_checkout,
            env=coverage_env,
        )
        runner.command("configuration-validation", [str(tasb), "validate-config", "small"], cwd=temporary_checkout)
        for config_name in (
            "suite_standard_v0_4",
            "suite_research_v0_4",
            "suite_challenge_v0_4",
        ):
            runner.command(
                f"configuration-validation-{config_name}",
                [str(tasb), "validate-config", config_name],
                cwd=temporary_checkout,
            )
        runner.command("suite-contract-list", [str(tasb), "suite", "list"], cwd=temporary_checkout)
        runner.command("standard-suite-plan", [str(tasb), "suite", "plan", "standard"], cwd=temporary_checkout)
        runner.command("challenge-suite-plan", [str(tasb), "suite", "plan", "challenge"], cwd=temporary_checkout)

        def deterministic_plan() -> tuple[bool, str]:
            first = subprocess.run(
                [str(tasb), "plan", "--config", "small", "--scenario-index", "0"],
                cwd=temporary_checkout,
                capture_output=True,
                text=True,
                check=False,
            )
            second = subprocess.run(
                [str(tasb), "plan", "--config", "small", "--scenario-index", "0"],
                cwd=temporary_checkout,
                capture_output=True,
                text=True,
                check=False,
            )
            if first.returncode or second.returncode:
                return False, f"planner failed: first={first.returncode}, second={second.returncode}"
            return (
                first.stdout == second.stdout,
                "planner output matched twice" if first.stdout == second.stdout else "planner output differed",
            )

        runner.check("deterministic-planning", "run tasb plan twice with a fixed input", deterministic_plan)
        for label in ("determinism-a", "determinism-b"):
            run_dir = f"runs/{label}"
            runner.command(
                f"{label}-benchmark",
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
                    label,
                    "--overwrite",
                ],
                cwd=temporary_checkout,
            )
            runner.command(f"{label}-analysis", [str(tasb), "analyze", "--run", run_dir], cwd=temporary_checkout)
            runner.command(f"{label}-plot", [str(tasb), "plot", "--run", run_dir], cwd=temporary_checkout)
            runner.command(
                f"{label}-report",
                [str(tasb), "report", "--run", run_dir, "--html"],
                cwd=temporary_checkout,
            )
        runner.check(
            "deterministic-output-comparison",
            "compare canonical bundle artifacts from two fixed-seed runs",
            lambda: compare_deterministic_outputs(
                temporary_checkout / "runs" / "determinism-a",
                temporary_checkout / "runs" / "determinism-b",
            ),
        )
        runner.command(
            "performance-budget",
            [str(tasb), "performance", "--suite", "smoke", "--output", str(work_dir / "performance.json")],
            cwd=temporary_checkout,
        )
        runner.command(
            "install-locked-node-tooling",
            ["npm", "ci", "--ignore-scripts", "--no-audit", "--fund=false"],
            cwd=temporary_checkout,
        )
        browser_cache = temporary_checkout / ".puppeteer-cache"
        runner.command(
            "install-pinned-browser",
            [
                str(temporary_checkout / "node_modules" / ".bin" / "browsers"),
                "install",
                PINNED_BROWSER,
                "--path",
                str(browser_cache),
            ],
            cwd=temporary_checkout,
            timeout_seconds=600,
        )
        browser_executable: Path | None = None

        def verify_browser_extraction() -> tuple[bool, str]:
            nonlocal browser_executable
            browser_executable = extract_pinned_browser(browser_cache)
            return True, f"verified pinned browser executable: {browser_executable}"

        runner.check(
            "verify-pinned-browser-extraction",
            "safely validate and extract the downloaded pinned browser archive",
            verify_browser_extraction,
        )
        if browser_executable is None:
            raise ReleaseVerificationError("pinned browser extraction did not produce an executable")
        runner.command(
            "architecture-rendering",
            ["bash", "scripts/render_architecture.sh"],
            cwd=temporary_checkout,
            env={
                "TASB_REQUIRE_MERMAID": "1",
                "PUPPETEER_CACHE_DIR": str(browser_cache),
                "PUPPETEER_EXECUTABLE_PATH": str(browser_executable),
            },
        )
        runner.command(
            "distribution-build-and-installed-smoke",
            [str(venv_python), "scripts/distribution_smoke.py", "--source-root", ".", "--python", str(venv_python)],
            cwd=temporary_checkout,
            timeout_seconds=900,
        )
    except ReleaseVerificationError as exc:
        failure = str(exc)
    report = _write_report(work_dir, runner.results, failure)
    _print_table(runner.results, report)
    if failure:
        print(f"release verification failed; temporary workspace retained: {work_dir}", file=sys.stderr)
        raise ReleaseVerificationError(failure)
    print(f"release verification passed; temporary workspace retained: {work_dir}")
    return runner.results, report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run non-destructive release verification in a temporary checkout")
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="interpreter used to create the isolated verifier venv",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="default per-phase timeout in seconds",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="directory under which to retain the verifier workspace and logs",
    )
    args = parser.parse_args(argv)
    try:
        run_release_verification(
            source_root=args.source_root,
            python=args.python,
            timeout_seconds=args.timeout,
            output_dir=args.output_dir,
        )
    except ReleaseVerificationError as exc:
        print(f"release verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
