from __future__ import annotations

from dataclasses import replace
from random import Random

import pytest

from tool_agent_shift_benchmark.agents.retry import RetryAgent
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.context import ObservationContext, redact_response_for_policy
from tool_agent_shift_benchmark.core.contracts import PluginDescriptor
from tool_agent_shift_benchmark.core.identity import IDENTITY_SCHEMA_VERSION
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.requery import REQUERY_ACTION_TYPE, TOOL_REQUERY_CONTRACT
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision, ToolResponse
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.faults import FAULTS


def attempt_response(response: ToolResponse, *, attempt: int, remaining: int, fingerprint: str) -> ToolResponse:
    return replace(
        redact_response_for_policy(response),
        metadata={
            "requery": {
                "contract": TOOL_REQUERY_CONTRACT,
                "attempt_number": attempt,
                "remaining_requeries": remaining,
                "visible_response_hash": fingerprint,
            }
        },
    )


def context(environment: object, response: ToolResponse) -> ObservationContext:
    return ObservationContext.from_environment(environment, response.observation)


@pytest.mark.parametrize(
    ("environment", "fault_name", "expected_reason"),
    [
        (FileOpsEnvironment(seed=31), "schema_drift", "invalid_schema"),
        (FileOpsEnvironment(seed=31), "conflicting_tool_output", "conflicting_output"),
        (CalendarOpsEnvironment(seed=31), "missing_field", "incomplete_observation"),
    ],
)
def test_retry_agent_requests_requery_for_invalid_incomplete_and_conflicting_outputs(
    environment: object,
    fault_name: str,
    expected_reason: str,
) -> None:
    faulted = FAULTS[fault_name]().apply(environment.tool_response(), environment, Random(1))
    response = attempt_response(faulted, attempt=1, remaining=2, fingerprint=fault_name)
    decision = RetryAgent().decide(context(environment, response), response)

    assert decision.action.action_type == REQUERY_ACTION_TYPE
    assert decision.action.is_requery is True
    assert expected_reason in decision.reasons
    assert decision.metadata["retry"] is True
    assert decision.metadata["clean_tool_bypass_prevented"] is True


def test_retry_agent_detects_repeated_persistent_output_then_exhausts_safely() -> None:
    environment = FileOpsEnvironment(seed=37)
    faulted = FAULTS["schema_drift"]().apply(environment.tool_response(), environment, Random(2))
    agent = RetryAgent()

    first = attempt_response(faulted, attempt=1, remaining=2, fingerprint="same-shifted-response")
    second = attempt_response(faulted, attempt=2, remaining=1, fingerprint="same-shifted-response")
    final = attempt_response(faulted, attempt=3, remaining=0, fingerprint="same-shifted-response")
    first_decision = agent.decide(context(environment, first), first)
    second_decision = agent.decide(context(environment, second), second)
    final_decision = agent.decide(context(environment, final), final)

    assert first_decision.action.is_requery
    assert second_decision.action.is_requery
    assert "repeated_response" in second_decision.reasons
    assert "persistent_fault_suspected" in second_decision.reasons
    assert final_decision.action.abstain
    assert final_decision.action.reason == "requery_exhausted"
    assert final_decision.metadata["safe_abstention"] is True
    assert final_decision.metadata["persistent_fault_suspected"] is True


def test_retry_agent_acts_when_a_later_shifted_observation_recovers() -> None:
    environment = FileOpsEnvironment(seed=39)
    faulted = FAULTS["schema_drift"]().apply(environment.tool_response(), environment, Random(3))
    first = attempt_response(faulted, attempt=1, remaining=2, fingerprint="invalid")
    recovered = attempt_response(environment.tool_response(), attempt=2, remaining=1, fingerprint="recovered")
    agent = RetryAgent()

    assert agent.decide(context(environment, first), first).action.is_requery
    recovered_decision = agent.decide(context(environment, recovered), recovered)

    assert recovered_decision.action.is_requery is False
    assert recovered_decision.action.abstain is False
    assert recovered_decision.metadata["retry"] is False


def persistent_schema_config(*, agent: str = "retry", requery_attempts: int = 2) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": [agent],
        "faults": ["schema_drift"],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "monitor_policy": "record",
        "requery_attempts": requery_attempts,
    }
    if agent != "retry":
        config["plugin_references"] = [
            {
                "kind": "agent",
                "name": agent,
                "version": "test",
                "contract_version": "2",
                "entry_point": f"tests:{agent}",
            }
        ]
    return config


