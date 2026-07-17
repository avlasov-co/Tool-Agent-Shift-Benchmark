"""High-level interval tables built from independent scenario units."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from tool_agent_shift_benchmark.metrics.statistics import (
    AnalysisConfig,
    paired_scenario_bootstrap,
    scenario_cluster_bootstrap,
)

DEFAULT_GROUP_KEYS = (
    "environment",
    "agent",
    "fault",
    "severity",
    "monitor_mode",
    "oversight_mode",
)

EPISODE_METRICS: dict[str, tuple[str, str | None]] = {
    "safe_success_rate": ("safe_success", None),
    "unsafe_episode_rate": ("unsafe_outcome", None),
    "constraint_violation_rate": ("constraint_violation", None),
    "stale_data_action_rate": ("stale_data_action", None),
    "temporal_recovery_rate": ("temporal_recovery", "temporal_recovery_eligible"),
    "schema_recovery_rate": ("schema_recovery", "schema_recovery_eligible"),
}


def _truth(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _interval_row(metric: str, estimate, base: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(base),
        "metric": metric,
        **estimate.to_dict(),
        "mean": estimate.effect_size,
        "ci95_low": estimate.interval_low,
        "ci95_high": estimate.interval_high,
        "n": estimate.independent_scenario_count,
    }


def confidence_intervals(
    rows: Iterable[Mapping[str, object]],
    group_keys: tuple[str, ...] = DEFAULT_GROUP_KEYS,
    metrics: Mapping[str, tuple[str, str | None]] = EPISODE_METRICS,
    *,
    config: AnalysisConfig = AnalysisConfig(),
) -> list[dict[str, Any]]:
    """Estimate absolute rates after reducing repeated rows to scenarios."""

    groups: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        key = tuple(str(row.get(name, "")) for name in group_keys)
        groups[key].append(row)
    output: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        base = dict(zip(group_keys, key, strict=True))
        for metric, (value_key, eligibility_key) in metrics.items():
            eligible = [item for item in items if eligibility_key is None or _truth(item.get(eligibility_key))]
            estimate = scenario_cluster_bootstrap(eligible, value_key=value_key, config=config)
            output.append(_interval_row(metric, estimate, base))
    return output


def paired_effect_intervals(
    rows: Iterable[Mapping[str, object]],
    *,
    metrics: Mapping[str, tuple[str, str | None]] = EPISODE_METRICS,
    config: AnalysisConfig = AnalysisConfig(),
) -> list[dict[str, Any]]:
    """Estimate shifted-minus-clean effects within authoritative scenario pairs."""

    all_rows = list(rows)
    match_fields = (
        "scenario_manifest_hash",
        "root_seed",
        "environment",
        "agent",
        "monitor_mode",
        "oversight_mode",
    )
    clean_index: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in all_rows:
        if str(row.get("fault")) == "normal":
            clean_index[tuple(str(row.get(name, "")) for name in match_fields)].append(row)
    treatment_groups: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    group_fields = ("environment", "agent", "fault", "severity", "monitor_mode", "oversight_mode")
    for row in all_rows:
        if str(row.get("fault")) != "normal":
            treatment_groups[tuple(str(row.get(name, "")) for name in group_fields)].append(row)
    output: list[dict[str, Any]] = []
    for group_key, shifted_rows in sorted(treatment_groups.items()):
        base = dict(zip(group_fields, group_key, strict=True))
        for metric, (value_key, eligibility_key) in metrics.items():
            paired_rows: list[dict[str, object]] = []
            for shifted in shifted_rows:
                if eligibility_key is not None and not _truth(shifted.get(eligibility_key)):
                    continue
                shifted_value = dict(shifted)
                shifted_value["condition"] = "shifted"
                paired_rows.append(shifted_value)
                match_key = tuple(str(shifted.get(name, "")) for name in match_fields)
                for clean in clean_index.get(match_key, ()):
                    if eligibility_key is not None and not _truth(clean.get(eligibility_key)):
                        continue
                    clean_value = dict(clean)
                    clean_value["condition"] = "clean"
                    paired_rows.append(clean_value)
            estimate = paired_scenario_bootstrap(paired_rows, value_key=value_key, config=config)
            output.append(_interval_row(metric, estimate, base))
    return output
