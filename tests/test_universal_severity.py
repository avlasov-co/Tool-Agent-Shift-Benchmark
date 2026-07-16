from __future__ import annotations

from random import Random

import pytest

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.context import redact_response_for_policy
from tool_agent_shift_benchmark.core.fault_effects import FAULT_EFFECT_CONTRACT, FaultEffect
from tool_agent_shift_benchmark.core.identity import IDENTITY_SCHEMA_VERSION
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.types import FaultConfig
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.faults import FAULTS

ENVIRONMENTS = (FileOpsEnvironment, CalendarOpsEnvironment, RiskOpsEnvironment)
SEVERITIES = (0.0, 0.25, 0.5, 1.0)
DETAIL_FIELDS = {
    "normal": "reason",
    "schema_drift": "renamed_fields",
    "stale_observation": "staleness_ms",
    "latency_spike": "added_latency_ms",
    "missing_field": "removed_paths",
    "conflicting_tool_output": "conflict_fraction",
    "corrupted_memory": "corruption_amount",
    "constraint_shift": "constraint_deltas",
    "compound_shift": "parts",
}


def named_effect(response, fault_name: str) -> dict[str, object]:
    return next(effect for effect in reversed(response.observation.metadata["faults"]) if effect["name"] == fault_name)


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
@pytest.mark.parametrize("fault_name", tuple(FAULTS))
@pytest.mark.parametrize("severity", SEVERITIES)
def test_every_fault_has_auditable_zero_low_medium_and_maximum_behavior(
    environment_type: type,
    fault_name: str,
    severity: float,
) -> None:
    environment = environment_type(seed=97, scenario_index=1)
    clean = environment.tool_response()
    ground_truth = environment.hidden_ground_truth()
    shifted = FAULTS[fault_name](severity=severity).apply(clean, environment, Random(101))
    effect = named_effect(shifted, fault_name)

    assert effect["contract"] == FAULT_EFFECT_CONTRACT
    assert effect["configured_severity"] == severity
    assert 0.0 <= float(effect["realized_magnitude"]) <= 1.0
    assert effect["no_op"] is (float(effect["realized_magnitude"]) == 0.0)
    assert DETAIL_FIELDS[fault_name] in effect["details"]
    assert environment.hidden_ground_truth() == ground_truth
    if severity == 0.0:
        assert redact_response_for_policy(shifted).to_dict() == redact_response_for_policy(clean).to_dict()
        assert effect["no_op"] is True
    elif fault_name == "normal":
        assert redact_response_for_policy(shifted).to_dict() == redact_response_for_policy(clean).to_dict()
        assert effect["realized_magnitude"] == 0.0
    else:
        assert float(effect["realized_magnitude"]) > 0.0


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
@pytest.mark.parametrize("fault_name", tuple(FAULTS))
def test_realized_fault_magnitude_is_deterministic_and_monotonic(
    environment_type: type,
    fault_name: str,
) -> None:
    magnitudes = []
    outputs = []
    for severity in SEVERITIES:
        environment = environment_type(seed=103, scenario_index=2)
        response = FAULTS[fault_name](severity=severity).apply(
            environment.tool_response(),
            environment,
            Random(107),
        )
        magnitudes.append(float(named_effect(response, fault_name)["realized_magnitude"]))
        outputs.append(response.to_dict())
        repeat_environment = environment_type(seed=103, scenario_index=2)
        repeated = FAULTS[fault_name](severity=severity).apply(
            repeat_environment.tool_response(),
            repeat_environment,
            Random(107),
        )
        assert repeated.to_dict() == outputs[-1]

    assert magnitudes == sorted(magnitudes)
    assert magnitudes[0] == 0.0
    if fault_name == "normal":
        assert magnitudes[-1] == 0.0
    else:
        assert magnitudes[-1] == 1.0


def test_maximum_severity_effect_summaries_match_defined_endpoints() -> None:
    environment = FileOpsEnvironment(seed=109)
    clean = environment.tool_response()

    schema = FAULTS["schema_drift"](1.0).apply(clean, environment, Random(1))
    missing = FAULTS["missing_field"](1.0).apply(clean, environment, Random(1))
    latency = FAULTS["latency_spike"](1.0).apply(clean, environment, Random(1))
    conflict = FAULTS["conflicting_tool_output"](1.0).apply(clean, environment, Random(1))
    memory = FAULTS["corrupted_memory"](1.0).apply(clean, environment, Random(1))

    assert set(named_effect(schema, "schema_drift")["details"]["renamed_fields"]) == {
        "files->items",
        "lifecycle.phase->lifecycle.state.phase",
    }
    missing_details = named_effect(missing, "missing_field")["details"]
    assert missing_details["removed_count"] == missing_details["candidate_count"]
    latency_details = named_effect(latency, "latency_spike")["details"]
    assert latency_details["added_latency_ms"] == latency_details["maximum_latency_ms"]
    assert named_effect(conflict, "conflicting_tool_output")["details"]["conflict_fraction"] == 1.0
    assert named_effect(memory, "corrupted_memory")["details"]["corruption_amount"] == 5
    assert "memory_hint" not in memory.observation.metadata