def test_runner_routes_every_requery_through_the_same_persistent_shifted_channel() -> None:
    episodes = RunCoordinator(ExperimentSpec.from_config(persistent_schema_config(), seed=41)).run()
    episode = next(item for item in episodes if item.fault.name == "schema_drift")
    policy_step = episode.metadata["step_trace"][0]
    evaluator_attempts = episode.metadata["evaluator_trace"][0]["tool_attempts"]

    assert episode.metadata["requery_contract"] == TOOL_REQUERY_CONTRACT
    assert episode.metadata["total_tool_calls"] == 3
    assert episode.metadata["total_requeries"] == 2
    assert episode.metadata["total_tool_cost_units"] == 3
    assert policy_step["attempt_count"] == 3
    assert [attempt["decision_type"] for attempt in policy_step["attempts"]] == [
        REQUERY_ACTION_TYPE,
        REQUERY_ACTION_TYPE,
        "abstain",
    ]
    assert all("response_provenance" not in attempt for attempt in policy_step["attempts"])
    assert "faults" not in policy_step["tool_response"]["observation"]["metadata"]
    assert "fault_schedule_provenance" not in policy_step["tool_response"]["observation"]["metadata"]

    response_hashes = {attempt["visible_response_hash"] for attempt in evaluator_attempts}
    schedule_ids = {
        evaluation["schedule_id"]
        for attempt in evaluator_attempts
        for evaluation in attempt["response_provenance"]["schedule_evaluations"]
    }
    assert len(response_hashes) == 1
    assert schedule_ids == set(episode.fault.metadata["schedule_ids"])
    assert all(
        evaluation["active"]
        for attempt in evaluator_attempts
        for evaluation in attempt["response_provenance"]["schedule_evaluations"]
    )
    assert all(attempt["response_provenance"]["realized_faults"] for attempt in evaluator_attempts)
    assert all(attempt["response_provenance"]["clean_response_exposed"] is False for attempt in evaluator_attempts)
    assert episode.decision.action.abstain
    assert episode.decision.metadata["persistent_fault_suspected"] is True
    assert episode.metadata["state_transitions"][0]["action_type"] == "abstain"


def test_runner_enforces_requery_budget_for_an_agent_that_never_stops_requesting() -> None:
    class AlwaysRequeryAgent:
        name = "always_requery"

        def decide(self, context: ObservationContext, response: ToolResponse) -> AgentDecision:
            return AgentDecision(
                self.name,
                AgentAction(REQUERY_ACTION_TYPE, reason="always"),
                1.0,
                ["always"],
            )

    catalog = PluginCatalog(include_external=False)
    catalog.register(
        PluginDescriptor.for_factory("agent", AlwaysRequeryAgent.name, AlwaysRequeryAgent, version="test"),
        AlwaysRequeryAgent,
    )
    episode = RunCoordinator(
        ExperimentSpec.from_config(persistent_schema_config(agent=AlwaysRequeryAgent.name, requery_attempts=1)),
        catalog,
    ).run()[0]

    assert episode.metadata["total_tool_calls"] == 2
    assert episode.metadata["total_requeries"] == 1
    assert episode.decision.action.abstain
    assert episode.decision.action.reason == "requery_budget_exhausted"
    assert episode.decision.metadata["runner_enforced_requery_budget"] is True


def test_requery_action_cannot_target_or_double_as_abstention() -> None:
    with pytest.raises(ValueError, match="cannot abstain or target"):
        AgentAction(REQUERY_ACTION_TYPE, target="hidden")
    with pytest.raises(ValueError, match="cannot abstain or target"):
        AgentAction(REQUERY_ACTION_TYPE, abstain=True)


def test_requery_budget_is_semantic_identity_and_builtin_capability() -> None:
    first = ExperimentSpec.from_config(persistent_schema_config(requery_attempts=1))
    second = ExperimentSpec.from_config(persistent_schema_config(requery_attempts=2))
    first_coordinator = RunCoordinator(first)
    second_coordinator = RunCoordinator(second)
    first_coordinator.run()
    second_coordinator.run()

    assert int(IDENTITY_SCHEMA_VERSION) >= 5
    assert first_coordinator.run_id != second_coordinator.run_id
    assert first_coordinator.identity is not None
    assert first_coordinator.identity.semantic.step_semantics.maximum_requeries_per_step == 1
    retry_descriptor = PluginCatalog(include_external=False).descriptor("agent", "retry")
    assert retry_descriptor.version == "4.0.0"
    assert TOOL_REQUERY_CONTRACT in retry_descriptor.capabilities


def test_requery_traces_are_deterministic_across_worker_counts() -> None:
    config = {**persistent_schema_config(), "episodes_per_combo": 2}
    serial = RunCoordinator(ExperimentSpec.from_config(config, seed=43, workers=1)).run()
    parallel = RunCoordinator(ExperimentSpec.from_config(config, seed=43, workers=2)).run()
    serial_shifted = sorted(
        (episode.to_dict() for episode in serial if episode.fault.name == "schema_drift"),
        key=lambda episode: episode["episode_id"],
    )
    parallel_shifted = sorted(
        (episode.to_dict() for episode in parallel if episode.fault.name == "schema_drift"),
        key=lambda episode: episode["episode_id"],
    )

    assert canonical_dumps(serial_shifted) == canonical_dumps(parallel_shifted)
