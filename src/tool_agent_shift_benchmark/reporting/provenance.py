"""Verified, self-contained source snapshots for evidence-bearing reports."""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from tool_agent_shift_benchmark.core.serialization import canonical_loads
from tool_agent_shift_benchmark.core.verification import COMPLETE_VALID, verify_run

REPORT_PROVENANCE_SCHEMA_VERSION = "report-provenance-v1"
HEADLINE_METRICS = (
    "safe_success_rate",
    "unsafe_episode_rate",
    "useful_action_rate",
    "unsafe_proposed_action_rate",
    "temporal_recovery_rate",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = canonical_loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def capture_verified_source(run_dir: str | Path) -> dict[str, Any]:
    """Capture the complete-valid pre-report manifest so later writes cannot invalidate provenance."""

    root = Path(run_dir)
    verification = verify_run(root)
    if verification.get("status") != COMPLETE_VALID:
        raise ValueError(f"reports require a complete-valid source bundle: {verification.get('status')}")
    manifest_path = root / "run_manifest.json"
    finalization_path = root / "finalization.json"
    manifest = _json(manifest_path)
    finalization = _json(finalization_path)
    results_config = _json(root / "results" / "config.json")
    normalized = _json(root / "config" / "normalized_config.json")
    status = _json(root / "status.json")
    semantic = (manifest.get("normalized_semantic_identity") or {}) if isinstance(manifest, Mapping) else {}
    return {
        "schema_version": REPORT_PROVENANCE_SCHEMA_VERSION,
        "verification": verification,
        "source_run_id": manifest.get("run_id"),
        "source_manifest_path": "run_manifest.json",
        "source_manifest_sha256": _sha256(manifest_path),
        "source_finalization_path": "finalization.json",
        "source_finalization_sha256": _sha256(finalization_path),
        "source_manifest": manifest,
        "source_finalization": finalization,
        "metric_schema_version": manifest.get("metric_schema_version"),
        "monitor_evaluation_schema_version": manifest.get("monitor_evaluation_schema_version"),
        "status": status,
        "clean_competence": results_config.get(
            "competence_gate", {"passed": False, "failed_gates": ["competence_metadata_missing"]}
        ),
        "supported_treatments": {
            "monitor_modes": semantic.get("monitor_modes", normalized.get("monitor_modes", [])),
            "oversight_modes": semantic.get("oversight_modes", normalized.get("oversight_modes", [])),
            "faults": normalized.get("faults", []),
            "severities": normalized.get("fault_severities", []),
        },
        "sample_counts": {
            name: status.get(name)
            for name in (
                "planned_episodes",
                "started_episodes",
                "completed_episodes",
                "failed_episodes",
                "skipped_episodes",
                "pending_episodes",
                "invalid_episodes",
            )
        },
    }


def _headline_metrics(run_dir: Path, source: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _csv(run_dir / "results" / "metric_evidence.csv")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("metric_name") in HEADLINE_METRICS:
            grouped[str(row["metric_name"])].append(row)
    source_manifest = source.get("source_manifest", {})
    checksums = source_manifest.get("checksums", {}) if isinstance(source_manifest, Mapping) else {}
    output: list[dict[str, Any]] = []
    for metric in HEADLINE_METRICS:
        metric_rows = grouped.get(metric, [])
        formulas = {row.get("formula", "") for row in metric_rows}
        units = {row.get("unit", "") for row in metric_rows}
        if len(formulas) > 1 or len(units) > 1:
            raise ValueError(f"headline metric has inconsistent formula or unit: {metric}")
        numerator = sum(int(float(row.get("numerator", 0) or 0)) for row in metric_rows)
        denominator = sum(int(float(row.get("denominator", 0) or 0)) for row in metric_rows)
        output.append(
            {
                "metric_name": metric,
                "metric_schema_version": source.get("metric_schema_version"),
                "numerator": numerator,
                "denominator": denominator,
                "value": numerator / denominator if denominator else None,
                "unit": next(iter(units), ""),
                "formula": next(iter(formulas), ""),
                "status": "ok" if denominator else "no_eligible_units",
                "source_artifact": "results/metric_evidence.csv",
                "source_artifact_sha256": checksums.get("results/metric_evidence.csv"),
            }
        )
    return output


def build_report_provenance(run_dir: str | Path, source: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(run_dir)
    confidence = _csv(root / "results" / "confidence_intervals.csv")
    interval_methods = sorted({row.get("interval_method", "") for row in confidence if row.get("interval_method")})
    interval_statuses: dict[str, int] = defaultdict(int)
    for row in confidence:
        interval_statuses[str(row.get("status", "unknown"))] += 1
    return {
        "schema_version": REPORT_PROVENANCE_SCHEMA_VERSION,
        "source_snapshot": dict(source),
        "headline_metrics": _headline_metrics(root, source),
        "uncertainty": {
            "artifact": "results/confidence_intervals.csv" if confidence else None,
            "artifact_sha256": source.get("source_manifest", {})
            .get("checksums", {})
            .get("results/confidence_intervals.csv"),
            "row_count": len(confidence),
            "methods": interval_methods,
            "statuses": dict(sorted(interval_statuses.items())),
            "claim_status": "available" if confidence else "not_estimated_for_this_run",
        },
    }


def validate_report_provenance(provenance: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    source = provenance.get("source_snapshot")
    if provenance.get("schema_version") != REPORT_PROVENANCE_SCHEMA_VERSION or not isinstance(source, Mapping):
        errors.append("invalid report provenance schema")
        source = {}
    verification = source.get("verification", {}) if isinstance(source, Mapping) else {}
    if not isinstance(verification, Mapping) or verification.get("status") != COMPLETE_VALID:
        errors.append("source bundle was not complete-valid")
    if not source.get("source_manifest_sha256") or not source.get("source_finalization_sha256"):
        errors.append("source manifest/finalization checksums are missing")
    if source.get("metric_schema_version") in {None, "", "unknown"}:
        errors.append("metric schema version is missing")
    competence = source.get("clean_competence")
    if not isinstance(competence, Mapping) or "passed" not in competence or "failed_gates" not in competence:
        errors.append("clean competence disclosure is missing")
    counts = source.get("sample_counts")
    if not isinstance(counts, Mapping) or counts.get("planned_episodes") is None:
        errors.append("planned/completed sample counts are missing")
    elif int(counts.get("pending_episodes", 0) or 0) or int(counts.get("invalid_episodes", 0) or 0):
        errors.append("source run has pending or invalid episodes")
    treatments = source.get("supported_treatments")
    if not isinstance(treatments, Mapping) or not treatments.get("oversight_modes"):
        errors.append("executed treatment disclosure is missing")
    metrics = provenance.get("headline_metrics")
    if not isinstance(metrics, list) or not metrics:
        errors.append("headline metric evidence is missing")
    else:
        for metric in metrics:
            if not isinstance(metric, Mapping):
                errors.append("invalid headline metric record")
                continue
            required = ("metric_schema_version", "formula", "numerator", "denominator", "source_artifact_sha256")
            if any(metric.get(name) in {None, ""} for name in required):
                errors.append(f"incomplete headline metric provenance: {metric.get('metric_name', 'unknown')}")
    uncertainty = provenance.get("uncertainty")
    if not isinstance(uncertainty, Mapping) or "claim_status" not in uncertainty:
        errors.append("uncertainty disclosure is missing")
    elif uncertainty.get("claim_status") == "available" and not uncertainty.get("methods"):
        errors.append("available uncertainty lacks an interval method")
    return {
        "schema_version": REPORT_PROVENANCE_SCHEMA_VERSION,
        "status": "valid" if not errors else "invalid",
        "errors": errors,
    }
