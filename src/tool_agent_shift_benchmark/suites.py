"""Versioned golden-suite contracts and durable invariant validation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from tool_agent_shift_benchmark.core.execution import ExecutionRequest, normalize_execution_request
from tool_agent_shift_benchmark.core.serialization import canonical_loads
from tool_agent_shift_benchmark.core.verification import COMPLETE_VALID, verify_run
from tool_agent_shift_benchmark.package_resources import builtin_suite_names, read_builtin_suite

SUITE_CONTRACT_VERSION = "suite-contract-v1"
GOLDEN_VALIDATION_VERSION = "golden-suite-validation-v1"
REQUIRED_MANIFEST_KEYS = {
    "challenge_outcomes_may_inform_development",
    "config",
    "expected_plan_count",
    "golden_checks",
    "name",
    "performance_budget",
    "scenario_split",
    "schema_version",
    "seed",
    "suite_version",
}


class SuiteValidationError(ValueError):
    """Raised when a suite contract or its completed bundle is invalid."""


@dataclass(frozen=True)
class SuiteContract:
    name: str
    suite_version: str
    config: str
    seed: int
    scenario_split: str
    expected_plan_count: int
    golden_checks: tuple[str, ...]
    performance_budget: Mapping[str, float]
    challenge_outcomes_may_inform_development: bool

    @classmethod
    def load(cls, name: str) -> "SuiteContract":
        raw = read_builtin_suite(name)
        if set(raw) != REQUIRED_MANIFEST_KEYS:
            missing = sorted(REQUIRED_MANIFEST_KEYS - set(raw))
            unknown = sorted(set(raw) - REQUIRED_MANIFEST_KEYS)
            raise SuiteValidationError(f"invalid suite manifest keys: missing={missing}, unknown={unknown}")
        if raw["schema_version"] != SUITE_CONTRACT_VERSION:
            raise SuiteValidationError(f"unsupported suite schema: {raw['schema_version']!r}")
        if raw["name"] not in builtin_suite_names() or raw["name"] != name.removeprefix("builtin:"):
            raise SuiteValidationError("suite manifest name does not match its packaged resource")
        checks = tuple(str(value) for value in raw["golden_checks"])
        budget = raw["performance_budget"]
        if not isinstance(budget, dict) or not budget:
            raise SuiteValidationError("suite performance_budget must be a non-empty object")
        contract = cls(
            name=str(raw["name"]),
            suite_version=str(raw["suite_version"]),
            config=str(raw["config"]),
            seed=int(raw["seed"]),
            scenario_split=str(raw["scenario_split"]),
            expected_plan_count=int(raw["expected_plan_count"]),
            golden_checks=checks,
            performance_budget={str(key): float(value) for key, value in budget.items()},
            challenge_outcomes_may_inform_development=bool(raw["challenge_outcomes_may_inform_development"]),
        )
        contract.validate_plan()
        return contract

    def plan(self):
        return normalize_execution_request(ExecutionRequest(config_path=self.config, mode="ordinary", seed=self.seed))

    def validate_plan(self) -> None:
        first = self.plan()
        second = self.plan()
        if len(first.episodes) != self.expected_plan_count:
            raise SuiteValidationError(
                f"suite {self.name} expected {self.expected_plan_count} episodes, planned {len(first.episodes)}"
            )
        if first.to_dict() != second.to_dict():
            raise SuiteValidationError(f"suite {self.name} plan is not stable")
        if first.planner.identity.semantic.scenario_split != self.scenario_split:
            raise SuiteValidationError(f"suite {self.name} scenario split does not match its contract")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SUITE_CONTRACT_VERSION,
            "name": self.name,
            "suite_version": self.suite_version,
            "config": self.config,
            "seed": self.seed,
            "scenario_split": self.scenario_split,
            "expected_plan_count": self.expected_plan_count,
            "golden_checks": list(self.golden_checks),
            "performance_budget": dict(self.performance_budget),
            "challenge_outcomes_may_inform_development": self.challenge_outcomes_may_inform_development,
        }


def _json(path: Path) -> dict[str, Any]:
    value = canonical_loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SuiteValidationError(f"JSON object required: {path}")
    return value


def _jsonl(path: Path) -> list[dict[str, Any]]:
    output = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = canonical_loads(line)
        if isinstance(value, dict):
            output.append(value)
    return output


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _check(name: str, passed: bool, detail: str, evidence: list[str]) -> dict[str, Any]:
    return {"name": name, "status": "passed" if passed else "failed", "detail": detail, "evidence": evidence}


def validate_suite_bundle(contract: SuiteContract, run_dir: str | Path) -> dict[str, Any]:
    """Evaluate broad scientific invariants without brittle floating snapshots."""

    root = Path(run_dir)
    verification = verify_run(root)
    status = _json(root / "status.json")
    identity = _json(root / "identity" / "experiment_identity.json")
    plugins = _json(root / "plugins" / "descriptors.json")
    episodes = _jsonl(root / "results" / "episodes.jsonl")
    outcomes = _csv(root / "results" / "episode_outcomes.csv")
    metrics = _csv(root / "results" / "metric_evidence.csv")
    checks: list[dict[str, Any]] = []
    checks.append(
        _check(
            "artifact_verification",
            verification["status"] == COMPLETE_VALID,
            str(verification["status"]),
            ["run_manifest.json", "finalization.json"],
        )
    )
    plan_count_ok = all(
        int(status.get(field, -1)) == expected
        for field, expected in (
            ("planned_episodes", contract.expected_plan_count),
            ("completed_episodes", contract.expected_plan_count),
            ("failed_episodes", 0),
            ("pending_episodes", 0),
            ("invalid_episodes", 0),
        )
    )
    checks.append(
        _check("plan_count", plan_count_ok, f"planned/completed={contract.expected_plan_count}", ["status.json"])
    )
    semantic = identity.get("semantic", {})
    split_ok = semantic.get("scenario_split") == contract.scenario_split and all(
        row.get("scenario_split") == contract.scenario_split for row in outcomes
    )
    checks.append(
        _check(
            "scenario_split_integrity",
            split_ok,
            f"expected split={contract.scenario_split}",
            ["identity/experiment_identity.json", "results/episode_outcomes.csv"],
        )
    )
    recomputed = contract.plan()
    recomputed_identity = recomputed.planner.identity.to_dict()
    identity_ok = all(
        recomputed_identity.get(key) == identity.get(key) for key in ("schema_version", "run_id", "config_digest")
    )
    checks.append(
        _check(
            "identity_stability",
            identity_ok,
            f"recomputed run_id={recomputed.planner.run_id}",
            ["identity/experiment_identity.json", "plan/execution_plan.json"],
        )
    )
    config = _json(root / "results" / "config.json")
    competence = config.get("competence_gate", {})
    checks.append(
        _check(
            "clean_competence",
            competence.get("passed") is True,
            f"failed_gates={competence.get('failed_gates', [])}",
            ["results/config.json"],
        )
    )
    shifted = [episode for episode in episodes if episode.get("fault", {}).get("name") != "normal"]
    active_faults = [
        episode
        for episode in shifted
        if float(episode.get("metadata", {}).get("maximum_realized_effect_magnitude", 0.0)) > 0.0
    ]
    checks.append(
        _check(
            "fault_activation",
            bool(shifted) and len(active_faults) == len(shifted),
            f"activated={len(active_faults)}/{len(shifted)} shifted episodes",
            ["results/episodes.jsonl"],
        )
    )
    trace_lengths = [len(episode.get("action_records", [])) for episode in episodes]
    max_steps = int(config.get("normalized_config", {}).get("episode_steps", 0))
    trace_ok = bool(trace_lengths) and max_steps > 0 and all(1 <= value <= max_steps for value in trace_lengths)
    checks.append(
        _check(
            "trace_length_distribution",
            trace_ok,
            f"min={min(trace_lengths, default=0)}, max={max(trace_lengths, default=0)}, budget={max_steps}",
            ["results/episodes.jsonl", "traces/policy/", "traces/evaluator/"],
        )
    )
    if "retry_behavior" in contract.golden_checks:
        retry_episodes = [episode for episode in episodes if episode.get("agent_name") == "retry"]
        attempt_counts = [
            int(step.get("attempt_count", 0))
            for episode in retry_episodes
            for step in episode.get("metadata", {}).get("step_trace", [])
        ]
        checks.append(
            _check(
                "retry_behavior",
                bool(retry_episodes) and bool(attempt_counts) and max(attempt_counts) >= 2,
                f"retry episodes={len(retry_episodes)}, maximum decision attempts={max(attempt_counts, default=0)}",
                ["results/episodes.jsonl"],
            )
        )
    descriptors = plugins.get("descriptors", [])
    isolated = bool(descriptors) and all(
        isinstance(item, dict)
        and item.get("contract_version")
        and item.get("trust_level")
        and item.get("isolation_mode") not in {None, "", "legacy_unspecified"}
        for item in descriptors
    )
    checks.append(
        _check(
            "plugin_boundary_isolation",
            isolated,
            f"validated descriptors={len(descriptors)}",
            ["plugins/descriptors.json"],
        )
    )
    rate_rows = [
        row for row in metrics if row.get("value") not in {None, ""} and row.get("unit") in {"episode", "step"}
    ]
    ranges_ok = bool(rate_rows) and all(0.0 <= float(row["value"]) <= 1.0 for row in rate_rows)
    checks.append(
        _check(
            "broad_metric_ranges",
            ranges_ok,
            f"bounded rate rows={len(rate_rows)}",
            ["results/metric_evidence.csv"],
        )
    )
    expected = set(contract.golden_checks)
    observed = {row["name"] for row in checks}
    missing = sorted(expected - observed)
    if missing:
        checks.append(_check("suite_contract_coverage", False, f"missing checks: {missing}", []))
    return {
        "schema_version": GOLDEN_VALIDATION_VERSION,
        "suite": contract.to_dict(),
        "run": str(root),
        "run_id": verification.get("run_id"),
        "challenge_use_policy": (
            "development_use_permitted"
            if contract.challenge_outcomes_may_inform_development
            else "outcomes_sealed_from_development; structural validation only"
        ),
        "status": "passed" if checks and all(row["status"] == "passed" for row in checks) else "failed",
        "checks": checks,
    }
