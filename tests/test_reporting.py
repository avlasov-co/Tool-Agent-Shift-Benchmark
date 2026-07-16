import csv
from pathlib import Path

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.reporting.failure_cases import replay_case
from tool_agent_shift_benchmark.reporting.plots import generate_plots
from tool_agent_shift_benchmark.reporting.report import generate_markdown_report
from tool_agent_shift_benchmark.run_eval import run_eval


def test_reporting_outputs_and_replay(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    store = ArtifactStore(tmp_path / "run")
    run_eval("small", 42, artifact_store=store)
    plots = generate_plots(
        store.run_dir / "results" / "summary.csv",
        "plots",
        results_dir=store.run_dir / "results",
        artifact_store=store,
    )
    assert plots
    assert (store.run_dir / "plots" / "unsafe_action_rate.png").exists()
    report = generate_markdown_report(
        store.run_dir / "results" / "summary.csv",
        "reports/experimental_report.md",
        artifact_store=store,
    )
    assert Path(report).exists()
    with (store.run_dir / "results" / "failure_cases.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    replayed = replay_case(rows[0]["case_id"], str(store.run_dir / "results" / "failure_cases.csv"))
    assert replayed["case_id"] == rows[0]["case_id"]
    with (store.run_dir / "results" / "monitor_events.csv").open(newline="", encoding="utf-8") as f:
        monitor_rows = list(csv.DictReader(f))
    assert monitor_rows
    assert "reasons" in monitor_rows[0]


def test_plots_do_not_consume_or_delete_stale_global_confidence_figure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from tool_agent_shift_benchmark.reporting.plots import generate_plots
    from tool_agent_shift_benchmark.run_eval import run_eval

    store = ArtifactStore(tmp_path / "run")
    run_eval("small", 42, artifact_store=store)
    stale = tmp_path / "figures" / "confidence_intervals.png"
    stale.parent.mkdir(exist_ok=True)
    stale.write_bytes(b"stale")
    generate_plots(
        store.run_dir / "results" / "summary.csv",
        "plots",
        results_dir=store.run_dir / "results",
        artifact_store=store,
    )
    assert stale.exists()
    assert not (store.run_dir / "plots" / "confidence_intervals.png").exists()
