import csv
from pathlib import Path

from tool_agent_shift_benchmark.reporting.failure_cases import replay_case
from tool_agent_shift_benchmark.reporting.plots import generate_plots
from tool_agent_shift_benchmark.reporting.report import generate_markdown_report
from tool_agent_shift_benchmark.run_eval import run_eval


def test_reporting_outputs_and_replay(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import pathlib
    import shutil

    srcroot = pathlib.Path(__file__).resolve().parents[1]
    shutil.copytree(srcroot / "configs", tmp_path / "configs")
    run_eval("configs/small.yaml", 42)
    plots = generate_plots()
    assert plots
    assert Path("figures/unsafe_action_rate.png").exists()
    report = generate_markdown_report()
    assert Path(report).exists()
    with open("results/failure_cases.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    replayed = replay_case(rows[0]["case_id"])
    assert replayed["case_id"] == rows[0]["case_id"]
    with open("results/monitor_events.csv", newline="", encoding="utf-8") as f:
        monitor_rows = list(csv.DictReader(f))
    assert monitor_rows
    assert "reasons" in monitor_rows[0]


def test_plots_remove_stale_confidence_interval_figure_without_ci(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import pathlib
    import shutil

    from tool_agent_shift_benchmark.reporting.plots import generate_plots
    from tool_agent_shift_benchmark.run_eval import run_eval

    srcroot = pathlib.Path(__file__).resolve().parents[1]
    shutil.copytree(srcroot / "configs", tmp_path / "configs")
    run_eval("configs/small.yaml", 42)
    stale = tmp_path / "figures" / "confidence_intervals.png"
    stale.parent.mkdir(exist_ok=True)
    stale.write_bytes(b"stale")
    generate_plots()
    assert not stale.exists()
