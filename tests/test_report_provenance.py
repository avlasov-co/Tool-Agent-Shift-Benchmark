from __future__ import annotations

from copy import deepcopy

import pytest

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.reporting.provenance import (
    build_report_provenance,
    capture_verified_source,
    validate_report_provenance,
)
from tool_agent_shift_benchmark.run_eval import run_eval


def _verified_run(tmp_path) -> ArtifactStore:
    store = ArtifactStore(tmp_path / "run")
    run_eval("small", 42, artifact_store=store)
    store.finalize(command=["test", "verified-source"])
    return store


def test_report_provenance_links_formula_counts_schema_and_checksums(tmp_path) -> None:
    store = _verified_run(tmp_path)
    source = capture_verified_source(store.run_dir)
    provenance = build_report_provenance(store.run_dir, source)
    validation = validate_report_provenance(provenance)

    assert validation == {"schema_version": "report-provenance-v1", "status": "valid", "errors": []}
    assert source["verification"]["status"] == "complete_valid"
    assert source["source_manifest_sha256"]
    assert source["source_finalization_sha256"]
    assert source["sample_counts"]["planned_episodes"] == 28
    assert "passed" in source["clean_competence"]
    assert source["supported_treatments"]["oversight_modes"] == ["record_only"]
    for metric in provenance["headline_metrics"]:
        assert metric["metric_schema_version"] == "metric-schema-v2"
        assert metric["formula"]
        assert metric["denominator"] >= metric["numerator"]
        assert metric["source_artifact_sha256"]
    assert provenance["uncertainty"]["claim_status"] == "not_estimated_for_this_run"


def test_report_provenance_refuses_incomplete_and_malformed_claim_context(tmp_path) -> None:
    incomplete = ArtifactStore(tmp_path / "incomplete")
    with pytest.raises(ValueError, match="complete-valid"):
        capture_verified_source(incomplete.run_dir)

    store = _verified_run(tmp_path)
    provenance = build_report_provenance(store.run_dir, capture_verified_source(store.run_dir))

    missing_competence = deepcopy(provenance)
    missing_competence["source_snapshot"]["clean_competence"] = {}
    assert "clean competence disclosure is missing" in validate_report_provenance(missing_competence)["errors"]

    pending = deepcopy(provenance)
    pending["source_snapshot"]["sample_counts"]["pending_episodes"] = 1
    assert "source run has pending or invalid episodes" in validate_report_provenance(pending)["errors"]

    unsupported = deepcopy(provenance)
    unsupported["source_snapshot"]["supported_treatments"]["oversight_modes"] = []
    assert "executed treatment disclosure is missing" in validate_report_provenance(unsupported)["errors"]

    missing_method = deepcopy(provenance)
    missing_method["uncertainty"] = {"claim_status": "available", "methods": []}
    assert "available uncertainty lacks an interval method" in validate_report_provenance(missing_method)["errors"]


def test_report_provenance_records_available_interval_method_and_status(tmp_path) -> None:
    store = _verified_run(tmp_path)
    store.write_csv(
        "results/confidence_intervals.csv",
        [
            {
                "metric": "safe_success_rate",
                "interval_method": "deterministic_stratified_scenario_cluster_bootstrap_percentile",
                "status": "ok",
                "independent_scenario_count": 2,
                "analysis_seed": 91,
            }
        ],
    )
    store.finalize(command=["test", "verified-source-with-interval"])
    provenance = build_report_provenance(store.run_dir, capture_verified_source(store.run_dir))

    assert provenance["uncertainty"]["claim_status"] == "available"
    assert provenance["uncertainty"]["methods"] == ["deterministic_stratified_scenario_cluster_bootstrap_percentile"]
    assert provenance["uncertainty"]["statuses"] == {"ok": 1}
    assert validate_report_provenance(provenance)["status"] == "valid"
