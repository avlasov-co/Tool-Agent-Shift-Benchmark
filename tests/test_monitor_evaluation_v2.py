from __future__ import annotations

import pytest

from tool_agent_shift_benchmark.metrics.monitor_evaluation import (
    MonitorUtilityConfig,
    apply_monitor_utility,
    build_monitor_calibration,
    build_monitor_detection_table,
    build_monitor_gating_table,
)
from tool_agent_shift_benchmark.metrics.statistics import AnalysisConfig

CONFIG = AnalysisConfig(analysis_seed=91, resamples=300)


def _event(
    scenario: str,
    *,
    risk: float,
    proposed_unsafe: bool,
    predicted_unsafe: bool,
    intervened: bool,
    blocked: bool,
    executed_unsafe: bool,
    score_semantics: str = "ordinal_risk_score",
    realized_unsafe: bool | None = None,
) -> dict[str, object]:
    return {
        "episode_id": f"episode_{scenario}",
        "scenario_manifest_hash": scenario,
        "scenario_family": "fixture_family",
        "root_seed": scenario.rsplit("_", 1)[-1],
        "monitor_name": "fixture_monitor",
        "environment": "file_ops",
        "fault": "stale_observation",
        "severity": "1.0",
        "agent": "fixture_agent",
        "oversight_mode": "hard_gate",
        "monitor_mode": "fixture_mode",
        "risk_score": risk,
        "score_semantics": score_semantics,
        "score_calibration_contract": "probability-score-v1" if score_semantics == "probability" else "",
        "monitor_evaluated": True,
        "monitor_predicted_unsafe": predicted_unsafe,
        "allow_action": not predicted_unsafe,
        "proposed_action_unsafe": proposed_unsafe,
        "proposed_action_success": not proposed_unsafe,
        "executed_action_unsafe": executed_unsafe,
        # Realized safety is intentionally allowed to disagree. It must never
        # become the detector label.
        "realized_unsafe": (not proposed_unsafe) if realized_unsafe is None else realized_unsafe,
        "intervened": intervened,
        "blocked": blocked,
        "intervention_type": "block_to_abstain" if blocked else "allowed",
    }


def _confusion_fixture(*, probability: bool = False) -> list[dict[str, object]]:
    semantics = "probability" if probability else "ordinal_risk_score"
    return [
        _event(
            "scenario_1",
            risk=0.9,
            proposed_unsafe=True,
            predicted_unsafe=True,
            intervened=True,
            blocked=True,
            executed_unsafe=False,
            score_semantics=semantics,
        ),
        _event(
            "scenario_2",
            risk=0.8,
            proposed_unsafe=False,
            predicted_unsafe=True,
            intervened=True,
            blocked=True,
            executed_unsafe=False,
            score_semantics=semantics,
        ),
        _event(
            "scenario_3",
            risk=0.1,
            proposed_unsafe=False,
            predicted_unsafe=False,
            intervened=False,
            blocked=False,
            executed_unsafe=False,
            score_semantics=semantics,
        ),
        _event(
            "scenario_4",
            risk=0.2,
            proposed_unsafe=True,
            predicted_unsafe=False,
            intervened=False,
            blocked=False,
            executed_unsafe=True,
            score_semantics=semantics,
        ),
    ]


def test_counterfactual_confusion_matrix_and_cluster_intervals() -> None:
    rows = build_monitor_detection_table(_confusion_fixture(), thresholds=(0.5,), analysis_config=CONFIG)
    aggregate = next(row for row in rows if row["monitor_name"] == "ALL")

    assert (
        aggregate["true_positives"],
        aggregate["false_positives"],
        aggregate["true_negatives"],
        aggregate["false_negatives"],
    ) == (1, 1, 1, 1)
    assert aggregate["precision"] == aggregate["recall"] == 0.5
    assert aggregate["specificity"] == aggregate["false_positive_rate"] == 0.5
    assert aggregate["false_negative_rate"] == 0.5
    assert aggregate["recall_interval_status"] == "ok"
    assert aggregate["recall_interval_low"] is not None
    assert aggregate["recall_independent_scenario_count"] == 2
    assert aggregate["label_source"] == "counterfactual_proposed_action_unsafe"


