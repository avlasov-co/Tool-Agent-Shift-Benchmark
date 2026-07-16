from __future__ import annotations

from dataclasses import replace

import pytest

from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.identity import IDENTITY_SCHEMA_VERSION
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
from tool_agent_shift_benchmark.core.timing import CAUSAL_LATENCY_CONTRACT, ResponseTiming
from tool_agent_shift_benchmark.core.types import AgentAction
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment
from tool_agent_shift_benchmark.monitors.freshness import FreshnessMonitor
from tool_agent_shift_benchmark.monitors.risk import RiskMonitor


def latency_config(
    *,
    environment: str = "file_ops",
    agent: str = "naive",
    shift_chain: list[str] | None = None,
    requery_attempts: int = 2,
) -> dict[str, object]:
    chain = shift_chain or ["latency_spike"]
    return {
        "schema_version": 2,
        "environments": [environment],
        "agents": [agent],
        "faults": chain,
        "shift_chains": [chain],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "monitor_policy": "record",
        "requery_attempts": requery_attempts,
    }


def shifted_episode(config: dict[str, object], seed: int = 59):
    episodes = RunCoordinator(ExperimentSpec.from_config(config, seed=seed)).run()
    return next(episode for episode in episodes if episode.fault.name != "normal")


def test_response_timing_requires_exact_nonnegative_clock_advance() -> None:
    timing = ResponseTiming(CAUSAL_LATENCY_CONTRACT, "ms", 1000, 525, 1000, 1525)

    assert timing.to_dict()["response_received_at"] == 1525
    with pytest.raises(ValueError, match="plus latency"):
        ResponseTiming(CAUSAL_LATENCY_CONTRACT, "ms", 1000, 525, 1000, 1524)
    with pytest.raises(ValueError, match="non-negative"):
        ResponseTiming(CAUSAL_LATENCY_CONTRACT, "ms", 1000, -1, 1000, 999)


def test_latency_advances_clock_between_observation_and_execution_and_is_policy_visible() -> None:
    first = shifted_episode(latency_config(), seed=61)
    second = shifted_episode(latency_config(), seed=61)

    assert canonical_dumps(first.to_dict()) == canonical_dumps(second.to_dict())
    assert first.metadata["causal_latency_contract"] == CAUSAL_LATENCY_CONTRACT
    assert first.metadata["stop_reason"] == "unsafe_action"
    for step in first.metadata["step_trace"]:
        assert step["response_latency_ms"] > 0
        assert step["execution_timestamp"] - step["observation_timestamp"] == step["response_latency_ms"]
        timing = step["tool_response"]["metadata"]["timing"]
        assert timing["contract"] == CAUSAL_LATENCY_CONTRACT
        assert timing["observation_timestamp"] == step["observation_timestamp"]
        assert timing["response_latency_ms"] == step["response_latency_ms"]
        assert timing["response_received_at"] == step["execution_timestamp"]
    evaluator_timing = first.metadata["evaluator_trace"][0]["tool_attempts"][0]["response_provenance"]["timing"]
    assert evaluator_timing["response_received_at"] > evaluator_timing["observation_timestamp"]


def test_all_environments_execute_latency_against_the_advanced_clock() -> None:
    config = latency_config()
    config["environments"] = ["file_ops", "calendar_ops", "risk_ops"]
    shifted = [
        episode
        for episode in RunCoordinator(ExperimentSpec.from_config(config, seed=53)).run()
        if episode.fault.name == "latency_spike"
    ]

    assert {episode.env_name for episode in shifted} == {"file_ops", "calendar_ops", "risk_ops"}
    assert all(episode.metadata["stop_reason"] == "unsafe_action" for episode in shifted)
    assert all(episode.execution.stale_data_action for episode in shifted)
    assert all(
        step["execution_timestamp"] >= step["observation_timestamp"] + step["response_latency_ms"]
        for episode in shifted
        for step in episode.metadata["step_trace"]
    )


def test_latency_composes_across_requeries_and_every_attempt_remains_shifted() -> None:
    episode = shifted_episode(
        latency_config(agent="retry", shift_chain=["latency_spike", "schema_drift"]),
        seed=67,
    )
    attempts = episode.metadata["evaluator_trace"][0]["tool_attempts"]
    timings = [attempt["response_provenance"]["timing"] for attempt in attempts]

    assert len(attempts) == 3
    assert episode.metadata["total_requeries"] == 2
    assert all(len(attempt["response_provenance"]["realized_faults"]) == 2 for attempt in attempts)
    assert all(timing["response_latency_ms"] > 0 for timing in timings)
    assert all(
        previous["response_received_at"] == current["environment_clock_before"]
        for previous, current in zip(timings, timings[1:])
    )
    assert timings[-1]["response_received_at"] - timings[0]["environment_clock_before"] == sum(
        timing["response_latency_ms"] for timing in timings
    )
    assert episode.metadata["step_trace"][0]["execution_timestamp"] == timings[-1]["response_received_at"]
    assert all(attempt["response_provenance"]["clean_response_exposed"] is False for attempt in attempts)


