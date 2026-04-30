import csv
from pathlib import Path
from src.run_eval import run_eval
from src.reporting.plots import generate_plots
from src.reporting.report import generate_markdown_report
from src.reporting.failure_cases import replay_case


def test_reporting_outputs_and_replay(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shutil, pathlib
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
