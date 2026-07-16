#!/usr/bin/env python3
"""Build final sdist/wheel artifacts and checksums without touching the checkout."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


COPY_IGNORES = {
    ".audit",
    ".coverage",
    ".git",
    ".mypy_cache",
    ".puppeteer-cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "figures",
    "htmlcov",
    "node_modules",
    "results",
    "runs",
}


class ReleaseArtifactError(RuntimeError):
    """Raised when final artifact construction is not safe or complete."""


def _resolve_python(value: str) -> str:
    path = Path(value)
    return str(path.absolute()) if path.is_file() else shutil.which(value) or value


def _package_version(source_root: Path) -> str:
    namespace: dict[str, str] = {}
    version_module = source_root / "src" / "tool_agent_shift_benchmark" / "_version.py"
    exec(version_module.read_text(encoding="utf-8"), namespace)
    version = namespace.get("__version__")
    if not isinstance(version, str):
        raise ReleaseArtifactError(f"could not read __version__ from {version_module}")
    return version


def _copy_source(source_root: Path, destination: Path, output_dir: Path) -> None:
    output_in_source = output_dir.parent == source_root

    def ignore(_: str, names: list[str]) -> set[str]:
        ignored = {
            name
            for name in names
            if name in COPY_IGNORES
            or name.endswith((".egg-info", ".pyc", ".pyo"))
            or name == ".DS_Store"
        }
        if output_in_source and _ == str(source_root):
            ignored.add(output_dir.name)
        return ignored

    shutil.copytree(source_root, destination, ignore=ignore)


def _distribution_validator(source_root: Path):
    path = source_root / "scripts" / "distribution_smoke.py"
    spec = importlib.util.spec_from_file_location("tasb_distribution_smoke", path)
    if spec is None or spec.loader is None:
        raise ReleaseArtifactError(f"could not load archive validator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(command: Sequence[str], *, cwd: Path) -> None:
    completed = subprocess.run(list(command), cwd=cwd, check=False)
    if completed.returncode:
        raise ReleaseArtifactError(f"command exited {completed.returncode}: {' '.join(command)}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(output_dir: Path, files: Sequence[Path]) -> Path:
    """Write checksums only after every final release artifact exists."""
    if any(not path.is_file() for path in files):
        raise ReleaseArtifactError("cannot checksum a missing final artifact")
    checksum_path = output_dir / "SHA256SUMS"
    lines = [f"{_sha256(path)}  {path.name}" for path in sorted(files, key=lambda item: item.name)]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def verify_checksums(output_dir: Path) -> None:
    checksum_path = output_dir / "SHA256SUMS"
    if not checksum_path.is_file():
        raise ReleaseArtifactError(f"missing checksum manifest: {checksum_path}")
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        try:
            expected, filename = line.split("  ", maxsplit=1)
        except ValueError as exc:
            raise ReleaseArtifactError(f"malformed checksum line: {line}") from exc
        artifact = output_dir / filename
        if not artifact.is_file() or _sha256(artifact) != expected:
            raise ReleaseArtifactError(f"checksum mismatch: {filename}")


def build_release_artifacts(*, source_root: Path, output_dir: Path, python: str) -> list[Path]:
    source_root = source_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ReleaseArtifactError(f"output directory must be new or empty; refusing to overwrite: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    python = _resolve_python(python)
    version = _package_version(source_root)
    temporary_root = Path(tempfile.mkdtemp(prefix="tasb-release-artifact-source-"))
    try:
        build_source = temporary_root / "source"
        _copy_source(source_root, build_source, output_dir)
        _run([python, "-m", "build", "--sdist", "--wheel", "--outdir", str(output_dir)], cwd=build_source)
        artifacts = sorted(output_dir.glob("*.tar.gz")) + sorted(output_dir.glob("*.whl"))
        expected_names = {
            f"tool_agent_shift_benchmark-{version}.tar.gz",
            f"tool_agent_shift_benchmark-{version}-py3-none-any.whl",
        }
        if {artifact.name for artifact in artifacts} != expected_names:
            raise ReleaseArtifactError(
                f"unexpected artifacts for version {version}: {[artifact.name for artifact in artifacts]}"
            )
        validator = _distribution_validator(source_root)
        for artifact in artifacts:
            validator.validate_archive(artifact)
        _run([python, "-m", "twine", "check", *map(str, artifacts)], cwd=build_source)
        sbom = output_dir / "sbom.cdx.json"
        _run(
            [
                python,
                "-m",
                "cyclonedx_py",
                "environment",
                "--output-reproducible",
                "--pyproject",
                str(build_source / "pyproject.toml"),
                "--mc-type",
                "library",
                "--of",
                "JSON",
                "--output-file",
                str(sbom),
                python,
            ],
            cwd=build_source,
        )
        final_files = [*artifacts, sbom]
        write_checksums(output_dir, final_files)
        verify_checksums(output_dir)
        return final_files
    except Exception:
        print(f"release artifact source retained for diagnostics: {temporary_root}", file=sys.stderr)
        raise
    finally:
        if not sys.exc_info()[0]:
            shutil.rmtree(temporary_root)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build validated sdist/wheel release artifacts and checksums")
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    try:
        artifacts = build_release_artifacts(
            source_root=args.source_root,
            output_dir=args.output_dir,
            python=args.python,
        )
        print("built final release artifacts:")
        for artifact in artifacts:
            print(f"- {artifact}")
        print(f"- {args.output_dir / 'SHA256SUMS'}")
    except ReleaseArtifactError as exc:
        print(f"release artifact build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