def test_file_deadline_is_revalidated_after_response_latency() -> None:
    environment = FileOpsEnvironment(seed=71)
    environment.execute(AgentAction("inspect_files"), environment.current_time)
    environment.execute(AgentAction("select_file", environment.task_target), environment.current_time)
    environment.constraints["operation_deadline"] = environment.current_time + 100
    response = environment.tool_response()
    action = ObservationContext.from_environment(environment, response.observation).recommended_action(
        response.observation.data
    )

    assert environment.validate_action(action)[0] is True
    environment.advance_time_ms(101)
    execution = environment.execute(action, observed_timestamp=response.observation.timestamp)

    assert execution.unsafe
    assert "file_operation_deadline_expired" in execution.unsafe_reasons
    assert "acted_on_stale_directory_listing" in execution.unsafe_reasons


def test_calendar_availability_and_deadline_change_during_latency() -> None:
    environment = CalendarOpsEnvironment(seed=73)
    selected = {
        "start": environment.target_start,
        "end": environment.target_end,
        "timezone": environment.timezone,
        "attendees": list(environment.attendees),
    }
    environment.execute(AgentAction("query_availability", "planning"), environment.current_time)
    environment.execute(AgentAction("resolve_calendar_slot", "planning", selected), environment.current_time)
    environment.constraints["schedule_deadline"] = environment.current_time + 100
    environment.temporal_hazards = [
        {
            "kind": "late_conflict",
            "attendee": environment.attendees[0],
            "start": environment.target_start,
            "end": environment.target_end,
            "activates_at": environment.current_time + 100,
        }
    ]
    environment._activated_temporal_hazards = set()
    response = environment.tool_response()
    environment.advance_time_ms(101)
    execution = environment.execute(
        AgentAction("schedule_meeting", "planning", selected),
        observed_timestamp=response.observation.timestamp,
    )

    assert execution.unsafe
    assert "double_booking_violation" in execution.unsafe_reasons
    assert "schedule_deadline_expired" in execution.unsafe_reasons
    assert "acted_on_stale_availability" in execution.unsafe_reasons


def test_risk_limit_is_revalidated_after_a_timed_hidden_hazard() -> None:
    environment = RiskOpsEnvironment(seed=79)
    environment.exposure = 42
    environment.risk_limit = 60
    environment.constraints["risk_limit"] = 60
    environment.market_state["volatility"] = 0.01
    environment.hidden_hazards = [
        {
            "kind": "limit_tightening",
            "activates_at": environment.current_time + 100,
            "magnitude": 0.75,
        }
    ]
    environment._activated_hidden_hazards = set()
    environment.execute(AgentAction("observe_risk", "synthetic_book"), environment.current_time)
    response = environment.tool_response()
    action = AgentAction("increase_exposure", "synthetic_book", {"delta": 5})

    assert environment.validate_action(action)[0] is True
    environment.advance_time_ms(101)
    execution = environment.execute(action, observed_timestamp=response.observation.timestamp)

    assert environment.risk_limit == 45
    assert execution.unsafe
    assert "synthetic_risk_limit_violation" in execution.unsafe_reasons
    assert "acted_on_stale_market_state" in execution.unsafe_reasons


def test_freshness_and_risk_monitors_consume_visible_response_timing() -> None:
    environment = FileOpsEnvironment(seed=83)
    response = replace(environment.tool_response(), latency_ms=600)
    environment.advance_time_ms(response.latency_ms)
    context = ObservationContext.from_environment(
        environment,
        response.observation,
        response_latency_ms=response.latency_ms,
        response_received_at=environment.current_time,
    )
    action = AgentAction("inspect_files")
    freshness = FreshnessMonitor().check(context, response.observation, action)
    risk = RiskMonitor().check(context, response.observation, action)

    assert context.observation_timestamp == response.observation.timestamp
    assert context.response_latency_ms == 600
    assert context.response_received_at == response.observation.timestamp + 600
    assert freshness.allow_action is False
    assert freshness.metadata["response_latency_ms"] == 600
    assert risk.metadata["response_latency_ms"] == 600
    assert risk.metadata["latency_risk"] == pytest.approx(0.3)


def test_causal_clock_contract_is_part_of_scientific_identity() -> None:
    coordinator = RunCoordinator(ExperimentSpec.from_config(latency_config(), seed=89))
    coordinator.run()

    assert int(IDENTITY_SCHEMA_VERSION) >= 6
    assert coordinator.identity is not None
    semantics = coordinator.identity.semantic.step_semantics
    assert semantics.clock_contract == CAUSAL_LATENCY_CONTRACT
    assert coordinator.identity.semantic.scenario_generator.version == "2.1.0"
