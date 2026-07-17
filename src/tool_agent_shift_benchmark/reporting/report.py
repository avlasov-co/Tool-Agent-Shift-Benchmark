"""Evidence-backed Markdown reporting from complete-valid run bundles."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.serialization import canonical_loads
from tool_agent_shift_benchmark.metrics.aggregation import aggregate
from tool_agent_shift_benchmark.reporting.provenance import (
    build_report_provenance,
    capture_verified_source,
    validate_report_provenance,
)


def _rows(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists() and path.name == "summary.csv":
        structured = path.parent / "episodes.jsonl"
        if structured.exists():
            episodes = [
                Episode.from_dict(canonical_loads(line))
                for line in structured.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            errors_path = path.parent / "orchestration_errors.jsonl"
            errors = []
            if errors_path.exists():
                errors = [
                    canonical_loads(line)
                    for line in errors_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                errors = [value for value in errors if "planned_episode" in value]
            return aggregate(episodes, errors)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _format_rate(value: object) -> str:
    return "not estimable" if value is None else f"{float(value):.3f}"


def generate_markdown_report(
    summary_path: str | Path = "results/summary.csv",
    out_path: str | Path = "reports/experimental_report.md",
    *,
    artifact_store: ArtifactStore | None = None,
    source_provenance: Mapping[str, Any] | None = None,
) -> str:
    results_dir = Path(summary_path).parent
    run_dir = artifact_store.run_dir if artifact_store is not None else results_dir.parent
    source = dict(source_provenance or capture_verified_source(run_dir))
    provenance = build_report_provenance(run_dir, source)
    validation = validate_report_provenance(provenance)
    if validation["status"] != "valid":
        raise ValueError(f"report provenance validation failed: {validation['errors']}")
    rows = _rows(summary_path)
    failures = _rows(results_dir / "failure_cases.csv")
    clean_shifted = _rows(results_dir / "clean_vs_shifted.csv")
    snapshot = provenance["source_snapshot"]
    counts = snapshot["sample_counts"]
    competence = snapshot["clean_competence"]
    treatments = snapshot["supported_treatments"]
    uncertainty = provenance["uncertainty"]
    lines = [
        "# Experimental Report",
        "",
        "This report is generated only from a `complete_valid` run bundle. Its immutable pre-report source manifest "
        "is embedded in `reports/source_evidence_snapshot.json`; the final run manifest checksums this report and "
        "that snapshot.",
        "",
        "## Verified source",
        "",
        f"- Run ID: `{snapshot['source_run_id']}`",
        f"- Verification: `{snapshot['verification']['status']}`",
        f"- Source run manifest SHA-256: `{snapshot['source_manifest_sha256']}`",
        f"- Source finalization SHA-256: `{snapshot['source_finalization_sha256']}`",
        f"- Metric schema: `{snapshot['metric_schema_version']}`",
        f"- Planned / completed / failed: {counts['planned_episodes']} / {counts['completed_episodes']} / "
        f"{counts['failed_episodes']}",
        f"- Clean competence passed: `{competence['passed']}`",
        f"- Failed competence gates: `{'; '.join(competence.get('failed_gates', [])) or 'none'}`",
        f"- Executed monitor modes: `{'; '.join(str(value) for value in treatments['monitor_modes'])}`",
        f"- Executed oversight modes: `{'; '.join(str(value) for value in treatments['oversight_modes'])}`",
        "",
        "## Headline metric evidence",
        "",
        "These are sums of disjoint numerator/denominator records, never unweighted means of summary rows.",
        "",
        "| metric | numerator | denominator | value | formula | source checksum |",
        "|---|---:|---:|---:|---|---|",
    ]
    for metric in provenance["headline_metrics"]:
        lines.append(
            f"| {metric['metric_name']} | {metric['numerator']} | {metric['denominator']} | "
            f"{_format_rate(metric['value'])} | {metric['formula']} | `{metric['source_artifact_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Uncertainty",
            "",
            f"- Status: `{uncertainty['claim_status']}`",
            f"- Interval rows: {uncertainty['row_count']}",
            f"- Methods: `{'; '.join(uncertainty['methods']) or 'none'}`",
            f"- Sufficiency statuses: `{uncertainty['statuses']}`",
            "",
            "No uncertainty is implied when this section says `not_estimated_for_this_run`.",
            "",
            "## Condition rows",
            "",
            "The following rows are descriptive cells, not a best-agent ranking.",
            "",
            "| environment | agent | fault | severity | planned | unsafe/failed | useful coverage |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in rows[:12]:
        lines.append(
            f"| {row.get('environment', row.get('env_name', ''))} | {row.get('agent', row.get('agent_name', ''))} "
            f"| {row.get('fault', row.get('fault_name', ''))} | {float(row.get('fault_severity', 0) or 0):.2f} "
            f"| {float(row.get('planned_episodes', 0) or 0):.0f} | "
            f"{float(row.get('unsafe_or_failed_rate', 0) or 0):.3f} | "
            f"{float(row.get('coverage', 0) or 0):.3f} |"
        )
    lines.extend(["", "## Clean versus shifted safe success", ""])
    if clean_shifted:
        for row in clean_shifted:
            lines.append(
                f"- {row.get('agent_name')}: clean={float(row.get('clean_safe_success_rate', 0) or 0):.3f}, "
                f"shifted={float(row.get('shifted_safe_success_rate', 0) or 0):.3f}, "
                f"clean-minus-shifted={float(row.get('safe_success_gap', 0) or 0):.3f}; "
                f"n={row.get('clean_episodes')}/{row.get('shifted_episodes')}."
            )
    else:
        lines.append("No clean-versus-shifted artifact was available.")
    lines.extend(["", "## Representative unsafe executed cases", ""])
    if failures:
        for row in failures[:5]:
            lines.append(
                f"- `{row.get('case_id')}`: {row.get('env_name')} / {row.get('agent_name')} / "
                f"{row.get('fault_name')} -> {row.get('unsafe_reasons')}"
            )
    else:
        lines.append("No unsafe executed cases were recorded.")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "The benchmark uses synthetic environments and transparent reference policies. It does not certify "
            "production systems or frontier-model safety. A passed clean competence gate only supports the declared "
            "suite thresholds. Monitor threshold sweeps are detector analyses, not evidence that unexecuted gating "
            "treatments occurred. Challenge outcomes are excluded from tuning claims.",
        ]
    )
    content = "\n".join(lines) + "\n"
    if artifact_store is not None:
        artifact_store.write_json("reports/source_evidence_snapshot.json", source)
        artifact_store.write_json("reports/report_provenance.json", provenance)
        artifact_store.write_json("reports/report_validation.json", validation)
        return str(artifact_store.write_text(out_path, content))
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return str(output)
