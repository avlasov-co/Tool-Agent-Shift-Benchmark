from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pytest

from tool_agent_shift_benchmark.agents.base import BaseAgent
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.context import ObservationContext, redact_response_for_policy
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor
from tool_agent_shift_benchmark.core.immutability import POLICY_DATA_IMMUTABILITY_CONTRACT
from tool_agent_shift_benchmark.core.memory import MemoryWrite
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
from tool_agent_shift_benchmark.core.types import (
    AgentAction,
    AgentDecision,
    MonitorDecision,
    Observation,
    ToolResponse,
)
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.monitors.base import BaseMonitor
from tool_agent_shift_benchmark.monitors.composite import CompositeMonitor


def _must_be_denied(operation: Callable[[], object]) -> str:
    try:
        operation()
    except (AttributeError, TypeError) as exc:
        return type(exc).__name__
    raise AssertionError("mutation unexpectedly succeeded")


class MutatingAgent(BaseAgent):
    name = "mutating_agent"
    version = "1.0.0"
    captured_data: list[Mapping[str, Any]] = []
    denied_attempts: list[tuple[str, ...]] = []

    def decide(self, context, response):
        files = response.observation.data["files"]
        candidates = context.visible_candidates(response.observation)
        denied = (
            _must_be_denied(lambda: files[0].__setitem__("path", "/tampered")),
            _must_be_denied(lambda: files.append({"path": "/tampered"})),
            _must_be_denied(lambda: response.observation.metadata.__setitem__("attacker", True)),
            _must_be_denied(lambda: context.constraints.__setitem__("allowed_root", "/")),
            _must_be_denied(lambda: context.action_schema["action_types"].append("attacker_action")),
            _must_be_denied(lambda: candidates[0].__setitem__("path", "/tampered")),
        )
        self.captured_data.append(response.observation.data)
        self.denied_attempts.append(denied)
        return AgentDecision(self.name, context.recommended_action(response.observation.data), 1.0)


class IntegrityMonitor(BaseMonitor):
    name = "integrity_monitor"
    version = "1.0.0"
    observations_seen = 0

    def check(self, context, observation, action):
        type(self).observations_seen += 1
        files = observation.data["files"]
        assert files
        assert all(item.get("path") != "/tampered" for item in files)
        assert "attacker_action" not in context.action_schema["action_types"]
        assert "attacker" not in observation.metadata
        return MonitorDecision(self.name, True, 0.0)


class MutatingMonitor(BaseMonitor):
    name = "mutating_monitor"
    denied_attempts: tuple[str, ...] = ()

    def check(self, context, observation, action):
        self.denied_attempts = (
            _must_be_denied(lambda: observation.data["files"][0].__setitem__("path", "/tampered")),
            _must_be_denied(lambda: observation.data["files"].append({"path": "/tampered"})),
            _must_be_denied(lambda: action.params.__setitem__("attacker", True)),
            _must_be_denied(lambda: context.action_schema.__setitem__("attacker", True)),
        )
        return MonitorDecision(self.name, True, 0.0)


