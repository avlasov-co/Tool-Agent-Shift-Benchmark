from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path


def _load_distribution_smoke():
    path = Path(__file__).parents[1] / "scripts" / "distribution_smoke.py"
    spec = importlib.util.spec_from_file_location("distribution_smoke", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_archive_inspection_accepts_required_wheel_contents(tmp_path) -> None:
    smoke = _load_distribution_smoke()
    wheel = tmp_path / "tool_agent_shift_benchmark-0.3.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("tool_agent_shift_benchmark/__init__.py", "")
        archive.writestr("tool_agent_shift_benchmark/resources/configs/small.yaml", "schema_version: 2\n")
        archive.writestr("tool_agent_shift_benchmark/resources/policies/offline_llm_policy.json", "{}")
        archive.writestr("tool_agent_shift_benchmark/resources/templates/report.html", "<html></html>")
        archive.writestr("tool_agent_shift_benchmark-0.3.1.dist-info/METADATA", "Metadata-Version: 2.3\n")

    assert smoke.archive_content_errors(wheel) == []


def test_archive_inspection_rejects_junk_and_undeclared_packages(tmp_path) -> None:
    smoke = _load_distribution_smoke()
    wheel = tmp_path / "tool_agent_shift_benchmark-0.3.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("tool_agent_shift_benchmark/.venv/ignored.py", "")
        archive.writestr("other_package/__init__.py", "")
        archive.writestr("other_package.egg-info/PKG-INFO", "Metadata-Version: 2.3\n")

    errors = smoke.archive_content_errors(wheel)
    assert any("forbidden path component" in error for error in errors)
    assert "undeclared Python package in archive: other_package" in errors
    assert "stale egg-info in archive: other_package.egg-info/PKG-INFO" in errors
    assert sum("missing required package resource" in error for error in errors) == 3
