from __future__ import annotations

import argparse
import csv
import html
from collections.abc import Mapping
from pathlib import Path
from string import Template
from typing import Any

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.package_resources import read_builtin_resource
from tool_agent_shift_benchmark.reporting.provenance import (
    build_report_provenance,
    capture_verified_source,
    validate_report_provenance,
)


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _table(rows: list[dict[str, str]], columns: list[str], limit: int = 20) -> str:
    if not rows:
        return "<p class='muted'>No rows available.</p>"
    header = "".join(f"<th>{html.escape(col)}</th>" for col in columns)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in columns) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _metric_cards(provenance: Mapping[str, Any], failure_rows: list[dict[str, str]]) -> str:
    metrics = {row["metric_name"]: row for row in provenance["headline_metrics"]}
    counts = provenance["source_snapshot"]["sample_counts"]
    cards = [
        ("Planned episodes", counts["planned_episodes"]),
        ("Completed episodes", counts["completed_episodes"]),
        ("Failure cases", len(failure_rows)),
        ("Safe-success rate", f"{float(metrics['safe_success_rate']['value'] or 0):.3f}"),
        ("Unsafe-episode rate", f"{float(metrics['unsafe_episode_rate']['value'] or 0):.3f}"),
        ("Useful-action rate", f"{float(metrics['useful_action_rate']['value'] or 0):.3f}"),
    ]
    return (
        "<div class='cards'>"
        + "".join(
            f"<section class='card'><span>{html.escape(k)}</span><strong>{html.escape(str(v))}</strong></section>"
            for k, v in cards
        )
        + "</div>"
    )


def render_html_report(
    results_dir: str | Path = "results",
    output_path: str | Path = "reports/analysis_report.html",
    title: str = "Tool-Agent Shift Benchmark Report",
    *,
    artifact_store: ArtifactStore | None = None,
    source_provenance: Mapping[str, Any] | None = None,
) -> Path:
    results = Path(results_dir)
    analysis = (
        results.parent / "analysis"
        if artifact_store is not None and results.name == "results"
        else results / "analysis"
    )
    failures = _read_rows(results / "failure_cases.csv")
    profiles = _read_rows(analysis / "agent_safety_profile.csv")
    clusters = _read_rows(analysis / "failure_clusters.csv")
    thresholds = _read_rows(analysis / "monitor_threshold_sweep.csv")
    calibration = _read_rows(analysis / "monitor_calibration.csv")
    calibration_summary = _read_rows(analysis / "monitor_calibration_summary.csv")
    gating = _read_rows(analysis / "monitor_gating_outcomes.csv")
    pairwise = _read_rows(analysis / "pairwise_compound_matrix.csv") or _read_rows(
        analysis / "compound_shift_matrix.csv"
    )
    run_dir = artifact_store.run_dir if artifact_store is not None else results.parent
    source = dict(source_provenance or capture_verified_source(run_dir))
    provenance = build_report_provenance(run_dir, source)
    validation = validate_report_provenance(provenance)
    if validation["status"] != "valid":
        raise ValueError(f"report provenance validation failed: {validation['errors']}")
    snapshot = provenance["source_snapshot"]

    sections = [
        f"<h1>{html.escape(title)}</h1>",
        f"<p class='muted'>Complete-valid run <code>{html.escape(str(snapshot['source_run_id']))}</code>; "
        f"metric schema <code>{html.escape(str(snapshot['metric_schema_version']))}</code>; source manifest "
        f"SHA-256 <code>{html.escape(str(snapshot['source_manifest_sha256']))}</code>. Synthetic evidence is not "
        "production certification.</p>",
        _metric_cards(provenance, failures),
        "<h2>Agent raw outcome profile</h2>",
        _table(
            profiles,
            [
                "agent",
                "episodes",
                "completed_episodes",
                "infrastructure_failures",
                "unsafe_action_rate",
                "unsafe_or_failed_rate",
                "coverage",
                "safe_useful_action_rate",
                "clean_shifted_safe_success_gap",
            ],
            20,
        ),
        "<h2>Top failure clusters</h2>",
        _table(
            clusters,
            [
                "cluster_id",
                "count",
                "environment",
                "fault",
                "agent",
                "unsafe_reason_family",
            ],
            20,
        ),
        "<h2>Monitor threshold sweep</h2>",
        _table(
            [r for r in thresholds if r.get("monitor_name") == "ALL"] or thresholds,
            [
                "threshold",
                "precision",
                "recall",
                "false_positive_rate",
                "specificity",
                "predicted_block_rate",
                "coverage_cost",
            ],
            21,
        ),
        "<h2>Realized gating outcomes</h2>",
        _table(
            [row for row in gating if row.get("monitor_name") == "ALL"] or gating,
            [
                "precision",
                "recall",
                "intervention_rate",
                "prevented_harm",
                "unnecessary_blocks",
                "coverage_cost",
                "executed_unsafe_rate",
            ],
            20,
        ),
        "<h2>Monitor reliability bins</h2>",
        _table(
            calibration,
            [
                "monitor_name",
                "bin_lower",
                "bin_upper",
                "events",
                "mean_predicted_probability",
                "empirical_proposed_unsafe_rate",
                "absolute_calibration_error",
            ],
            30,
        ),
        "<h3>Calibration eligibility and scores</h3>",
        _table(
            calibration_summary,
            [
                "monitor_name",
                "status",
                "score_semantics",
                "eligible_events",
                "brier_score",
                "expected_calibration_error",
            ],
            20,
        ),
        "<h2>Compound fault effects</h2>",
        _table(
            pairwise,
            [
                "environment",
                "agent",
                "fault_pair",
                "fault_severity",
                "worst_single_fault",
                "pair_unsafe_action_rate",
                "delta_pair_vs_worst_single_unsafe_action_rate",
            ],
            30,
        ),
        "<h2>Artifacts</h2>",
        "<ul>"
        + "".join(
            f"<li>{html.escape(str(p))}</li>"
            for p in sorted(
                str(p.relative_to(results.parent if artifact_store is not None else results))
                for p in analysis.glob("*")
                if p.is_file()
            )
        )
        + "</ul>",
    ]
    css = (
        "body{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"
        "margin:0;background:#f7f7f8;color:#18181b}main{max-width:1120px;margin:0 auto;padding:40px 24px}"
        "h1{font-size:34px;margin:0 0 10px}h2{margin-top:34px}.muted{color:#5f6368}.cards{display:grid;"
        "grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:24px 0}.card{background:white;"
        "border:1px solid #ddd;border-radius:16px;padding:18px;box-shadow:0 4px 16px rgba(0,0,0,.04)}"
        ".card span{display:block;color:#666;font-size:13px}.card strong{display:block;font-size:25px;margin-top:8px}"
        "table{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden;"
        "border:1px solid #ddd}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid #ececec;font-size:13px}"
        "th{background:#202124;color:white}tr:last-child td{border-bottom:0}ul{background:white;border:1px solid #ddd;"
        "border-radius:14px;padding:20px 34px}code{background:#eee;padding:2px 5px;border-radius:5px}"
    )
    content = ""
    template = Template(read_builtin_resource("templates", "report.html").decode("utf-8"))
    content = template.substitute(title=html.escape(title), css=css, sections="\n".join(sections))
    if artifact_store is not None:
        return artifact_store.write_text(output_path, content)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate HTML analysis report")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default="docs/analysis_report.html")
    args = parser.parse_args(argv)
    path = render_html_report(args.results_dir, args.output)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
