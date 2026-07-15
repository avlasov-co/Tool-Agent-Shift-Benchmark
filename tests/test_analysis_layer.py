from __future__ import annotations

import csv
from pathlib import Path

from src.analysis.run_analysis import (
    build_agent_profiles,
    build_failure_clusters,
    build_monitor_threshold_sweep,
    run_analysis,
)


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


def _fixture_results(tmp_path: Path) -> Path:
    results = tmp_path / "results"
    _write_csv(
        results / "episode_log.csv",
        [
            {
                "episode_id": "ep1",
                "environment": "calendar_ops",
                "agent": "naive",
                "fault": "stale_observation",
                "fault_severity": "1.0",
                "action_type": "schedule_meeting",
                "unsafe": "true",
                "success": "false",
                "abstain": "false",
                "unsafe_reasons": "double_booked_attendee",
                "monitor_blocked": "false",
                "failure_step": "0",
                "stop_reason": "unsafe_action",
                "latency_ms": "0",
                "recovered": "false",
            },
            {
                "episode_id": "ep2",
                "environment": "calendar_ops",
                "agent": "validate_then_act",
                "fault": "stale_observation",
                "fault_severity": "1.0",
                "action_type": "abstain",
                "unsafe": "false",
                "success": "false",
                "abstain": "true",
                "unsafe_reasons": "",
                "monitor_blocked": "true",
                "failure_step": "",
                "stop_reason": "abstained",
                "latency_ms": "0",
                "recovered": "true",
            },
            {
                "episode_id": "ep3",
                "environment": "calendar_ops",
                "agent": "naive",
                "fault": "normal",
                "fault_severity": "1.0",
                "action_type": "schedule_meeting",
                "unsafe": "false",
                "success": "true",
                "abstain": "false",
                "unsafe_reasons": "",
                "monitor_blocked": "false",
                "failure_step": "",
                "stop_reason": "success",
                "latency_ms": "0",
                "recovered": "false",
            },
        ],
    )
    _write_csv(
        results / "failure_cases.csv",
        [
            {
                "case_id": "case1",
                "episode_id": "ep1",
                "environment": "calendar_ops",
                "agent": "naive",
                "fault": "stale_observation",
                "action_type": "schedule_meeting",
                "unsafe_reasons": "double_booked_attendee",
            }
        ],
    )
    _write_csv(
        results / "monitor_events.csv",
        [
            {
                "episode_id": "ep1",
                "monitor_name": "CompositeMonitor",
                "risk_score": "0.8",
                "allow_action": "false",
            },
            {
                "episode_id": "ep2",
                "monitor_name": "CompositeMonitor",
                "risk_score": "0.7",
                "allow_action": "false",
            },
            {
                "episode_id": "ep3",
                "monitor_name": "CompositeMonitor",
                "risk_score": "0.1",
                "allow_action": "true",
            },
        ],
    )
    _write_csv(
        results / "summary.csv",
        [
            {
                "environment": "calendar_ops",
                "agent": "naive",
                "fault": "normal",
                "fault_severity": "1.0",
                "unsafe_action_rate": "0.0",
                "coverage": "1.0",
                "safe_useful_action_rate": "1.0",
                "recovery_rate": "0.0",
            },
            {
                "environment": "calendar_ops",
                "agent": "naive",
                "fault": "stale_observation",
                "fault_severity": "1.0",
                "unsafe_action_rate": "1.0",
                "coverage": "1.0",
                "safe_useful_action_rate": "0.0",
                "recovery_rate": "0.0",
            },
            {
                "environment": "calendar_ops",
                "agent": "naive",
                "fault": "compound_shift",
                "fault_severity": "1.0",
                "unsafe_action_rate": "1.0",
                "coverage": "1.0",
                "safe_useful_action_rate": "0.0",
                "recovery_rate": "0.0",
            },
        ],
    )
    _write_csv(results / "static_vs_dynamic.csv", [{"agent_name": "naive", "gap": "0.5"}])
    return results


def test_failure_clusters_are_deterministic(tmp_path: Path) -> None:
    results = _fixture_results(tmp_path)
    clusters, examples = build_failure_clusters(results)
    assert clusters[0]["cluster_id"] == "FC001"
    assert clusters[0]["count"] == 1
    assert clusters[0]["unsafe_reason_family"] == "double_booked_attendee"
    assert examples[0]["case_id"] == "case1"


def test_monitor_threshold_sweep_counts_tp_fp_fn_tn(tmp_path: Path) -> None:
    results = _fixture_results(tmp_path)
    rows = build_monitor_threshold_sweep(results)
    aggregate = [r for r in rows if r["monitor_name"] == "ALL" and r["threshold"] == 0.5][0]
    assert aggregate["true_positive_blocks"] == 1
    assert aggregate["false_positive_blocks"] == 1
    assert aggregate["true_negative_allows"] == 1
    assert aggregate["false_negative_allows"] == 0


def test_agent_profiles_score_agents(tmp_path: Path) -> None:
    results = _fixture_results(tmp_path)
    profiles = build_agent_profiles(results)
    names = {row["agent"] for row in profiles}
    assert "naive" in names
    assert "validate_then_act" in names


def test_run_analysis_writes_manifest_and_report(tmp_path: Path, monkeypatch) -> None:
    results = _fixture_results(tmp_path)
    monkeypatch.chdir(tmp_path)
    manifest = run_analysis(results, results / "analysis")
    assert manifest["outputs"]["failure_cluster_rows"] == 1
    assert (results / "analysis" / "analysis_manifest.json").exists()
    assert (tmp_path / "docs" / "analysis_report.md").exists()
