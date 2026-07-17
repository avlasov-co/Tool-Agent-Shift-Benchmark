"""Non-destructive repository audit runner.

The audit deliberately writes only beneath its selected output directory. It
does not invoke cleanup, experiment generation, or release scripts because
those can mutate checked-in benchmark evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

import yaml

from tool_agent_shift_benchmark import __version__
from tool_agent_shift_benchmark.core.serialization import write_json
from tool_agent_shift_benchmark.core.verification import COMPLETE_VALID, verify_run

DEFAULT_TIMEOUT_SECONDS = 180


@dataclass
class AuditResult:
    name: str
    status: str
    duration_seconds: float
    command: list[str]
    timeout_seconds: int
    log_path: str
    failure_explanation: str | None = None


def exit_code(results: Sequence[AuditResult], strict: bool) -> int:
    """Return a non-zero result only for strict audits with failed checks."""
    return 1 if strict and any(result.status == "failed" for result in results) else 0


class AuditRunner:
    def __init__(
        self,
        output_dir: str | Path = ".audit",
        *,
        strict: bool = False,
        python: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.output_dir = Path(output_dir).resolve()
        self.logs_dir = self.output_dir / "logs"
        self.strict = strict
        self.python = python or sys.executable
        self.timeout_seconds = timeout_seconds
        self.results: list[AuditResult] = []
        self._index = 0

    def _log_path(self, name: str) -> Path:
        self._index += 1
        return self.logs_dir / f"{self._index:02d}-{name}.log"

    def run_command(
        self,
        name: str,
        command: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        env: dict[str, str] | None = None,
        cwd: str | Path | None = None,
    ) -> AuditResult:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._log_path(name)
        timeout = timeout_seconds or self.timeout_seconds
        started = time.monotonic()
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        try:
            completed = subprocess.run(
                list(command),
                cwd=cwd or Path.cwd(),
                env=merged_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )
            log_path.write_text(completed.stdout, encoding="utf-8")
            failure = None if completed.returncode == 0 else f"command exited with status {completed.returncode}"
            status = "passed" if failure is None else "failed"
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            log_path.write_text(f"{output}\nTimed out after {timeout} seconds.\n", encoding="utf-8")
            status, failure = "failed", f"timed out after {timeout} seconds"
        except OSError as exc:
            log_path.write_text(f"Could not start command: {exc}\n", encoding="utf-8")
            status, failure = "failed", f"could not start command: {exc}"
        result = AuditResult(
            name,
            status,
            round(time.monotonic() - started, 3),
            list(command),
            timeout,
            str(log_path),
            failure,
        )
        self.results.append(result)
        return result

    def run_callable(self, name: str, description: str, check: Callable[[], tuple[bool, str]]) -> AuditResult:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._log_path(name)
        started = time.monotonic()
        try:
            passed, detail = check()
            status, failure = ("passed", None) if passed else ("failed", detail)
        except Exception as exc:  # Audit reporting must retain unexpected check failures.
            status, detail, failure = (
                "failed",
                f"{type(exc).__name__}: {exc}",
                f"audit check raised {type(exc).__name__}: {exc}",
            )
        log_path.write_text(detail + "\n", encoding="utf-8")
        result = AuditResult(
            name,
            status,
            round(time.monotonic() - started, 3),
            [description],
            self.timeout_seconds,
            str(log_path),
            failure,
        )
        self.results.append(result)
        return result

    def skip(self, name: str, reason: str) -> AuditResult:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._log_path(name)
        log_path.write_text(reason + "\n", encoding="utf-8")
        result = AuditResult(name, "skipped", 0.0, [], self.timeout_seconds, str(log_path), reason)
        self.results.append(result)
        return result

    def write_report(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "schema_version": 1,
            "strict": self.strict,
            "python": self.python,
            "overall_status": "failed" if any(result.status == "failed" for result in self.results) else "passed",
            "exit_code": exit_code(self.results, self.strict),
            "checks": [asdict(result) for result in self.results],
        }
        path = self.output_dir / "report.json"
        write_json(path, report)
        return path


def _git_clean() -> tuple[bool, str]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if status.returncode:
        return False, f"git status failed:\n{status.stdout}"
    return (
        not status.stdout.strip(),
        "worktree is clean" if not status.stdout.strip() else f"worktree is not clean:\n{status.stdout}",
    )


def _junk_files() -> tuple[bool, str]:
    forbidden = {".DS_Store", ".pytest_cache", "__pycache__"}
    commands = [
        ["git", "ls-files"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    paths: list[str] = []
    for command in commands:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode:
            return (
                False,
                f"could not inspect files with {' '.join(command)}:\n{result.stdout}",
            )
        for raw_path in result.stdout.splitlines():
            path = Path(raw_path)
            if path.name in forbidden or path.suffix in {".pyc", ".pyo"} or path.name.endswith(".egg-info"):
                paths.append(raw_path)
    return (
        not paths,
        "no junk files found" if not paths else "junk files found:\n" + "\n".join(sorted(paths)),
    )


_CLAIM_LEDGER = Path("docs/metrics/claims-to-evidence-ledger.md")
_EVIDENCE_REFERENCES = Path("docs/metrics/verified-evidence.json")
_VERIFIED_CLAIM = re.compile(r"^\|\s*(C\d+)\s*\|.*\|\s*verified\s*\|\s*$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified_claim_ids(ledger: Path) -> set[str]:
    return {
        match.group(1)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if (match := _VERIFIED_CLAIM.match(line)) is not None
    }


def _historical_root_warning() -> str | None:
    """Describe incomplete root evidence without treating it as current evidence."""
    root_candidates = [Path("results"), Path("figures"), Path("docs/analysis_report.md")]
    if not any(path.exists() for path in root_candidates):
        return None
    missing = [
        str(path)
        for path in (
            Path("results/episode_log.csv"),
            Path("results/summary.csv"),
            Path("results/config.json"),
            Path("results/episodes.jsonl"),
            Path("figures/unsafe_action_rate.png"),
        )
        if not path.is_file() or path.stat().st_size == 0
    ]
    if not missing:
        return "historical root evidence is present but is not used for v0.4.0 claims"
    return "historical root evidence is partial and not used for v0.4.0 claims: " + ", ".join(missing)


def _artifact_consistency() -> tuple[bool, str]:
    """Check claim-bound evidence without promoting historical root artifacts.

    Run bundles are intentionally ignored local/release evidence, so a source
    checkout may not contain each referenced bundle. A missing local bundle is
    reported for operator follow-up, while malformed references or an available
    bundle that is not complete-valid fail the audit.
    """
    problems: list[str] = []
    warnings: list[str] = []
    if not _CLAIM_LEDGER.is_file():
        return False, f"missing claims ledger: {_CLAIM_LEDGER}"
    if not _EVIDENCE_REFERENCES.is_file():
        return False, f"missing verified evidence references: {_EVIDENCE_REFERENCES}"
    try:
        references = json.loads(_EVIDENCE_REFERENCES.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"invalid verified evidence references: {exc}"
    if not isinstance(references, dict):
        return False, "verified evidence references must be a JSON object"
    if references.get("schema_version") != "claim-evidence-references-v1":
        problems.append("unsupported verified evidence reference schema")
    entries = references.get("claims")
    if not isinstance(entries, list):
        problems.append("verified evidence references must contain a claims list")
        entries = []
    expected_claims = _verified_claim_ids(_CLAIM_LEDGER)
    by_claim: dict[str, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("claim_id"), str):
            problems.append("verified evidence reference has no string claim_id")
            continue
        claim_id = entry["claim_id"]
        if claim_id in by_claim:
            problems.append(f"duplicate verified evidence reference for {claim_id}")
        by_claim[claim_id] = entry
    if set(by_claim) != expected_claims:
        problems.append(
            "verified claim references do not match ledger: "
            f"expected {sorted(expected_claims)}, found {sorted(by_claim)}"
        )
    for claim_id in sorted(expected_claims):
        entry = by_claim.get(claim_id, {})
        bundles = entry.get("bundles") if isinstance(entry, dict) else None
        if not isinstance(bundles, list) or not bundles:
            problems.append(f"{claim_id} has no referenced run bundle")
            continue
        for bundle in bundles:
            if not isinstance(bundle, dict):
                problems.append(f"{claim_id} has a malformed run-bundle reference")
                continue
            path_value = bundle.get("path")
            expected_run_id = bundle.get("run_id")
            expected_manifest = bundle.get("run_manifest_sha256")
            expected_finalization = bundle.get("finalization_sha256")
            reference_values = (path_value, expected_run_id, expected_manifest, expected_finalization)
            if not all(isinstance(value, str) and value for value in reference_values):
                problems.append(f"{claim_id} has an incomplete run-bundle reference")
                continue
            if not all(re.fullmatch(r"[0-9a-f]{64}", value) for value in (expected_manifest, expected_finalization)):
                problems.append(f"{claim_id} has an invalid run-bundle checksum reference")
                continue
            root = Path(path_value)
            if not root.exists():
                warnings.append(f"{claim_id} referenced bundle is not locally available: {root}")
                continue
            result = verify_run(root)
            if result.get("status") != COMPLETE_VALID:
                problems.append(f"{claim_id} referenced bundle is not complete-valid: {root}")
                continue
            manifest = root / "run_manifest.json"
            finalization = root / "finalization.json"
            if result.get("run_id") != expected_run_id:
                problems.append(f"{claim_id} run ID does not match referenced bundle: {root}")
            if _sha256(manifest) != expected_manifest:
                problems.append(f"{claim_id} run-manifest checksum does not match: {root}")
            if _sha256(finalization) != expected_finalization:
                problems.append(f"{claim_id} finalization checksum does not match: {root}")
    root_warning = _historical_root_warning()
    if root_warning is not None:
        warnings.append(root_warning)
    detail = [
        "verified claims reference complete-valid run bundles" if not problems else "claim-bound evidence issues:"
    ]
    detail.extend(problems)
    if warnings:
        detail.append("warnings:")
        detail.extend(warnings)
    return not problems, "\n".join(detail)


def _release_metadata() -> tuple[bool, str]:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    citation = yaml.safe_load(Path("CITATION.cff").read_text(encoding="utf-8"))
    expected = f"v{__version__}"
    notes = Path(f"release-notes-{expected}.md")
    issues: list[str] = []
    if 'dynamic = ["version"]' not in pyproject or "tool_agent_shift_benchmark._version.__version__" not in pyproject:
        issues.append("pyproject does not derive its version from the package version module")
    if expected not in changelog:
        issues.append(f"{expected} is absent from CHANGELOG.md")
    if citation.get("version") != __version__:
        issues.append("CITATION.cff version does not match the package version")
    if citation.get("repository-code") != "https://github.com/avlasov-co/tool-agent-shift-benchmark":
        issues.append("CITATION.cff repository URL is not canonical")
    if not notes.is_file():
        issues.append(f"missing release notes: {notes}")
    return (not issues, "release metadata is consistent" if not issues else "\n".join(issues))


def _deterministic_plan_command(python: str) -> list[str]:
    code = (
        "from tool_agent_shift_benchmark.core.config import load_config; "
        "from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec; "
        "config=load_config('small'); "
        "first=ExperimentPlanner(ExperimentSpec.from_config(config, seed=42)).plan(); "
        "second=ExperimentPlanner(ExperimentSpec.from_config(config, seed=42)).plan(); "
        "assert first == second and "
        "len({item.episode_id for item in first}) == len(first), "
        "'plan identity is not deterministic'"
    )
    return [python, "-c", code]


def _wheel_inspection(wheel_dir: Path) -> tuple[bool, str]:
    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        return False, f"expected one wheel in {wheel_dir}, found {len(wheels)}"
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
    entry_point = next((name for name in names if name.endswith(".dist-info/entry_points.txt")), None)
    if entry_point is None:
        return False, "wheel has no console entry-point metadata"
    with zipfile.ZipFile(wheels[0]) as archive:
        entry_points = archive.read(entry_point).decode("utf-8")
    return (
        "tasb = tool_agent_shift_benchmark.cli:main" in entry_points,
        "wheel contains tasb console entry point"
        if "tasb = tool_agent_shift_benchmark.cli:main" in entry_points
        else "wheel entry point does not contain tasb",
    )


def _package_source_copy(output_dir: Path) -> Path:
    """Copy source for the build so setuptools cannot create workspace build files."""
    destination = output_dir / f"package-source-{time.time_ns()}"
    ignored = shutil.ignore_patterns(
        ".git",
        ".audit",
        ".venv",
        "build",
        "dist",
        "__pycache__",
        ".pytest_cache",
        "runs",
        "*.pyc",
        "*.egg-info",
    )
    shutil.copytree(Path.cwd(), destination, ignore=ignored)
    return destination


def run_audit(
    *,
    output_dir: str | Path = ".audit",
    strict: bool = False,
    python: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[list[AuditResult], Path]:
    runner = AuditRunner(output_dir, strict=strict, python=python, timeout_seconds=timeout_seconds)
    pycache = runner.output_dir / "pycache"
    common_env = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(pycache),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    runner.run_callable("git_cleanliness", "git status --porcelain --untracked-files=all", _git_clean)
    runner.run_callable("junk_file_detection", "read-only junk-file scan", _junk_files)
    runner.run_command(
        "byte_compilation",
        [runner.python, "-m", "compileall", "-q", "src", "tests"],
        env=common_env,
    )
    runner.run_command(
        "unit_tests",
        [runner.python, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        env=common_env,
    )
    coverage_file = runner.output_dir / ".coverage"
    runner.run_command(
        "branch_coverage",
        [
            runner.python,
            "-m",
            "coverage",
            "run",
            "--branch",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        env={**common_env, "COVERAGE_FILE": str(coverage_file)},
    )
    runner.run_command(
        "configuration_validation",
        [runner.python, "-m", "tool_agent_shift_benchmark.core.config_schema", "small"],
        env=common_env,
    )
    runner.run_command(
        "deterministic_planning",
        _deterministic_plan_command(runner.python),
        env=common_env,
    )
    runner.run_callable(
        "claim_bound_evidence_consistency",
        "read-only claim-bound evidence consistency check",
        _artifact_consistency,
    )
    # Retain previous audit evidence and build into a fresh directory. Reusing a
    # static ``dist`` directory would make a later audit inspect stale wheels.
    wheel_dir = runner.output_dir / f"dist-{time.time_ns()}"
    package_source = _package_source_copy(runner.output_dir)
    runner.run_command(
        "package_build",
        [runner.python, "-m", "build", "--wheel", "--outdir", str(wheel_dir)],
        env=common_env,
        cwd=package_source,
    )
    runner.run_callable(
        "wheel_content_inspection",
        f"inspect wheel in {wheel_dir}",
        lambda: _wheel_inspection(wheel_dir),
    )
    wheel = next(iter(sorted(wheel_dir.glob("*.whl"))), None)
    venv_dir = runner.output_dir / f"wheel-venv-{time.time_ns()}"
    if wheel is None:
        runner.skip("isolated_installation", "skipped because package build produced no wheel")
        runner.skip("cli_smoke", "skipped because package build produced no wheel")
        runner.skip("cli_validate_config_alias_smoke", "skipped because package build produced no wheel")
        runner.skip("cli_config_validate_smoke", "skipped because package build produced no wheel")
        runner.skip("cli_config_migrate_smoke", "skipped because package build produced no wheel")
        runner.skip("cli_config_validate_migrated_smoke", "skipped because package build produced no wheel")
        runner.skip("cli_plan_smoke", "skipped because package build produced no wheel")
    else:
        runner.run_command(
            "isolated_installation",
            [runner.python, "-m", "venv", str(venv_dir)],
            env=common_env,
        )
        installer = venv_dir / "bin" / "python"
        runner.run_command(
            "wheel_installation",
            [str(installer), "-m", "pip", "install", str(wheel)],
            timeout_seconds=timeout_seconds,
        )
        runner.run_command("cli_smoke", [str(venv_dir / "bin" / "tasb"), "--help"], env=common_env)
        runner.run_command(
            "cli_validate_config_alias_smoke",
            [str(venv_dir / "bin" / "tasb"), "validate-config", "small"],
            env=common_env,
        )
        runner.run_command(
            "cli_config_validate_smoke",
            [str(venv_dir / "bin" / "tasb"), "config", "validate", "small"],
            env=common_env,
        )
        legacy_config = runner.output_dir / "legacy-config-smoke.yaml"
        migrated_config = runner.output_dir / "migrated-config-smoke.yaml"
        legacy_config.write_text(
            "episodes_per_combo: 1\nenvironments: [file_ops]\nagents: [naive]\nfaults: [normal]\n",
            encoding="utf-8",
        )
        runner.run_command(
            "cli_config_migrate_smoke",
            [
                str(venv_dir / "bin" / "tasb"),
                "config",
                "migrate",
                str(legacy_config),
                "--output",
                str(migrated_config),
            ],
            env=common_env,
        )
        runner.run_command(
            "cli_config_validate_migrated_smoke",
            [str(venv_dir / "bin" / "tasb"), "config", "validate", str(migrated_config)],
            env=common_env,
        )
        runner.run_command(
            "cli_plan_smoke",
            [str(venv_dir / "bin" / "tasb"), "plan", "--config", "small"],
            env=common_env,
        )
    runner.run_callable(
        "release_metadata_consistency",
        "compare pyproject and changelog version",
        _release_metadata,
    )
    report = runner.write_report()
    return runner.results, report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run non-destructive repository diagnostics")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when any check fails")
    parser.add_argument(
        "--output-dir",
        default=".audit",
        help="directory for audit-only logs and report",
    )
    parser.add_argument("--python", default=sys.executable, help="interpreter used by subprocess checks")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="per-command timeout in seconds",
    )
    args = parser.parse_args(argv)
    results, report = run_audit(
        output_dir=args.output_dir,
        strict=args.strict,
        python=args.python,
        timeout_seconds=args.timeout,
    )
    for result in results:
        explanation = f" — {result.failure_explanation}" if result.failure_explanation else ""
        print(f"{result.status.upper():7} {result.name:32} {result.duration_seconds:7.3f}s{explanation}")
    print(f"JSON report: {report}")
    return exit_code(results, args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
