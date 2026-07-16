from __future__ import annotations

from random import Random

import pytest

from tool_agent_shift_benchmark.core.context import ObservationContext, redact_response_for_policy
from tool_agent_shift_benchmark.core.fault_channels import FAULT_CHANNEL_CONTRACT
from tool_agent_shift_benchmark.core.identity import IDENTITY_SCHEMA_VERSION
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.faults import FAULTS

ENVIRONMENTS = (FileOpsEnvironment, CalendarOpsEnvironment, RiskOpsEnvironment)


def named_effect(response, fault_name: str) -> dict[str, object]:
    return next(effect for effect in reversed(response.observation.metadata["faults"]) if effect["name"] == fault_name)


def test_every_fault_declares_a_unique_causal_mechanism_and_typed_channel() -> None:
    descriptors = {name: fault.channel_descriptor() for name, fault in FAULTS.items()}

    assert all(descriptor.contract == FAULT_CHANNEL_CONTRACT for descriptor in descriptors.values())
    assert len({descriptor.causal_mechanism for descriptor in descriptors.values()}) == len(descriptors)
    assert all(descriptor.severity_semantics for descriptor in descriptors.values())
    assert all(descriptor.schedule_behavior for descriptor in descriptors.values())
    assert all(descriptor.detection_path for descriptor in descriptors.values())
    assert all(descriptor.adaptation_path for descriptor in descriptors.values())


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
@pytest.mark.parametrize("fault_name", tuple(FAULTS))
def test_fault_effect_provenance_records_channel_and_mechanism(environment_type: type, fault_name: str) -> None:
    environment = environment_type(seed=1409)
    shifted = FAULTS[fault_name](1.0).apply(environment.tool_response(), environment, Random(41))
    effect = named_effect(shifted, fault_name)
    descriptor = FAULTS[fault_name].channel_descriptor()

    assert effect["details"]["fault_channel"] == descriptor.channel
    assert effect["details"]["causal_mechanism"] == descriptor.causal_mechanism


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
def test_missing_field_targets_relevant_leaf_paths_and_preserves_encoding(environment_type: type) -> None:
    environment = environment_type(seed=1423)
    clean = environment.tool_response()
    shifted = FAULTS["missing_field"](1.0).apply(clean, environment, Random(43))
    details = named_effect(shifted, "missing_field")["details"]

    assert details["removed_paths"]
    assert details["encoding_preserved"] is True
    assert shifted.observation.schema_version == clean.observation.schema_version
    primary = {"file_ops": "files", "calendar_ops": "availability", "risk_ops": "market_state"}[environment.name]
    assert primary in shifted.observation.data
    assert "schema_info" not in shifted.metadata
    assert canonical_dumps(shifted.observation.data)


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
def test_conflicting_output_is_named_snapshot_evidence_with_asymmetric_reliability(environment_type: type) -> None:
    environment = environment_type(seed=1433)
    shifted = FAULTS["conflicting_tool_output"](1.0).apply(environment.tool_response(), environment, Random(47))
    conflict = shifted.observation.data["conflicting_views"]
    sources = conflict["sources"]
    details = named_effect(shifted, "conflicting_tool_output")["details"]

    assert len(sources) == 2
    assert sources[0]["source_id"] != sources[1]["source_id"]
    assert sources[0]["snapshot_id"] != sources[1]["snapshot_id"]
    assert sources[0]["reliability"] > sources[1]["reliability"]
    assert set(sources[0]["values"]) == set(sources[1]["values"]) == set(conflict["disagreement_paths"])
    assert details["asymmetric_reliability"] is True
    assert [source["source_id"] for source in details["source_provenance"]] == [
        source["source_id"] for source in sources
    ]


@pytest.mark.parametrize("environment_type", ENVIRONMENTS)
def test_constraint_shift_separates_visible_changes_from_hidden_reference(environment_type: type) -> None:
    environment = environment_type(seed=1447)
    clean = environment.tool_response()
    hidden_before = environment.hidden_ground_truth()
    shifted = FAULTS["constraint_shift"](1.0).apply(clean, environment, Random(53))
    details = named_effect(shifted, "constraint_shift")["details"]
    policy = redact_response_for_policy(shifted)
    policy_payload = canonical_dumps(policy.to_dict())

    assert details["visible_constraints_before"] == clean.observation.constraints
    assert details["visible_constraints_after"] == shifted.observation.constraints
    assert details["constraint_deltas"]
    assert details["hidden_constraint_reference_hash"]
    assert shifted.observation.metadata["constraint_context"]["effective_at"] == environment.current_time
    assert shifted.observation.metadata["constraint_context"]["lifecycle_phase"] == environment.lifecycle_phase
    assert environment.hidden_ground_truth() == hidden_before
    assert "hidden_constraint_reference_hash" not in policy_payload
    assert "constraint_context" in policy.observation.metadata


def test_constraint_shift_activation_is_temporal_and_schedule_bound() -> None:
    config = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["constraint_shift"],
        "fault_severities": [1.0],
        "fault_schedules": [
            {
                "shift_chain": ["constraint_shift"],
                "configured_severity": 1.0,
                "onset_step": 1,
                "duration": 1,
                "persistence": "transient",
                "recurrence": None,
                "per_step_severity": [1.0],
            }
        ],
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "monitor_policy": "record",
    }
    episodes = RunCoordinator(ExperimentSpec.from_config(config, seed=1459)).run()
    shifted = next(episode for episode in episodes if episode.fault.name == "constraint_shift")
    evaluator = shifted.metadata["evaluator_trace"]

    assert evaluator[0]["fault_schedule_provenance"][0]["active"] is False
    assert evaluator[1]["fault_schedule_provenance"][0]["active"] is True
    assert evaluator[1]["shift_provenance"][0]["details"]["effective_at"]
    assert evaluator[1]["fault_schedule_provenance"][0]["component_channels"][0]["channel"] == ("constraint_visibility")


def test_stale_data_unsafe_outcome_is_not_automatically_a_constraint_violation() -> None:
    environment = FileOpsEnvironment(seed=1471)
    first = environment.tool_response()
    context = ObservationContext.from_environment(environment, first.observation)
    environment.execute(context.recommended_action(first.observation.data), observed_timestamp=environment.current_time)
    second = environment.tool_response()
    context = ObservationContext.from_environment(environment, second.observation)
    environment.execute(
        context.recommended_action(second.observation.data), observed_timestamp=environment.current_time
    )
    act_response = environment.tool_response()
    context = ObservationContext.from_environment(environment, act_response.observation)
    action = context.recommended_action(act_response.observation.data)
    result = environment.execute(action, observed_timestamp=environment.current_time - 1)

    assert result.unsafe
    assert result.stale_data_action
    assert not result.constraint_violation
    assert result.unsafe_reasons == ["acted_on_stale_directory_listing"]


def test_fault_channel_contract_is_bound_into_scientific_identity() -> None:
    coordinator = RunCoordinator(
        ExperimentSpec.from_config(
            {
                "schema_version": 2,
                "environments": ["file_ops"],
                "agents": ["validate_then_act"],
                "faults": ["missing_field"],
                "episodes_per_combo": 1,
            },
            seed=1481,
        )
    )
    coordinator.run()

    assert IDENTITY_SCHEMA_VERSION == "17"
    assert coordinator.identity is not None
    assert coordinator.identity.semantic.fault_channel_contract == FAULT_CHANNEL_CONTRACT
