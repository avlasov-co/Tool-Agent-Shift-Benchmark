import csv
from pathlib import Path

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.verification import COMPLETE_VALID, verify_run
from tool_agent_shift_benchmark.reporting.failure_cases import replay_case
from tool_agent_shift_benchmark.reporting.plots import _weighted_metric_rows, generate_plots
from tool_agent_shift_benchmark.reporting.report import generate_markdown_report
from tool_agent_shift_benchmark.run_eval import run_eval


def test_reporting_outputs_and_replay(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    store = ArtifactStore(tmp_path / "run")
    run_eval("small", 42, artifact_store=store)
    assert (store.run_dir / "results" / "clean_vs_shifted.csv").exists()
    assert not (store.run_dir / "results" / "static_vs_dynamic.csv").exists()
    plots = generate_plots(
        store.run_dir / "results" / "summary.csv",
        "plots",
        results_dir=store.run_dir / "results",
        artifact_store=store,
    )
    assert plots
    assert (store.run_dir / "plots" / "unsafe_action_rate.png").exists()
    store.finalize(command=["test", "run-and-plot"])
    report = generate_markdown_report(
        store.run_dir / "results" / "summary.csv",
        "reports/experimental_report.md",
        artifact_store=store,
    )
    assert Path(report).exists()
    store.finalize(command=["test", "run-plot-report"])
    assert verify_run(store.run_dir)["status"] == COMPLETE_VALID
    assert (store.run_dir / "reports" / "source_evidence_snapshot.json").exists()
    assert (store.run_dir / "reports" / "report_provenance.json").exists()
    assert (store.run_dir / "reports" / "report_validation.json").exists()
    assert "complete_valid" in Path(report).read_text(encoding="utf-8")
    with (store.run_dir / "results" / "failure_cases.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    replayed = replay_case(rows[0]["case_id"], str(store.run_dir / "results" / "failure_cases.csv"))
    assert replayed["case_id"] == rows[0]["case_id"]
    with (store.run_dir / "results" / "monitor_events.csv").open(newline="", encoding="utf-8") as f:
        monitor_rows = list(csv.DictReader(f))
    assert monitor_rows
    assert "reasons" in monitor_rows[0]


def test_plot_aggregation_sums_raw_counts_instead_of_mean_of_rates():
    rows = _weighted_metric_rows(
        [
            {"agent": "agent", "metric_name": "safe_success_rate", "numerator": "1", "denominator": "2"},
            {"agent": "agent", "metric_name": "safe_success_rate", "numerator": "9", "denominator": "10"},
        ],
        "safe_success_rate",
    )
    assert rows == [{"agent": "agent", "value": 10 / 12, "numerator": 10.0, "denominator": 12.0}]


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


def test_confidence_plot_draws_numeric_interval_whiskers(tmp_path, monkeypatch):
    import matplotlib.axes

    store = ArtifactStore(tmp_path / "run")
    store.write_csv(
        "results/summary.csv",
        [
            {
                "agent_name": "agent",
                "unsafe_action_rate": 0.1,
                "coverage": 0.8,
                "safe_success_rate": 0.7,
            }
        ],
    )
    store.write_csv(
        "results/confidence_intervals.csv",
        [
            {
                "environment": "file_ops",
                "agent": "agent",
                "fault": "normal",
                "metric": "safe_success_rate",
                "effect_size": 0.7,
                "interval_low": 0.5,
                "interval_high": 0.85,
                "status": "ok",
            }
        ],
    )
    calls = []
    original = matplotlib.axes.Axes.errorbar

    def recording_errorbar(self, *args, **kwargs):
        calls.append(kwargs.get("xerr") if kwargs.get("xerr") is not None else kwargs.get("yerr"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "errorbar", recording_errorbar)
    generate_plots(
        store.run_dir / "results" / "summary.csv",
        "plots",
        results_dir=store.run_dir / "results",
        artifact_store=store,
    )

    assert calls and calls[0] is not None
    assert (store.run_dir / "plots" / "confidence_intervals.png").is_file()


def test_reliability_diagram_requires_probability_score_contract(tmp_path):
    store = ArtifactStore(tmp_path / "run")
    store.write_csv("results/summary.csv", [{"agent_name": "agent", "unsafe_action_rate": 0.1}])
    store.write_csv(
        "analysis/monitor_calibration.csv",
        [
            {
                "monitor_name": "ALL",
                "score_semantics": "probability",
                "score_calibration_contract": "probability-score-v1",
                "mean_predicted_probability": 0.2,
                "empirical_proposed_unsafe_rate": 0.25,
                "interval_low": 0.1,
                "interval_high": 0.4,
            },
            {
                "monitor_name": "ALL",
                "score_semantics": "probability",
                "score_calibration_contract": "probability-score-v1",
                "mean_predicted_probability": 0.8,
                "empirical_proposed_unsafe_rate": 0.75,
                "interval_low": 0.6,
                "interval_high": 0.9,
            },
        ],
    )
    generate_plots(
        store.run_dir / "results" / "summary.csv",
        "plots",
        results_dir=store.run_dir / "results",
        artifact_store=store,
    )
    assert (store.run_dir / "plots" / "monitor_reliability_diagram.png").is_file()

    ordinal = ArtifactStore(tmp_path / "ordinal")
    ordinal.write_csv("results/summary.csv", [{"agent_name": "agent", "unsafe_action_rate": 0.1}])
    ordinal.write_csv(
        "analysis/monitor_calibration.csv",
        [
            {
                "monitor_name": "ALL",
                "score_semantics": "ordinal_risk_score",
                "mean_predicted_probability": 0.5,
                "empirical_proposed_unsafe_rate": 0.5,
            }
        ],
    )
    generate_plots(
        ordinal.run_dir / "results" / "summary.csv",
        "plots",
        results_dir=ordinal.run_dir / "results",
        artifact_store=ordinal,
    )
    assert not (ordinal.run_dir / "plots" / "monitor_reliability_diagram.png").exists()
