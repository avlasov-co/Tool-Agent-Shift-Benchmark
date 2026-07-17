from __future__ import annotations

import pytest

from tool_agent_shift_benchmark.metrics.confidence import confidence_intervals
from tool_agent_shift_benchmark.metrics.statistics import (
    AnalysisConfig,
    adjust_p_values,
    paired_scenario_bootstrap,
    plan_paired_sample_size,
    scenario_cluster_bootstrap,
    wilson_binomial_interval,
)

CONFIG = AnalysisConfig(analysis_seed=1234, resamples=500)


def _row(
    scenario: str,
    value: float,
    *,
    condition: str = "shifted",
    family: str = "family_a",
    seed: int = 1,
) -> dict[str, object]:
    return {
        "scenario_manifest_hash": scenario,
        "scenario_family": family,
        "root_seed": seed,
        "condition": condition,
        "value": value,
    }


def test_paired_bootstrap_recovers_known_null_and_positive_effects() -> None:
    null_rows = []
    positive_rows = []
    for index in range(20):
        scenario = f"scenario_{index}"
        baseline = float(index % 2)
        null_rows.extend(
            [
                _row(scenario, baseline, condition="clean", seed=index),
                _row(scenario, baseline, condition="shifted", seed=index),
            ]
        )
        positive_rows.extend(
            [
                _row(scenario, 0.0, condition="clean", seed=index),
                _row(scenario, 1.0, condition="shifted", seed=index),
            ]
        )

    null = paired_scenario_bootstrap(null_rows, value_key="value", config=CONFIG)
    positive = paired_scenario_bootstrap(positive_rows, value_key="value", config=CONFIG)

    assert null.status == "ok"
    assert null.effect_size == null.interval_low == null.interval_high == 0.0
    assert positive.status == "ok"
    assert positive.effect_size == positive.interval_low == positive.interval_high == 1.0
    assert positive.independent_scenario_count == 20
    assert positive.seed_count == 20
    assert positive.condition_count == 2


def test_clustered_and_highly_unbalanced_rows_get_equal_scenario_weight() -> None:
    rows = [_row("large_cluster", 1.0) for _ in range(100)]
    rows.append(_row("small_cluster", 0.0))

    estimate = scenario_cluster_bootstrap(rows, value_key="value", config=CONFIG)

    assert estimate.status == "ok"
    assert estimate.effect_size == 0.5
    assert estimate.independent_scenario_count == 2
    assert estimate.effect_size != pytest.approx(100 / 101)


def test_missing_pairs_are_visible_and_never_imputed_as_zero() -> None:
    rows = [
        _row("paired_a", 0.0, condition="clean"),
        _row("paired_a", 1.0, condition="shifted"),
        _row("paired_b", 0.0, condition="clean"),
        _row("paired_b", 1.0, condition="shifted"),
        _row("missing_clean", 1.0, condition="shifted"),
    ]

    estimate = paired_scenario_bootstrap(rows, value_key="value", config=CONFIG)

    assert estimate.status == "ok"
    assert estimate.effect_size == 1.0
    assert estimate.independent_scenario_count == 2
    assert estimate.missing_pair_count == 1


def test_insufficient_independent_units_refuse_numeric_interval() -> None:
    estimate = scenario_cluster_bootstrap([_row("only_scenario", 1.0)], value_key="value", config=CONFIG)

    assert estimate.status == "insufficient_independent_units"
    assert estimate.effect_size == 1.0
    assert estimate.interval_low is None and estimate.interval_high is None


def test_bootstrap_is_deterministic_and_records_exact_analysis_configuration() -> None:
    rows = [_row(f"scenario_{index}", float(index % 3 == 0), seed=index) for index in range(12)]

    first = scenario_cluster_bootstrap(rows, value_key="value", config=CONFIG)
    second = scenario_cluster_bootstrap(list(reversed(rows)), value_key="value", config=CONFIG)

    assert first.to_dict() == second.to_dict()
    assert first.analysis_seed == 1234
    assert first.resamples == 500
    assert first.interval_method.startswith("deterministic_stratified_scenario")


def test_binomial_interval_requires_independent_binary_units() -> None:
    with pytest.raises(ValueError, match="genuinely independent"):
        wilson_binomial_interval(5, 10, independent_binary_units=False)

    low, high = wilson_binomial_interval(5, 10, independent_binary_units=True)
    assert 0.0 < low < 0.5 < high < 1.0


def test_multiple_comparison_corrections_are_optional_and_monotone() -> None:
    values = [0.01, 0.04, 0.03]
    assert adjust_p_values(values, "none") == values
    assert adjust_p_values(values, "bonferroni") == pytest.approx([0.03, 0.12, 0.09])
    assert adjust_p_values(values, "holm") == pytest.approx([0.03, 0.06, 0.06])
    assert adjust_p_values(values, "benjamini_hochberg") == pytest.approx([0.03, 0.04, 0.04])


def test_power_planning_reports_required_independent_scenarios() -> None:
    plan = plan_paired_sample_size(0.2, 0.5, alpha=0.05, target_power=0.8)
    assert plan.status == "ok"
    assert plan.required_independent_scenarios is not None
    assert plan.required_independent_scenarios >= 2

    zero = plan_paired_sample_size(0.0, 0.5)
    assert zero.status == "undefined_zero_effect"
    assert zero.required_independent_scenarios is None


def test_confidence_table_reports_hierarchy_counts_instead_of_seed_row_n() -> None:
    rows = []
    for index in range(4):
        rows.append(
            {
                "environment": "file_ops",
                "agent": "agent",
                "fault": "normal",
                "severity": "0.0",
                "monitor_mode": "full",
                "oversight_mode": "record_only",
                "scenario_manifest_hash": f"scenario_{index}",
                "scenario_family": "file_family",
                "root_seed": index,
                "safe_success": index % 2 == 0,
                "unsafe_outcome": False,
                "constraint_violation": False,
                "stale_data_action": False,
                "temporal_recovery": False,
                "temporal_recovery_eligible": False,
                "schema_recovery": False,
                "schema_recovery_eligible": False,
            }
        )

    table = confidence_intervals(rows, config=CONFIG)
    safe = next(row for row in table if row["metric"] == "safe_success_rate")
    recovery = next(row for row in table if row["metric"] == "temporal_recovery_rate")
    assert safe["effect_size"] == 0.5
    assert safe["independent_scenario_count"] == 4
    assert safe["seed_count"] == 4
    assert safe["analysis_seed"] == 1234
    assert recovery["status"] == "no_eligible_units"
