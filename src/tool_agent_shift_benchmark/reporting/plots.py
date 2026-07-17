"""Readable, publication-style benchmark figures.

The old renderer intentionally emitted bare pixel bars.  These figures are
research outputs, so labels and annotations are part of the data contract.
"""

from __future__ import annotations

import csv
from io import BytesIO
from pathlib import Path

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore

_ARTIFACT_STORE: ArtifactStore | None = None


def _save_figure(fig, out_path: str | Path) -> None:
    if _ARTIFACT_STORE is None:
        fig.savefig(out_path, facecolor="white", bbox_inches="tight")
        return
    buffer = BytesIO()
    fig.savefig(buffer, format="png", facecolor="white", bbox_inches="tight")
    _ARTIFACT_STORE.write_bytes(out_path, buffer.getvalue())


def _load_plotting_dependencies():
    try:
        import matplotlib
        import numpy as np
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Plot generation requires the optional 'analysis' dependencies. "
            "Install them with: python -m pip install 'tool-agent-shift-benchmark[analysis]'"
        ) from exc
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt, np


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _weighted_metric_rows(
    evidence: list[dict[str, str]], metric: str, *, group_key: str = "agent"
) -> list[dict[str, object]]:
    grouped: dict[str, list[float]] = {}
    for row in evidence:
        if row.get("metric_name") != metric:
            continue
        key = row.get(group_key, "ALL") or "ALL"
        counts = grouped.setdefault(key, [0.0, 0.0])
        counts[0] += _number(row.get("numerator"))
        counts[1] += _number(row.get("denominator"))
    return [
        {
            group_key: key,
            "value": numerator / denominator if denominator else 0.0,
            "numerator": numerator,
            "denominator": denominator,
        }
        for key, (numerator, denominator) in sorted(grouped.items())
    ]


def _weighted_safety_coverage_rows(evidence: list[dict[str, str]]) -> list[dict[str, object]]:
    unsafe = {row["agent"]: row for row in _weighted_metric_rows(evidence, "unsafe_or_failed_rate")}
    useful = {row["agent"]: row for row in _weighted_metric_rows(evidence, "useful_action_rate")}
    return [
        {
            "agent_name": agent,
            "unsafe_or_failed_rate": unsafe.get(agent, {}).get("value", 0.0),
            "coverage": useful.get(agent, {}).get("value", 0.0),
        }
        for agent in sorted(set(unsafe) | set(useful))
    ]


BLUE = "#2563A6"
TEAL = "#0F766E"
RED = "#C2413B"
GOLD = "#C27A16"
GRID = "#D9E2EC"


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _finish(ax, title: str, subtitle: str, ylabel: str, percent: bool = True) -> None:
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", pad=18)
    ax.text(
        0,
        1.02,
        subtitle,
        transform=ax.transAxes,
        fontsize=9,
        color="#52606D",
        va="bottom",
    )
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    if percent:
        ax.set_ylim(0, 1)
        ax.set_yticks(np.linspace(0, 1, 6))
        ax.set_yticklabels([f"{v:.0%}" for v in np.linspace(0, 1, 6)])
    ax.tick_params(axis="x", labelrotation=30)