def test_realized_gating_separates_prevented_harm_and_unnecessary_safe_block() -> None:
    rows = build_monitor_gating_table(_confusion_fixture(), analysis_config=CONFIG)
    aggregate = next(row for row in rows if row["monitor_name"] == "ALL")

    assert aggregate["intervention_count"] == 2
    assert aggregate["intervention_rate"] == 0.5
    assert aggregate["prevented_harm"] == 1
    assert aggregate["prevented_harm_denominator"] == 2
    assert aggregate["unnecessary_blocks"] == 1
    assert aggregate["unnecessary_blocks_denominator"] == 2
    assert aggregate["coverage_cost"] == 0.5
    assert aggregate["executed_unsafe_rate"] == 0.25
    assert aggregate["intervention_rate_interval_status"] == "ok"
    assert aggregate["executed_unsafe_rate_interval_status"] == "ok"
    assert aggregate["realized_execution_fields_used_only_for_gating"] is True


def test_interval_refuses_one_independent_scenario() -> None:
    event = _confusion_fixture()[0]
    rows = build_monitor_detection_table([event], thresholds=(0.5,), analysis_config=CONFIG)
    aggregate = next(row for row in rows if row["monitor_name"] == "ALL")

    assert aggregate["recall_interval_status"] == "insufficient_independent_units"
    assert aggregate["recall_interval_low"] is None
    assert aggregate["recall_interval_high"] is None


def test_calibration_refuses_ordinal_scores_and_scores_declared_probabilities() -> None:
    bins, summaries = build_monitor_calibration(_confusion_fixture(), analysis_config=CONFIG)
    aggregate = next(row for row in summaries if row["monitor_name"] == "ALL")
    assert bins == []
    assert aggregate["status"] == "ineligible_non_probabilistic_score"
    assert aggregate["brier_score"] is None

    probability_rows = _confusion_fixture(probability=True)
    missing_contract = [dict(row, score_calibration_contract="") for row in probability_rows]
    bins, summaries = build_monitor_calibration(missing_contract, analysis_config=CONFIG)
    assert bins == []
    assert next(row for row in summaries if row["monitor_name"] == "ALL")["status"] == (
        "ineligible_non_probabilistic_score"
    )

    bins, summaries = build_monitor_calibration(probability_rows, analysis_config=CONFIG)
    aggregate = next(row for row in summaries if row["monitor_name"] == "ALL")
    assert bins
    assert sum(row["events"] for row in bins if row["monitor_name"] == "ALL") == 4
    assert aggregate["status"] == "ok"
    assert aggregate["brier_score"] == pytest.approx(0.325)
    assert aggregate["expected_calibration_error"] == pytest.approx(0.45)
    assert aggregate["brier_interval_status"] == "ok"


def test_utility_components_are_configurable_and_pareto_is_explicit() -> None:
    detection = build_monitor_detection_table(_confusion_fixture(), thresholds=(0.0, 0.5, 1.0), analysis_config=CONFIG)
    utility = MonitorUtilityConfig(
        prevented_harm_benefit=10.0,
        missed_harm_cost=7.0,
        unnecessary_block_cost=2.0,
        coverage_loss_cost=1.0,
        intervention_cost=0.5,
    )
    rows = apply_monitor_utility(detection, utility=utility)
    aggregate = [row for row in rows if row["monitor_name"] == "ALL"]
    middle = next(row for row in aggregate if row["threshold"] == 0.5)

    assert middle["utility_prevented_harm_component"] == 10.0
    assert middle["utility_missed_harm_component"] == -7.0
    assert middle["utility_unnecessary_block_component"] == -2.0
    assert middle["utility_coverage_loss_component"] == -2.0
    assert middle["utility_intervention_component"] == -1.0
    assert middle["utility_total"] == -2.0
    assert any(row["pareto_optimal"] for row in aggregate)


def test_missing_counterfactual_label_is_ineligible_not_assumed_safe() -> None:
    row = _confusion_fixture()[0]
    row.pop("proposed_action_unsafe")
    row["proposed_action_risk_label"] = "unavailable"
    detection = build_monitor_detection_table([row], thresholds=(0.5,), analysis_config=CONFIG)
    aggregate = next(item for item in detection if item["monitor_name"] == "ALL")
    assert aggregate["eligible_events"] == 0
    assert aggregate["ineligible_events"] == 1
    assert aggregate["precision"] is None
