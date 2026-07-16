from __future__ import annotations

import csv
from pathlib import Path

import pytest
from src.cli import build_parser
from src.core.config_schema import ConfigValidationError, validate_config_data
from src.core.run_artifacts import prepare_run_dir, snapshot_outputs
from src.reporting.failure_cases import format_replay, replay_case
from src.reporting.html_report import render_html_report


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
    assert parser.parse_args(["validate-config", "configs/small.yaml"]).command == "validate-config"
    assert parser.parse_args(["config", "validate", "configs/small.yaml"]).config_command == "validate"
    assert parser.parse_args(["config", "migrate", "legacy.yaml"]).config_command == "migrate"
    assert parser.parse_args(["run", "--config", "configs/small.yaml", "--all-envs"]).command == "run"
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


def test_run_artifact_snapshot_copies_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_csv(Path("results/summary.csv"), [{"agent": "naive", "episodes": 1}])
    Path("figures").mkdir()
    Path("figures/example.png").write_bytes(b"png")
    Path("docs").mkdir()
    Path("docs/analysis_report.md").write_text("# report\n", encoding="utf-8")
    run_dir = prepare_run_dir("smoke", overwrite=True)
    manifest = snapshot_outputs(run_dir, command=["tasb", "run"])
    assert (run_dir / "results" / "summary.csv").exists()
    assert (run_dir / "figures" / "example.png").exists()
    assert (run_dir / "docs" / "analysis_report.md").exists()
    assert manifest["command"] == ["tasb", "run"]


def test_html_report_is_generated(tmp_path: Path) -> None:
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
                "safety_coverage_score": 0.1,
            }
        ],
    )
    out = render_html_report(results, tmp_path / "report.html")
    text = out.read_text(encoding="utf-8")
    assert "Agent safety profile" in text
    assert "naive" in text


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
