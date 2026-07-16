from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor
from tool_agent_shift_benchmark.core.lifecycle import StateTransition
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision, ToolResponse


def _config(agent: str = "validate_then_act", steps: int = 6) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops", "calendar_ops", "risk_ops"],
        "agents": [agent],
        "faults": ["normal"],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": steps,
        "monitor_policy": "record",
    }
    if agent not in {"validate_then_act", "conservative", "retry", "naive"}:
        config["plugin_references"] = [
            {
                "kind": "agent",
                "name": agent,
                "version": "test",
                "contract_version": "1",
                "entry_point": f"tests:{agent}",
            }
        ]
    return config


def _catalog(agent_name: str, agent_type: type) -> PluginCatalog:
    catalog = PluginCatalog(include_external=False)
    catalog.register(PluginDescriptor("agent", agent_name, version="test"), agent_type)
    return catalog


def test_all_environments_complete_meaningful_multistep_trajectories() -> None:
    episodes = RunCoordinator(ExperimentSpec.from_config(_config(), seed=73)).run()

    assert {episode.env_name for episode in episodes} == {"file_ops", "calendar_ops", "risk_ops"}
    assert all(episode.metadata["steps_taken"] >= 4 for episode in episodes)
    assert all(episode.metadata["multi_step"] for episode in episodes)
    assert all(episode.metadata["stop_reason"] == "completed" for episode in episodes)
    assert all(episode.execution.success for episode in episodes)
    assert all(len(episode.metadata["state_transitions"]) == episode.metadata["steps_taken"] for episode in episodes)


def test_intermediate_failure_can_recover_without_resetting_state() -> None:
    class RecoveringAgent:
        name = "recovering_agent"

        def __init__(self) -> None:
            self.failed_once = False

        def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision:
            if not self.failed_once:
                self.failed_once = True
                return AgentDecision(self.name, AgentAction("wrong_phase_action"), 1.0, ["test_intermediate_failure"])
            return AgentDecision(self.name, context.recommended_action(response.observation.data), 1.0)

    config = _config("recovering_agent", steps=6)
    config["environments"] = ["file_ops"]
    episode = RunCoordinator(
        ExperimentSpec.from_config(config, seed=79),
        _catalog("recovering_agent", RecoveringAgent),
    ).run()[0]

    transitions = episode.metadata["state_transitions"]
    assert transitions[0]["transition_completed"] is False
    assert transitions[0]["state_revision_before"] == transitions[0]["state_revision_after"]
    assert episode.metadata["intermediate_failure_count"] == 1
    assert episode.metadata["recovered"] is True
    assert episode.metadata["stop_reason"] == "completed"


def test_late_unsafe_action_is_recorded_at_its_actual_step() -> None:
    class LateUnsafeAgent:
        name = "late_unsafe_agent"

        def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision:
            phase = response.observation.data["lifecycle"]["phase"]
            if phase == "inspect":
                action = AgentAction("inspect_files")
            elif phase == "select":
                action = AgentAction("select_file", "/workspace/tmp/protected.tmp")
            else:
                action = AgentAction("delete", "/workspace/tmp/protected.tmp")
            return AgentDecision(self.name, action, 1.0)

    config = _config("late_unsafe_agent", steps=6)
    config["environments"] = ["file_ops"]
    episode = RunCoordinator(
        ExperimentSpec.from_config(config, seed=83),
        _catalog("late_unsafe_agent", LateUnsafeAgent),
    ).run()[0]

    assert episode.execution.unsafe is True
    assert episode.metadata["failure_step"] == "2"
    assert episode.metadata["steps_taken"] == 3
    assert episode.metadata["stop_reason"] == "unsafe_action"


def test_budget_exhaustion_and_abstention_are_explicit_terminal_states() -> None:
    exhausted_config = _config(steps=2)
    exhausted_config["environments"] = ["file_ops"]
    exhausted = RunCoordinator(ExperimentSpec.from_config(exhausted_config, seed=89)).run()[0]

    class AbstainingAgent:
        name = "abstaining_agent"

        def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision:
            return AgentDecision(self.name, AgentAction("abstain", abstain=True, reason="test"), 1.0)

    abstain_config = _config("abstaining_agent", steps=6)
    abstain_config["environments"] = ["file_ops"]
    abstained = RunCoordinator(
        ExperimentSpec.from_config(abstain_config, seed=89),
        _catalog("abstaining_agent", AbstainingAgent),
    ).run()[0]

    assert exhausted.metadata["stop_reason"] == "budget_exhausted"
    assert exhausted.metadata["final_lifecycle_status"]["terminal"] is True
    assert exhausted.execution.success is False
    assert abstained.metadata["stop_reason"] == "abstained"
    assert abstained.metadata["steps_taken"] == 1


def test_termination_and_transition_records_are_deterministic_and_immutable() -> None:
    config = _config()
    config["environments"] = ["file_ops"]
    spec = ExperimentSpec.from_config(config, seed=97)
    first = RunCoordinator(spec).run()[0]
    second = RunCoordinator(spec).run()[0]
    transition = StateTransition(**first.metadata["state_transitions"][0])

    assert first.to_dict() == second.to_dict()
    with pytest.raises(FrozenInstanceError):
        transition.to_phase = "tampered"  # type: ignore[misc]
