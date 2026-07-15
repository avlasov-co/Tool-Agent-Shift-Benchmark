from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path

DEFAULT_TEMPLATE = Path("templates/report.html")


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


def _metric_cards(summary_rows: list[dict[str, str]], failure_rows: list[dict[str, str]]) -> str:
    episodes = sum(float(r.get("episodes", 0) or 0) for r in summary_rows)
    unsafe_values = [float(r.get("unsafe_action_rate", 0) or 0) for r in summary_rows]
    avg_unsafe = sum(unsafe_values) / len(unsafe_values) if unsafe_values else 0.0
    cards = [
        ("Summary rows", len(summary_rows)),
        ("Approx episodes", int(episodes)),
        ("Failure cases", len(failure_rows)),
        ("Mean unsafe rate", f"{avg_unsafe:.3f}"),
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
    output_path: str | Path = "docs/analysis_report.html",
    title: str = "Tool-Agent Shift Benchmark Report",
) -> Path:
    results = Path(results_dir)
    analysis = results / "analysis"
    summary = _read_rows(results / "summary.csv")
    failures = _read_rows(results / "failure_cases.csv")
    profiles = _read_rows(analysis / "agent_safety_profile.csv")
    clusters = _read_rows(analysis / "failure_clusters.csv")
    thresholds = _read_rows(analysis / "monitor_threshold_sweep.csv")
    calibration = _read_rows(analysis / "monitor_calibration.csv")
    pairwise = _read_rows(analysis / "pairwise_compound_matrix.csv") or _read_rows(
        analysis / "compound_shift_matrix.csv"
    )

    sections = [
        f"<h1>{html.escape(title)}</h1>",
        "<p class='muted'>Generated from local benchmark CSV artifacts. No external services, no API calls, "
        "no synthetic magic pretending to be production safety.</p>",
        _metric_cards(summary, failures),
        "<h2>Agent safety profile</h2>",
        _table(
            profiles,
            [
                "agent",
                "episodes",
                "unsafe_action_rate",
                "coverage",
                "safe_useful_action_rate",
                "safety_coverage_score",
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
                "coverage_after_gate",
                "unsafe_rate_after_gate",
            ],
            21,
        ),
        "<h2>Monitor calibration</h2>",
        _table(
            calibration,
            [
                "monitor_name",
                "risk_bucket",
                "events",
                "mean_risk_score",
                "empirical_unsafe_rate",
                "calibration_error_abs",
            ],
            30,
        ),
        "<h2>Compound fault matrix</h2>",
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
            for p in sorted(str(p.relative_to(results)) for p in analysis.glob("*") if p.is_file())
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
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' "
        "content='width=device-width,initial-scale=1'><title>"
        + html.escape(title)
        + "</title><style>"
        + css
        + "</style></head><body><main>"
        + "\n".join(sections)
        + "</main></body></html>\n",
        encoding="utf-8",
    )
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