@pytest.mark.parametrize("severity", [-0.1, 1.1, float("nan"), float("inf"), True, "0.5"])
def test_unsupported_severity_is_rejected_instead_of_clamped_or_ignored(severity: object) -> None:
    for fault_type in FAULTS.values():
        with pytest.raises(ValueError, match="severity"):
            fault_type(severity=severity)
    with pytest.raises(ValueError, match="severity"):
        FaultConfig("schema_drift", severity=severity)


def test_fault_effect_validation_rejects_inconsistent_or_unbounded_realization() -> None:
    with pytest.raises(ValueError, match="realized magnitude"):
        FaultEffect(FAULT_EFFECT_CONTRACT, "x", 0.5, 1.1, "x", False, {})
    with pytest.raises(ValueError, match="no_op"):
        FaultEffect(FAULT_EFFECT_CONTRACT, "x", 0.5, 0.0, "x", False, {})


def test_episode_and_analysis_rows_separate_configured_from_realized_severity() -> None:
    config = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["missing_field"],
        "fault_severities": [0.25],
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "monitor_policy": "record",
    }
    episode = next(
        item
        for item in RunCoordinator(ExperimentSpec.from_config(config, seed=113)).run()
        if item.fault.name == "missing_field"
    )
    row = episode.to_row()

    assert episode.metadata["fault_effect_contract"] == FAULT_EFFECT_CONTRACT
    assert episode.metadata["configured_fault_severity"] == 0.25
    assert episode.metadata["fault_effects"]
    assert episode.metadata["fault_effect_applications"] == len(episode.metadata["fault_effects"])
    assert row["configured_fault_severity"] == 0.25
    assert row["maximum_realized_effect_magnitude"] == episode.metadata["maximum_realized_effect_magnitude"]


def test_zero_severity_treatment_is_policy_equivalent_to_its_matched_clean_pair() -> None:
    config = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["schema_drift"],
        "fault_severities": [0.0],
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "monitor_policy": "record",
    }
    episodes = RunCoordinator(ExperimentSpec.from_config(config, seed=119)).run()
    clean = next(item for item in episodes if item.fault.name == "normal")
    zero = next(item for item in episodes if item.fault.name == "schema_drift")

    assert clean.scenario_pair_id == zero.scenario_pair_id
    assert clean.metadata["steps_taken"] == zero.metadata["steps_taken"]
    assert zero.metadata["maximum_realized_effect_magnitude"] == 0.0
    assert clean.execution.to_dict() == zero.execution.to_dict()
    assert clean.decision.action.to_dict() == zero.decision.action.to_dict()
    for clean_step, zero_step in zip(clean.metadata["step_trace"], zero.metadata["step_trace"]):
        assert clean_step["tool_response"]["observation"] == zero_step["tool_response"]["observation"]
        assert clean_step["response_latency_ms"] == zero_step["response_latency_ms"] == 0
        assert (
            clean_step["tool_response"]["metadata"]["requery"]["visible_response_hash"]
            == zero_step["tool_response"]["metadata"]["requery"]["visible_response_hash"]
        )


def test_fault_effect_contract_and_fault_plugin_version_are_scientific_identity() -> None:
    coordinator = RunCoordinator(
        ExperimentSpec.from_config(
            {
                "schema_version": 2,
                "environments": ["file_ops"],
                "agents": ["naive"],
                "faults": ["schema_drift"],
                "episodes_per_combo": 1,
            },
            seed=127,
        )
    )
    coordinator.run()

    assert int(IDENTITY_SCHEMA_VERSION) >= 7
    assert coordinator.identity is not None
    assert coordinator.identity.semantic.fault_effect_contract == FAULT_EFFECT_CONTRACT
    descriptor = PluginCatalog(include_external=False).descriptor("shift", "schema_drift")
    assert descriptor.version == "3.0.0"
    assert FAULT_EFFECT_CONTRACT in descriptor.capabilities
