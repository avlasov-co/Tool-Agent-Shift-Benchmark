from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from tool_agent_shift_benchmark import __version__

ROOT = Path(__file__).parents[1]


def _load_release_builder():
    path = ROOT / "scripts" / "build_release_artifacts.py"
    spec = importlib.util.spec_from_file_location("build_release_artifacts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_version_source_is_reflected_in_release_metadata() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = (ROOT / f"release-notes-v{__version__}.md").read_text(encoding="utf-8")

    assert 'dynamic = ["version"]' in pyproject
    assert "tool_agent_shift_benchmark._version.__version__" in pyproject
    assert 'requires-python = ">=3.10,<3.15"' in pyproject
    assert "Programming Language :: Python :: 3.14" in pyproject
    assert "https://github.com/avlasov-co/tool-agent-shift-benchmark" in pyproject
    assert citation["version"] == __version__
    assert citation["repository-code"] == "https://github.com/avlasov-co/tool-agent-shift-benchmark"
    assert f"## v{__version__} — 2026-07-17" in changelog
    assert f"v{__version__} evidence release" in notes


def test_release_checksums_cover_final_artifacts_and_detect_changes(tmp_path) -> None:
    builder = _load_release_builder()
    first = tmp_path / "first.whl"
    second = tmp_path / "second.tar.gz"
    first.write_bytes(b"wheel")
    second.write_bytes(b"sdist")

    checksum_path = builder.write_checksums(tmp_path, [first, second])
    builder.verify_checksums(tmp_path)

    assert checksum_path.read_text(encoding="utf-8").splitlines()[0].endswith("  first.whl")
    first.write_bytes(b"modified-wheel")
    try:
        builder.verify_checksums(tmp_path)
    except builder.ReleaseArtifactError as exc:
        assert "checksum mismatch" in str(exc)
    else:
        raise AssertionError("tampered release artifact passed checksum verification")


def test_release_builder_refuses_to_overwrite_existing_output(tmp_path) -> None:
    builder = _load_release_builder()
    output = tmp_path / "release-artifacts"
    output.mkdir()
    (output / "existing.txt").write_text("preserve this", encoding="utf-8")

    with pytest.raises(builder.ReleaseArtifactError, match="new or empty"):
        builder.build_release_artifacts(source_root=ROOT, output_dir=output, python="python")
