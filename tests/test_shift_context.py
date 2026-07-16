from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from tests.shift_context_helpers import shift_context

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor
from tool_agent_shift_benchmark.core.identity import IDENTITY_SCHEMA_VERSION
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
from tool_agent_shift_benchmark.core.shift_context import SHIFT_CONTEXT_SCHEMA_VERSION, ShiftContext
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.faults.base import BaseFault


class MaliciousInspectionShift(BaseFault):
    """Test shift that probes every historically exposed authority."""

    name = "malicious_inspection"
    version = "1.0.0"
    attempted_attributes = (
        "environment",
        "hidden_ground_truth",
        "protected_ground_truth",
        "execute",
        "pure_action_outcome",
        "filesystem",
        "network",
        "credentials",
    )
    observations: list[dict[str, Any]] = []

    def apply(self, response, context):
        missing = []
        for attribute in self.attempted_attributes:
            with pytest.raises(AttributeError):
                getattr(context, attribute)
            missing.append(attribute)
        with pytest.raises(TypeError):
            context.public_scenario_metadata["task"] = "attacker_override"
        with pytest.raises(FrozenInstanceError):
            context.rng_seed = 0
        self.observations.append(
            {
                "type": type(context),
                "missing": tuple(missing),
                "has_instance_dict": hasattr(context, "__dict__"),
                "schema_version": context.schema_version,
            }
        )
        return self._record_only(
            response,
            self._effect("malicious_boundary_probe", 0.0, {"access_denied": missing}),
        )


class LegacyEnvironmentShift(BaseFault):
    name = "legacy_environment_shift"

    def apply(self, response, environment, rng):
        return response


def test_legacy_environment_shift_signature_fails_registration() -> None:
    descriptor = PluginDescriptor.for_factory("shift", LegacyEnvironmentShift.name, LegacyEnvironmentShift)

    with pytest.raises(ValueError, match=r"apply signature must be \(self, response, context\)"):
        PluginCatalog(include_external=False).register(descriptor, LegacyEnvironmentShift)


def test_shift_context_is_recursively_immutable_and_deterministic() -> None:
    environment = FileOpsEnvironment(seed=41)
    response = environment.tool_response()
    context = shift_context(environment, response, 123)

    with pytest.raises(TypeError):
        context.visible_schema["required_fields"] = ()
    with pytest.raises(TypeError):
        context.visible_schema["action_schema"]["action_types"] = ()
    with pytest.raises(AttributeError):
        context.visible_schema["required_fields"].append("hidden")
    with pytest.raises(FrozenInstanceError):
        context.step_index = 99

    assert context.rng().getrandbits(128) == context.rng().getrandbits(128)
    assert context.with_rng_seed(124).rng().getrandbits(128) != context.rng().getrandbits(128)
    assert canonical_dumps(context.to_dict()) == canonical_dumps(context)


def test_runner_gives_malicious_shift_only_the_documented_context() -> None:
    MaliciousInspectionShift.observations.clear()
    catalog = PluginCatalog(include_external=False)
    catalog.register(
        PluginDescriptor.for_factory("shift", MaliciousInspectionShift.name, MaliciousInspectionShift),
        MaliciousInspectionShift,
    )
    config = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": [MaliciousInspectionShift.name],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": 1,
        "plugin_references": [
            {
                "kind": "shift",
                "name": MaliciousInspectionShift.name,
                "version": MaliciousInspectionShift.version,
                "contract_version": "2",
                "entry_point": "tests.test_shift_context:MaliciousInspectionShift",
            }
        ],
    }

    coordinator = RunCoordinator(ExperimentSpec.from_config(config, seed=43), catalog)
    episodes = coordinator.run()

    assert episodes
    assert MaliciousInspectionShift.observations
    for observed in MaliciousInspectionShift.observations:
        assert observed == {
            "type": ShiftContext,
            "missing": MaliciousInspectionShift.attempted_attributes,
            "has_instance_dict": False,
            "schema_version": SHIFT_CONTEXT_SCHEMA_VERSION,
        }
    identity = coordinator.identity
    assert identity is not None
    assert identity.schema_version == IDENTITY_SCHEMA_VERSION == "19"
    assert identity.semantic.step_semantics.shift_context_schema_version == SHIFT_CONTEXT_SCHEMA_VERSION
    provenance = episodes[0].tool_response.observation.metadata["fault_schedule_provenance"]
    assert all(item["shift_context_schema_version"] == SHIFT_CONTEXT_SCHEMA_VERSION for item in provenance)


def test_shift_context_serialization_contains_no_authoritative_handles() -> None:
    environment = FileOpsEnvironment(seed=47)
    response = environment.tool_response()
    payload = shift_context(environment, response, 149).to_dict()
    serialized = canonical_dumps(payload)

    assert set(payload) == {
        "schema_version",
        "step_index",
        "attempt_number",
        "public_scenario_metadata",
        "visible_schema",
        "timing",
        "rng_seed",
        "fault_schedule",
        "channel_metadata",
    }
    for forbidden in (
        "hidden_ground_truth",
        "protected_ground_truth",
        "pure_action_outcome",
        "filesystem",
        "network_handle",
        "credential",
    ):
        assert forbidden not in serialized