def _bar(
    rows,
    metric: str,
    out_path: str | Path,
    *,
    key="agent_name",
    title: str,
    subtitle: str,
    ylabel: str,
    color=BLUE,
    percent=True,
) -> None:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(row.get(key, row.get("agent_name", "all")) or "all", []).append(_number(row.get(metric)))
    labels = list(grouped) or ["No data"]
    values = [sum(v) / len(v) for v in grouped.values()] or [0.0]
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=150)
    bars = ax.bar(labels, values, color=color, width=0.68)
    _finish(ax, title, subtitle, ylabel, percent)
    for bar, value in zip(bars, values):
        text = f"{value:.1%}" if percent else f"{value:.2f}"
        ax.annotate(
            text,
            (bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            fontweight="bold",
        )
    fig.tight_layout()
    _save_figure(fig, out_path)
    plt.close(fig)


def _interval_bar(rows, out_path: str | Path, *, title: str, subtitle: str, ylabel: str) -> None:
    eligible = [
        row
        for row in rows
        if row.get("status") == "ok"
        and row.get("interval_low") not in {None, ""}
        and row.get("interval_high") not in {None, ""}
    ]
    if not eligible:
        return
    eligible = sorted(
        eligible,
        key=lambda row: (
            -(_number(row.get("interval_high")) - _number(row.get("interval_low"))),
            str(row.get("environment", "")),
            str(row.get("agent", "")),
            str(row.get("fault", "")),
        ),
    )[:30]
    labels = [
        " / ".join(
            value
            for value in (
                row.get("environment", ""),
                row.get("agent", ""),
                row.get("fault", ""),
            )
            if value
        )
        or row.get("metric", "estimate")
        for row in eligible
    ]
    values = [_number(row.get("effect_size", row.get("mean"))) for row in eligible]
    lower = [value - _number(row.get("interval_low")) for value, row in zip(values, eligible, strict=True)]
    upper = [_number(row.get("interval_high")) - value for value, row in zip(values, eligible, strict=True)]
    positions = np.arange(len(eligible))
    fig, ax = plt.subplots(figsize=(max(10, len(eligible) * 0.55), 5.8), dpi=150)
    bars = ax.bar(positions, values, color=BLUE, width=0.68)
    ax.errorbar(
        positions,
        values,
        yerr=np.array([lower, upper]),
        fmt="none",
        ecolor="#172B4D",
        elinewidth=1.3,
        capsize=4,
        capthick=1.3,
    )
    ax.set_xticks(positions, labels)
    _finish(ax, title, f"{subtitle} At most 30 widest cells are shown.", ylabel, percent=True)
    for bar, value in zip(bars, values, strict=True):
        ax.annotate(
            f"{value:.1%}",
            (bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    fig.tight_layout()
    _save_figure(fig, out_path)
    plt.close(fig)


def _reliability_diagram(rows, out_path: str | Path) -> None:
    probability_rows = [
        row
        for row in rows
        if row.get("score_semantics") == "probability"
        and row.get("score_calibration_contract") == "probability-score-v1"
    ]
    aggregate = [row for row in probability_rows if row.get("monitor_name") == "ALL"]
    selected = aggregate or probability_rows
    if not selected:
        return
    selected = sorted(selected, key=lambda row: _number(row.get("mean_predicted_probability")))
    predicted = [_number(row.get("mean_predicted_probability")) for row in selected]
    observed = [_number(row.get("empirical_proposed_unsafe_rate")) for row in selected]
    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=150)
    ax.plot([0, 1], [0, 1], linestyle="--", color="#7B8794", label="Perfect calibration")
    ax.plot(predicted, observed, marker="o", color=TEAL, linewidth=2, label="Observed")
    interval_rows = [
        (index, row)
        for index, row in enumerate(selected)
        if row.get("interval_low") not in {None, ""} and row.get("interval_high") not in {None, ""}
    ]
    if interval_rows:
        positions = [predicted[index] for index, _row in interval_rows]
        estimates = [observed[index] for index, _row in interval_rows]
        lower = [
            estimate - _number(row.get("interval_low"))
            for estimate, (_index, row) in zip(estimates, interval_rows, strict=True)
        ]
        upper = [
            _number(row.get("interval_high")) - estimate
            for estimate, (_index, row) in zip(estimates, interval_rows, strict=True)
        ]
        ax.errorbar(positions, estimates, yerr=np.array([lower, upper]), fmt="none", ecolor="#172B4D", capsize=4)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Mean predicted unsafe probability")
    _finish(
        ax,
        "Monitor reliability diagram",
        "Only scores declared under probability-score-v1 are eligible; whiskers are scenario-clustered intervals.",
        "Empirical proposed-action unsafe rate",
    )
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    _save_figure(fig, out_path)
    plt.close(fig)


def _precision_recall_plot(rows, out_path: str | Path) -> None:
    selected = [row for row in rows if row.get("monitor_name") == "ALL"] or rows
    selected = [
        row for row in selected if row.get("precision") not in {None, ""} and row.get("recall") not in {None, ""}
    ]
    if not selected:
        return
    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=150)
    x = [_number(row.get("recall")) for row in selected]
    y = [_number(row.get("precision")) for row in selected]
    colors = [_number(row.get("threshold")) for row in selected]
    points = ax.scatter(x, y, c=colors, cmap="viridis", s=52, edgecolor="white", linewidth=0.6)
    fig.colorbar(points, ax=ax, label="Detector threshold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Recall on unsafe proposed actions")
    _finish(
        ax,
        "Monitor precision–recall trade-off",
        "Both axes use counterfactual proposed-action risk; points are detector thresholds, not gating outcomes.",
        "Precision",
    )
    fig.tight_layout()
    _save_figure(fig, out_path)
    plt.close(fig)


def _scatter(rows, out_path: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=150)
    for row in rows:
        risk = row.get("unsafe_or_failed_rate", row.get("unsafe_action_rate"))
        x, y = _number(row.get("coverage")), 1 - _number(risk)
        ax.scatter(x, y, s=70, alpha=0.82, color=TEAL, edgecolor="white", linewidth=0.7)
        label = row.get("agent_name") or row.get("env_name") or "run"
        ax.annotate(
            label,
            (x, y),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=7,
            color="#334E68",
        )
    _finish(
        ax,
        "Coverage vs. safety",
        "Each point pools one agent by raw counts; higher and farther right is better.",
        "One minus unsafe-or-failed episode rate",
    )
    ax.set_xlabel("Coverage: fraction of useful actions completed")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks(np.linspace(0, 1, 6))
    ax.set_xticklabels([f"{v:.0%}" for v in np.linspace(0, 1, 6)])
    fig.tight_layout()
    _save_figure(fig, out_path)
    plt.close(fig)


def generate_plots(
    summary_path="results/summary.csv",
    figures_dir="plots",
    *,
    results_dir: str | Path | None = None,
    artifact_store: ArtifactStore | None = None,
):
    global _ARTIFACT_STORE, plt, np
    plt, np = _load_plotting_dependencies()
    _ARTIFACT_STORE = artifact_store
    results = Path(results_dir) if results_dir is not None else Path(summary_path).parent
    rows = _read_csv(summary_path)
    evidence = _read_csv(results / "metric_evidence.csv")
    figures = Path(figures_dir)
    if artifact_store is None:
        figures.mkdir(parents=True, exist_ok=True)
    unsafe_rows = _weighted_metric_rows(evidence, "unsafe_episode_rate")
    _bar(
        unsafe_rows or rows,
        "value" if unsafe_rows else "unsafe_action_rate",
        figures / "unsafe_action_rate.png",
        key="agent" if unsafe_rows else "agent_name",
        title="Unsafe action rate",
        subtitle="Lower is safer: actions that violated the hidden task constraints.",
        ylabel="Unsafe actions",
        color=RED,
    )
    unresolved_rows = _weighted_metric_rows(evidence, "unsafe_or_failed_rate")
    if unresolved_rows or any("unsafe_or_failed_rate" in row for row in rows):
        _bar(
            unresolved_rows or rows,
            "value" if unresolved_rows else "unsafe_or_failed_rate",
            figures / "unsafe_or_failed_rate.png",
            key="agent" if unresolved_rows else "agent_name",
            title="Unsafe or infrastructure-failed rate",
            subtitle="Lower is better: unresolved failures remain in the planned denominator.",
            ylabel="Unsafe or failed episodes",
            color=RED,
        )
    _scatter(_weighted_safety_coverage_rows(evidence) or rows, figures / "coverage_vs_safety.png")
    recovery_rows = _weighted_metric_rows(evidence, "temporal_recovery_rate")
    _bar(
        recovery_rows or rows,
        "value" if recovery_rows else "recovery_rate",
        figures / "recovery_rate.png",
        key="agent" if recovery_rows else "agent_name",
        title="Recovery rate",
        subtitle="Higher means the agent returns to a safe, useful trajectory after a shift.",
        ylabel="Recovered episodes",
        color=TEAL,
    )
    constraint_rows = _weighted_metric_rows(evidence, "constraint_violation_rate")
    _bar(
        constraint_rows or rows,
        "value" if constraint_rows else "constraint_violation_rate",
        figures / "failure_breakdown.png",
        key="agent" if constraint_rows else "agent_name",
        title="Constraint violation rate",
        subtitle="The share of episodes containing at least one constraint breach.",
        ylabel="Violating episodes",
        color=RED,
    )
    unsafe_step_rows = _weighted_metric_rows(evidence, "unsafe_executed_action_rate")
    _bar(
        unsafe_step_rows or rows,
        "value" if unsafe_step_rows else "unsafe_step_rate",
        figures / "unsafe_step_rate.png",
        key="agent" if unsafe_step_rows else "agent_name",
        title="Unsafe step rate",
        subtitle="The fraction of all rollout steps that were unsafe.",
        ylabel="Unsafe steps",
        color=RED,
    )
    clean_shifted = _read_csv(results / "clean_vs_shifted.csv")
    if clean_shifted:
        _bar(
            clean_shifted,
            "safe_success_gap",
            figures / "clean_vs_shifted_gap.png",
            title="Clean vs. shifted safe-success gap",
            subtitle="Positive values mean safe success is lower under executed shift treatments.",
            ylabel="Clean minus shifted safe-success rate",
            color=GOLD,
            percent=False,
        )
    analysis = results.parent / "analysis" if results.name == "results" else results / "analysis"
    thresholds = _read_csv(analysis / "monitor_threshold_sweep.csv")
    if thresholds:
        _bar(
            [r for r in thresholds if r.get("monitor_name") == "ALL"] or thresholds,
            "recall",
            figures / "monitor_threshold_curve.png",
            key="threshold",
            title="Monitor threshold trade-off",
            subtitle="Recall as the risk threshold changes; use with precision/coverage in the report.",
            ylabel="Recall",
            color=TEAL,
        )
        _precision_recall_plot(thresholds, figures / "monitor_precision_recall.png")
    calibration = _read_csv(analysis / "monitor_calibration.csv")
    if calibration:
        _reliability_diagram(calibration, figures / "monitor_reliability_diagram.png")
    profiles = _read_csv(analysis / "agent_safety_profile.csv")
    if profiles:
        _bar(
            profiles,
            "safe_useful_action_rate",
            figures / "agent_safe_useful_rate.png",
            key="agent",
            title="Agent safe-useful action rate",
            subtitle="A raw rate from planned episode evidence; this is not a weighted ranking.",
            ylabel="Safe-useful rate",
            color=BLUE,
        )
    pairwise = _read_csv(analysis / "pairwise_compound_matrix.csv") or _read_csv(analysis / "compound_shift_matrix.csv")
    if pairwise:
        metric = (
            "delta_pair_vs_worst_single_unsafe_action_rate"
            if "delta_pair_vs_worst_single_unsafe_action_rate" in pairwise[0]
            else "delta_vs_worst_single_unsafe_action_rate"
        )
        _bar(
            pairwise,
            metric,
            figures / "pairwise_compound_effect.png",
            key="fault_pair",
            title="Compound-shift effect",
            subtitle="Positive values mean paired faults are worse than the worst single fault.",
            ylabel="Unsafe-rate delta",
            color=RED,
            percent=False,
        )
    clusters = _read_csv(analysis / "failure_clusters.csv")
    if clusters:
        _bar(
            clusters,
            "count",
            figures / "failure_cluster_topn.png",
            key="cluster_id",
            title="Most common failure clusters",
            subtitle="Counts show which failure patterns occur most often.",
            ylabel="Episodes",
            color=GOLD,
            percent=False,
        )
    ci = _read_csv(results / "confidence_intervals.csv")
    if ci:
        _interval_bar(
            [r for r in ci if r.get("metric") == "safe_success_rate"] or ci,
            figures / "confidence_intervals.png",
            title="Scenario-clustered safe-success estimates",
            subtitle="Bars show point estimates; whiskers are deterministic scenario-clustered confidence intervals.",
            ylabel="Safe-success rate",
        )
    else:
        if artifact_store is None:
            (figures / "confidence_intervals.png").unlink(missing_ok=True)
    if artifact_store is not None:
        return [str(path) for path in sorted(artifact_store.run_dir.joinpath(figures).glob("*.png"))]
    return [str(p) for p in sorted(figures.glob("*.png"))]
