"""Deterministic scenario-clustered statistical inference."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist, mean
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass

STATISTICAL_ANALYSIS_SCHEMA_VERSION = "statistical-analysis-v1"
SCENARIO_BOOTSTRAP_METHOD = "deterministic_stratified_scenario_cluster_bootstrap_percentile"
PAIRED_BOOTSTRAP_METHOD = "deterministic_paired_scenario_cluster_bootstrap_percentile"


@dataclass(frozen=True)
class AnalysisConfig:
    schema_version: str = STATISTICAL_ANALYSIS_SCHEMA_VERSION
    analysis_seed: int = 20260717
    confidence_level: float = 0.95
    resamples: int = 2000
    independent_unit: str = "unique_scenario_manifest"
    cluster_hierarchy: tuple[str, ...] = (
        "scenario_family",
        "scenario_manifest_hash",
        "root_seed",
        "environment",
        "agent",
        "shift",
        "severity",
        "oversight_treatment",
        "repeated_steps",
    )
    multiple_comparison_method: str = "none"

    def __post_init__(self) -> None:
        if self.schema_version != STATISTICAL_ANALYSIS_SCHEMA_VERSION:
            raise ValueError("unsupported statistical analysis schema")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be in (0, 1)")
        if self.resamples < 100:
            raise ValueError("at least 100 bootstrap resamples are required")
        if self.multiple_comparison_method not in {"none", "bonferroni", "holm", "benjamini_hochberg"}:
            raise ValueError("unknown multiple-comparison method")

    def to_dict(self) -> dict[str, Any]:
        value = canonicalize(self)
        if not isinstance(value, dict):  # pragma: no cover
            raise RuntimeError("analysis config did not normalize to a mapping")
        return value


@dataclass(frozen=True)
class IntervalEstimate:
    analysis_schema_version: str
    estimate_type: str
    effect_size: float
    interval_low: float | None
    interval_high: float | None
    confidence_level: float
    interval_method: str
    status: str
    independent_scenario_count: int
    scenario_family_count: int
    seed_count: int
    condition_count: int
    analysis_seed: int
    resamples: int
    missing_pair_count: int = 0

    def __post_init__(self) -> None:
        if self.analysis_schema_version != STATISTICAL_ANALYSIS_SCHEMA_VERSION:
            raise ValueError("unsupported interval analysis schema")
        if self.status not in {"ok", "insufficient_independent_units", "no_eligible_units"}:
            raise ValueError(f"unknown interval status: {self.status!r}")
        if self.status == "ok" and (self.interval_low is None or self.interval_high is None):
            raise ValueError("successful interval estimates require numeric bounds")
        if self.status != "ok" and (self.interval_low is not None or self.interval_high is not None):
            raise ValueError("refused interval estimates must not emit numeric bounds")

    def to_dict(self) -> dict[str, Any]:
        value = canonicalize(self)
        if not isinstance(value, dict):  # pragma: no cover
            raise RuntimeError("interval estimate did not normalize to a mapping")
        return value


@dataclass(frozen=True)
class PowerPlan:
    analysis_schema_version: str
    method: str
    effect_size: float
    standard_deviation: float
    alpha: float
    target_power: float
    required_independent_scenarios: int | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        value = canonicalize(self)
        if not isinstance(value, dict):  # pragma: no cover
            raise RuntimeError("power plan did not normalize to a mapping")
        return value


def _number(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    else:
        text = str(value).strip().lower()
        if text in {"true", "yes"}:
            return 1.0
        if text in {"false", "no"}:
            return 0.0
        number = float(text)
    if not math.isfinite(number):
        raise ValueError("statistical values must be finite")
    return number


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("a percentile requires at least one value")
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _cluster_values(
    rows: Iterable[Mapping[str, object]],
    *,
    value_key: str,
    scenario_key: str,
    family_key: str,
    seed_key: str,
) -> tuple[dict[str, tuple[str, str, float]], int]:
    observations: dict[str, list[float]] = defaultdict(list)
    metadata: dict[str, tuple[str, str]] = {}
    conditions: set[str] = set()
    for row in rows:
        scenario = str(row.get(scenario_key, ""))
        if not scenario:
            continue
        family = str(row.get(family_key, "unknown"))
        seed = str(row.get(seed_key, "unknown"))
        prior = metadata.setdefault(scenario, (family, seed))
        if prior != (family, seed):
            raise ValueError(f"scenario {scenario!r} has inconsistent family or seed metadata")
        observations[scenario].append(_number(row[value_key]))
        conditions.add(str(row.get("condition", row.get("fault", "unknown"))))
    clusters = {
        scenario: (metadata[scenario][0], metadata[scenario][1], mean(values))
        for scenario, values in observations.items()
    }
    return clusters, len(conditions)


def _stratified_replicates(
    values: Mapping[str, tuple[str, str, float]],
    *,
    rng: random.Random,
    resamples: int,
) -> list[float]:
    by_family: dict[str, list[float]] = defaultdict(list)
    for scenario in sorted(values):
        family, _seed, value = values[scenario]
        by_family[family].append(value)
    replicates: list[float] = []
    for _ in range(resamples):
        sampled: list[float] = []
        for family in sorted(by_family):
            family_values = sorted(by_family[family])
            sampled.extend(rng.choice(family_values) for _ in family_values)
        replicates.append(mean(sampled))
    return replicates


def _estimate(
    clusters: Mapping[str, tuple[str, str, float]],
    *,
    config: AnalysisConfig,
    estimate_type: str,
    interval_method: str,
    condition_count: int,
    missing_pair_count: int = 0,
) -> IntervalEstimate:
    scenario_count = len(clusters)
    families = {family for family, _seed, _value in clusters.values()}
    seeds = {seed for _family, seed, _value in clusters.values()}
    effect = mean(value for _family, _seed, value in clusters.values()) if clusters else 0.0
    if not clusters:
        return IntervalEstimate(
            STATISTICAL_ANALYSIS_SCHEMA_VERSION,
            estimate_type,
            effect,
            None,
            None,
            config.confidence_level,
            interval_method,
            "no_eligible_units",
            0,
            0,
            0,
            condition_count,
            config.analysis_seed,
            config.resamples,
            missing_pair_count,
        )
    if scenario_count < 2:
        return IntervalEstimate(
            STATISTICAL_ANALYSIS_SCHEMA_VERSION,
            estimate_type,
            effect,
            None,
            None,
            config.confidence_level,
            interval_method,
            "insufficient_independent_units",
            scenario_count,
            len(families),
            len(seeds),
            condition_count,
            config.analysis_seed,
            config.resamples,
            missing_pair_count,
        )
    rng = random.Random(config.analysis_seed)
    replicates = _stratified_replicates(clusters, rng=rng, resamples=config.resamples)
    alpha = 1.0 - config.confidence_level
    return IntervalEstimate(
        STATISTICAL_ANALYSIS_SCHEMA_VERSION,
        estimate_type,
        effect,
        _percentile(replicates, alpha / 2.0),
        _percentile(replicates, 1.0 - alpha / 2.0),
        config.confidence_level,
        interval_method,
        "ok",
        scenario_count,
        len(families),
        len(seeds),
        condition_count,
        config.analysis_seed,
        config.resamples,
        missing_pair_count,
    )


def scenario_cluster_bootstrap(
    rows: Iterable[Mapping[str, object]],
    *,
    value_key: str,
    config: AnalysisConfig = AnalysisConfig(),
    scenario_key: str = "scenario_manifest_hash",
    family_key: str = "scenario_family",
    seed_key: str = "root_seed",
) -> IntervalEstimate:
    clusters, condition_count = _cluster_values(
        rows,
        value_key=value_key,
        scenario_key=scenario_key,
        family_key=family_key,
        seed_key=seed_key,
    )
    return _estimate(
        clusters,
        config=config,
        estimate_type="scenario_cluster_mean",
        interval_method=SCENARIO_BOOTSTRAP_METHOD,
        condition_count=condition_count,
    )


def paired_scenario_bootstrap(
    rows: Iterable[Mapping[str, object]],
    *,
    value_key: str,
    condition_key: str = "condition",
    reference_condition: str = "clean",
    treatment_condition: str = "shifted",
    config: AnalysisConfig = AnalysisConfig(),
    scenario_key: str = "scenario_manifest_hash",
    family_key: str = "scenario_family",
    seed_key: str = "root_seed",
) -> IntervalEstimate:
    by_scenario: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    metadata: dict[str, tuple[str, str]] = {}
    all_scenarios: set[str] = set()
    conditions: set[str] = set()
    for row in rows:
        scenario = str(row.get(scenario_key, ""))
        if not scenario:
            continue
        condition = str(row.get(condition_key, ""))
        all_scenarios.add(scenario)
        conditions.add(condition)
        family = str(row.get(family_key, "unknown"))
        seed = str(row.get(seed_key, "unknown"))
        prior = metadata.setdefault(scenario, (family, seed))
        if prior != (family, seed):
            raise ValueError(f"scenario {scenario!r} has inconsistent family or seed metadata")
        by_scenario[scenario][condition].append(_number(row[value_key]))
    differences: dict[str, tuple[str, str, float]] = {}
    for scenario, condition_values in by_scenario.items():
        if reference_condition not in condition_values or treatment_condition not in condition_values:
            continue
        differences[scenario] = (
            metadata[scenario][0],
            metadata[scenario][1],
            mean(condition_values[treatment_condition]) - mean(condition_values[reference_condition]),
        )
    return _estimate(
        differences,
        config=config,
        estimate_type="matched_treatment_minus_clean",
        interval_method=PAIRED_BOOTSTRAP_METHOD,
        condition_count=len(conditions),
        missing_pair_count=len(all_scenarios) - len(differences),
    )


def wilson_binomial_interval(
    successes: int,
    trials: int,
    *,
    confidence_level: float = 0.95,
    independent_binary_units: bool,
) -> tuple[float, float]:
    if not independent_binary_units:
        raise ValueError("binomial intervals require genuinely independent binary units")
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("binomial counts must satisfy 0 <= successes <= trials and trials > 0")
    z = NormalDist().inv_cdf(0.5 + confidence_level / 2.0)
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    half = z * math.sqrt(proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials))
    half /= denominator
    return max(0.0, center - half), min(1.0, center + half)


def adjust_p_values(p_values: Sequence[float], method: str = "none") -> list[float]:
    if method not in {"none", "bonferroni", "holm", "benjamini_hochberg"}:
        raise ValueError("unknown multiple-comparison method")
    if any(not 0.0 <= value <= 1.0 for value in p_values):
        raise ValueError("p-values must be in [0, 1]")
    count = len(p_values)
    if method == "none" or count == 0:
        return list(p_values)
    if method == "bonferroni":
        return [min(1.0, value * count) for value in p_values]
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * count
    if method == "holm":
        running = 0.0
        for rank, (index, value) in enumerate(ordered):
            running = max(running, min(1.0, value * (count - rank)))
            adjusted[index] = running
        return adjusted
    running = 1.0
    for reverse_rank, (index, value) in enumerate(reversed(ordered), start=1):
        rank = count - reverse_rank + 1
        running = min(running, value * count / rank)
        adjusted[index] = min(1.0, running)
    return adjusted


def plan_paired_sample_size(
    effect_size: float,
    standard_deviation: float,
    *,
    alpha: float = 0.05,
    target_power: float = 0.8,
) -> PowerPlan:
    if standard_deviation <= 0.0 or not 0.0 < alpha < 1.0 or not 0.0 < target_power < 1.0:
        raise ValueError("sample-size inputs must have positive deviation and probabilities in (0, 1)")
    if effect_size == 0.0:
        return PowerPlan(
            STATISTICAL_ANALYSIS_SCHEMA_VERSION,
            "normal_approximation_paired_mean",
            effect_size,
            standard_deviation,
            alpha,
            target_power,
            None,
            "undefined_zero_effect",
        )
    z_alpha = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    z_power = NormalDist().inv_cdf(target_power)
    required = math.ceil(((z_alpha + z_power) * standard_deviation / abs(effect_size)) ** 2)
    return PowerPlan(
        STATISTICAL_ANALYSIS_SCHEMA_VERSION,
        "normal_approximation_paired_mean",
        effect_size,
        standard_deviation,
        alpha,
        target_power,
        max(2, required),
        "ok",
    )


for _record in (AnalysisConfig, IntervalEstimate, PowerPlan):
    register_dataclass(_record)
