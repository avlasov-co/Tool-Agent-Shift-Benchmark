"""Readable, publication-style benchmark figures.

The old renderer intentionally emitted bare pixel bars.  These figures are
research outputs, so labels and annotations are part of the data contract.
"""

from __future__ import annotations

import csv
from pathlib import Path


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
    fig.savefig(out_path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def _scatter(rows, out_path: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=150)
    for row in rows:
        x, y = _number(row.get("coverage")), 1 - _number(row.get("unsafe_action_rate"))
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
        "Each point is one benchmark configuration; higher and farther right is better.",
        "Safe action rate",
    )
    ax.set_xlabel("Coverage: fraction of useful actions completed")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks(np.linspace(0, 1, 6))
    ax.set_xticklabels([f"{v:.0%}" for v in np.linspace(0, 1, 6)])
    fig.tight_layout()
    fig.savefig(out_path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def generate_plots(summary_path="results/summary.csv", figures_dir="figures"):
    global plt, np
    plt, np = _load_plotting_dependencies()
    rows = _read_csv(summary_path)
    figures = Path(figures_dir)
    figures.mkdir(parents=True, exist_ok=True)
    _bar(
        rows,
        "unsafe_action_rate",
        figures / "unsafe_action_rate.png",
        title="Unsafe action rate",
        subtitle="Lower is safer: actions that violated the hidden task constraints.",
        ylabel="Unsafe actions",
        color=RED,
    )
    _scatter(rows, figures / "coverage_vs_safety.png")
    _bar(
        [r for r in rows if r.get("agent_name") == "monitor_gated"] or rows,
        "monitor_recall",
        figures / "monitor_recall_precision.png",
        title="Monitor recall",
        subtitle="Higher means the monitor catches more genuinely unsafe episodes.",
        ylabel="Recall",
        color=TEAL,
    )
    _bar(
        rows,
        "recovery_rate",
        figures / "recovery_rate.png",
        title="Recovery rate",
        subtitle="Higher means the agent returns to a safe, useful trajectory after a shift.",
        ylabel="Recovered episodes",
        color=TEAL,
    )
    _bar(
        rows,
        "constraint_violation_rate",
        figures / "failure_breakdown.png",
        title="Constraint violation rate",
        subtitle="The share of episodes containing at least one constraint breach.",
        ylabel="Violating episodes",
        color=RED,
    )
    _bar(
        rows,
        "unsafe_step_rate",
        figures / "unsafe_step_rate.png",
        title="Unsafe step rate",
        subtitle="The fraction of all rollout steps that were unsafe.",
        ylabel="Unsafe steps",
        color=RED,
    )
    svd = _read_csv("results/static_vs_dynamic.csv")
    if svd:
        _bar(
            svd,
            "gap",
            figures / "static_vs_dynamic_gap.png",
            title="Static vs. dynamic performance gap",
            subtitle="Positive gap means performance changes when the agent must act in a rollout.",
            ylabel="Gap",
            color=GOLD,
            percent=False,
        )
    analysis = Path("results/analysis")
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
    calibration = _read_csv(analysis / "monitor_calibration.csv")
    if calibration:
        _bar(
            calibration,
            "calibration_error_abs",
            figures / "calibration_curve.png",
            key="risk_bucket",
            title="Risk calibration error",
            subtitle="Lower is better: distance between predicted risk and observed unsafe rate.",
            ylabel="Absolute error",
            color=GOLD,
        )
    profiles = _read_csv(analysis / "agent_safety_profile.csv")
    if profiles:
        _bar(
            profiles,
            "safety_coverage_score",
            figures / "agent_safety_profile.png",
            key="agent",
            title="Agent safety–coverage profile",
            subtitle="A combined view of safe behavior and useful task completion.",
            ylabel="Score",
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
            figures / "pairwise_compound_heatmap.png",
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
    ci = _read_csv("results/confidence_intervals.csv")
    if ci:
        _bar(
            [r for r in ci if r.get("metric") == "safe_useful_action_rate"] or ci,
            "mean",
            figures / "confidence_intervals.png",
            key="metric",
            title="Multi-seed estimate",
            subtitle="Mean safe-useful action rate across seeds; see the CSV for interval bounds.",
            ylabel="Mean rate",
            color=BLUE,
        )
    else:
        (figures / "confidence_intervals.png").unlink(missing_ok=True)
    return [str(p) for p in sorted(figures.glob("*.png"))]
