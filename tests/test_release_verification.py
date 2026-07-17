from __future__ import annotations

import json
import zipfile

from tool_agent_shift_benchmark.release_verification import (
    DETERMINISTIC_OUTPUT_DIRECTORIES,
    VOLATILE_OUTPUT_EXCLUSIONS,
    ReleaseVerificationError,
    canonical_output_tree,
    compare_deterministic_outputs,
    extract_pinned_browser,
)


def _write_run_bundle(path, payload: dict[str, object]) -> None:
    for directory in DETERMINISTIC_OUTPUT_DIRECTORIES:
        (path / directory).mkdir(parents=True, exist_ok=True)
    (path / "results" / "config.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (path / "results" / "episodes.jsonl").write_text('{"b":2,"a":1}\n', encoding="utf-8")
    (path / "plots" / "plot.png").write_bytes(b"deterministic-png-bytes")
    (path / "reports" / "analysis_report.html").write_text("<html>stable</html>\n", encoding="utf-8")
    (path / "checkpoint.json").write_text('{"schema_version":"checkpoint-v2"}\n', encoding="utf-8")
    (path / "status.json").write_text('{"schema_version":"run-status-v1"}\n', encoding="utf-8")


def test_canonical_output_tree_normalizes_json_encodings(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_run_bundle(first, {"b": 2, "a": 1})
    _write_run_bundle(second, {"a": 1, "b": 2})

    assert canonical_output_tree(first) == canonical_output_tree(second)
    assert compare_deterministic_outputs(first, second) == (True, "5 deterministic files matched exactly")


def test_canonical_output_comparison_reports_content_changes(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_run_bundle(first, {"value": 1})
    _write_run_bundle(second, {"value": 2})

    passed, detail = compare_deterministic_outputs(first, second)

    assert not passed
    assert "results/config.json" in detail
    assert "run_manifest.json" in VOLATILE_OUTPUT_EXCLUSIONS


def test_pinned_browser_extraction_rejects_unsafe_members(tmp_path) -> None:
    browser_root = tmp_path / "chrome-headless-shell"
    install_root = browser_root / "mac_arm-131.0.6778.204"
    install_root.mkdir(parents=True)
    archive = browser_root / "131.0.6778.204-browser.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside", "not permitted")

    try:
        extract_pinned_browser(tmp_path)
    except ReleaseVerificationError as exc:
        assert "unsafe browser archive member" in str(exc)
    else:
        raise AssertionError("unsafe browser archive member was accepted")


def test_pinned_browser_extraction_preserves_executable_mode(tmp_path) -> None:
    browser_root = tmp_path / "chrome-headless-shell"
    install_root = browser_root / "mac_arm-131.0.6778.204"
    install_root.mkdir(parents=True)
    archive = browser_root / "131.0.6778.204-browser.zip"
    member = zipfile.ZipInfo("chrome-headless-shell-mac-arm64/chrome-headless-shell")
    member.external_attr = 0o100755 << 16
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(member, "#!/bin/sh\nexit 0\n")

    executable = extract_pinned_browser(tmp_path)

    assert executable.is_file()
    assert executable.stat().st_mode & 0o111
