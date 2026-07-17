from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tool_agent_shift_benchmark.cli import build_parser
from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.config_schema import ConfigValidationError, validate_config_data
from tool_agent_shift_benchmark.core.run_artifacts import prepare_run_dir, snapshot_outputs
from tool_agent_shift_benchmark.reporting.failure_cases import format_replay, replay_case
from tool_agent_shift_benchmark.reporting.html_report import render_html_report


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_cli_parser_accepts_core_commands() -> None:
    parser = build_parser()
    assert parser.parse_args(["validate-config", "small"]).command == "validate-config"
    assert parser.parse_args(["config", "validate", "small"]).config_command == "validate"
    assert parser.parse_args(["config", "migrate", "legacy.yaml"]).config_command == "migrate"
    assert parser.parse_args(["run", "--config", "small", "--all-envs"]).command == "run"
    assert parser.parse_args(["report", "--html"]).command == "report"


def test_config_validation_rejects_unknown_agent() -> None:
    with pytest.raises(ConfigValidationError):
        validate_config_data(
            {
                "schema_version": 2,
                "environments": ["file_ops"],
                "agents": ["imaginary_agent"],
                "faults": ["normal"],
                "fault_severities": [1.0],
                "episodes_per_combo": 1,
            }
        )


def test_run_artifact_snapshot_does_not_copy_stale_global_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_csv(Path("results/summary.csv"), [{"agent": "naive", "episodes": 1}])
    Path("figures").mkdir()
    Path("figures/example.png").write_bytes(b"png")
    Path("docs").mkdir()
    Path("docs/analysis_report.md").write_text("# report\n", encoding="utf-8")
    run_dir = prepare_run_dir("smoke", overwrite=True)
    store = ArtifactStore(run_dir)
    store.write_csv("results/summary.csv", [{"agent": "fresh", "episodes": 2}])
    manifest = snapshot_outputs(run_dir, command=["tasb", "run"])
    assert (run_dir / "results" / "summary.csv").exists()
    assert "figures/example.png" not in manifest["artifacts"]
    assert "docs/analysis_report.md" not in manifest["artifacts"]
    assert manifest["command"] == ["tasb", "run"]


def test_html_report_refuses_unverified_loose_results(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_csv(results / "summary.csv", [{"episodes": 2, "unsafe_action_rate": 0.5}])
    _write_csv(results / "failure_cases.csv", [{"case_id": "case1"}])
    _write_csv(
        results / "analysis" / "agent_safety_profile.csv",
        [
            {
                "agent": "naive",
                "episodes": 2,
                "unsafe_action_rate": 0.5,
                "coverage": 1.0,
                "safe_useful_action_rate": 0.5,
                "clean_shifted_safe_success_gap": 0.1,
            }
        ],
    )
    with pytest.raises(ValueError, match="complete-valid"):
        render_html_report(results, tmp_path / "report.html")


def test_enhanced_failure_replay_markdown(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _write_csv(
        results / "failure_cases.csv",
        [
            {
                "case_id": "case1",
                "episode_id": "ep1",
                "environment": "calendar_ops",
                "agent": "naive",
                "fault": "stale_observation",
                "action_type": "schedule",
                "unsafe_reasons": "double_booked",
                "trace_json": "{}",
            }
        ],
    )
    analysis = results / "analysis"
    analysis.mkdir(parents=True)
    (analysis / "failure_cluster_examples.jsonl").write_text(
        '{"cluster_id":"FC001","case_id":"case1"}\n{"cluster_id":"FC001","case_id":"case2"}\n',
        encoding="utf-8",
    )
    data = replay_case("case1", results / "failure_cases.csv", analysis)
    rendered = format_replay(data, "markdown")
    assert "FC001" in rendered
    assert "case2" in rendered