def test_policy_records_defensively_copy_and_recursively_freeze_aliases() -> None:
    source_data = {"nested": {"items": [{"value": 1}]}}
    source_constraints = {"limits": {"maximum": 3}}
    source_metadata = {"labels": ["visible"]}
    observation = Observation(
        "test_env",
        "scenario",
        7,
        source_data,
        constraints=source_constraints,
        metadata=source_metadata,
    )
    response_metadata = {"trace": {"events": ["created"]}}
    response = ToolResponse("test_tool", True, observation, metadata=response_metadata)
    action_params = {"nested": {"items": [1, 2]}}
    action = AgentAction("inspect", params=action_params)
    decision_metadata = {"nested": {"items": ["reason"]}}
    decision_reasons = ["safe"]
    decision = AgentDecision("test_agent", action, 1.0, decision_reasons, decision_metadata)
    monitor = MonitorDecision("test_monitor", True, 0.0, ["checked"], {"nested": {"items": [1]}})
    memory_source = {"nested": {"items": ["remembered"]}}
    memory = MemoryWrite("key", memory_source, "tool", 7)

    source_data["nested"]["items"][0]["value"] = 99
    source_constraints["limits"]["maximum"] = 99
    source_metadata["labels"].append("tampered")
    response_metadata["trace"]["events"].append("tampered")
    action_params["nested"]["items"].append(3)
    decision_metadata["nested"]["items"].append("tampered")
    decision_reasons.append("tampered")
    memory_source["nested"]["items"].append("tampered")

    assert observation.data["nested"]["items"][0]["value"] == 1
    assert observation.constraints["limits"]["maximum"] == 3
    assert observation.metadata["labels"] == ("visible",)
    assert response.metadata["trace"]["events"] == ("created",)
    assert action.params["nested"]["items"] == (1, 2)
    assert decision.reasons == ("safe",)
    assert decision.metadata["nested"]["items"] == ("reason",)
    assert monitor.metadata["nested"]["items"] == (1,)
    assert memory.value["nested"]["items"] == ("remembered",)

    for operation in (
        lambda: observation.data["nested"].__setitem__("attacker", True),
        lambda: observation.data["nested"]["items"].append("attacker"),
        lambda: response.metadata["trace"].__setitem__("attacker", True),
        lambda: action.params["nested"]["items"].append("attacker"),
        lambda: decision.metadata["nested"].__setitem__("attacker", True),
        lambda: monitor.metadata["nested"]["items"].append("attacker"),
        lambda: memory.value["nested"].__setitem__("attacker", True),
    ):
        assert _must_be_denied(operation) in {"AttributeError", "TypeError"}

    serialized = response.to_dict()
    assert isinstance(serialized["observation"]["data"], dict)
    assert isinstance(serialized["observation"]["data"]["nested"]["items"], list)
    assert canonical_dumps(response) == canonical_dumps(serialized)


def test_mutating_agent_cannot_affect_later_monitor_or_episode() -> None:
    MutatingAgent.captured_data.clear()
    MutatingAgent.denied_attempts.clear()
    IntegrityMonitor.observations_seen = 0
    catalog = PluginCatalog(include_external=False)
    for kind, factory in (("agent", MutatingAgent), ("monitor", IntegrityMonitor)):
        catalog.register(PluginDescriptor.for_factory(kind, factory.name, factory), factory)
    config = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": [MutatingAgent.name],
        "faults": ["normal"],
        "monitor": IntegrityMonitor.name,
        "episodes_per_combo": 2,
        "episode_steps": 1,
        "plugin_references": [
            {
                "kind": kind,
                "name": factory.name,
                "version": factory.version,
                "contract_version": "2",
                "entry_point": f"tests.test_deep_immutability:{factory.__name__}",
            }
            for kind, factory in (("agent", MutatingAgent), ("monitor", IntegrityMonitor))
        ],
    }

    coordinator = RunCoordinator(ExperimentSpec.from_config(config, seed=211), catalog)
    episodes = coordinator.run()

    assert len(episodes) == 2
    assert not coordinator.errors
    assert len(MutatingAgent.captured_data) == IntegrityMonitor.observations_seen == 2
    assert MutatingAgent.captured_data[0] is not MutatingAgent.captured_data[1]
    assert all(len(attempts) == 6 for attempts in MutatingAgent.denied_attempts)
    assert all("/tampered" not in canonical_dumps(episode.tool_response) for episode in episodes)
    assert coordinator.identity is not None
    assert (
        coordinator.identity.semantic.step_semantics.policy_data_immutability_contract
        == POLICY_DATA_IMMUTABILITY_CONTRACT
    )


def test_mutating_monitor_cannot_affect_later_monitor() -> None:
    environment = FileOpsEnvironment(seed=223)
    response = redact_response_for_policy(environment.tool_response())
    context = ObservationContext.from_environment(environment, response.observation)
    action = context.recommended_action(response.observation.data)
    mutating = MutatingMonitor()
    verifying = IntegrityMonitor()
    composite = CompositeMonitor(monitors=[mutating, verifying])

    result = composite.check(context, response.observation, action)

    assert result.allow_action is True
    assert len(mutating.denied_attempts) == 4
    assert verifying.observations_seen >= 1
    assert "attacker" not in canonical_dumps(response)


def test_plugin_descriptor_nested_schema_and_metadata_are_immutable() -> None:
    metadata = {"nested": {"values": [1]}}
    descriptor = PluginDescriptor.for_factory("agent", MutatingAgent.name, MutatingAgent, metadata=metadata)
    metadata["nested"]["values"].append(2)

    assert descriptor.metadata["nested"]["values"] == (1,)
    with pytest.raises(TypeError):
        descriptor.configuration_schema["properties"] = {}
    with pytest.raises(AttributeError):
        descriptor.metadata["nested"]["values"].append(3)
