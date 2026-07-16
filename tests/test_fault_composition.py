from __future__ import annotations

from tests.shift_context_helpers import shift_context

from tool_agent_shift_benchmark.core.fault_composition import (
    FAULT_COMPOSITION_CONTRACT,
    compose_fault_chain,
)
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_dumps
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.faults.compound import CompoundShiftFault
from tool_agent_shift_benchmark.faults.latency_spike import LatencySpikeFault
from tool_agent_shift_benchmark.faults.missing_field import MissingFieldFault
from tool_agent_shift_benchmark.faults.schema_drift import SchemaDriftFault
from tool_agent_shift_benchmark.faults.stale_observation import StaleObservationFault


def _first_composition(episode):
    return episode.metadata["evaluator_trace"][0]["tool_attempts"][0]["response_provenance"]["fault_compositions"][0]


def test_schema_then_missing_is_distinct_from_missing_then_schema() -> None:
    environment = FileOpsEnvironment(seed=101)
    clean = environment.tool_response()
    forward, forward_record = compose_fault_chain(
        clean,
        shift_context(environment, clean, 0),
        (("schema_drift", SchemaDriftFault(1.0), 11), ("missing_field", MissingFieldFault(1.0), 13)),
        schedule_id="forward",
        scheduled_severity=1.0,
    )
    reverse, reverse_record = compose_fault_chain(
        clean,
        shift_context(environment, clean, 0),
        (("missing_field", MissingFieldFault(1.0), 13), ("schema_drift", SchemaDriftFault(1.0), 11)),
        schedule_id="reverse",
        scheduled_severity=1.0,
    )

    assert forward_record.explicit_order == ("schema_drift", "missing_field")
    assert reverse_record.explicit_order == ("missing_field", "schema_drift")
    assert forward_record.canonicalization == reverse_record.canonicalization == "none_order_preserved"
    assert forward_record.final_response_hash != reverse_record.final_response_hash
    assert forward.observation.data != reverse.observation.data
    assert forward.observation.metadata["faults"][1]["realized_magnitude"] == 0.0
    assert reverse.observation.metadata["faults"][0]["realized_magnitude"] > 0.0


def test_latency_and_staleness_compose_with_a_complete_hash_chain() -> None:
    environment = FileOpsEnvironment(seed=103)
    clean = environment.tool_response()
    shifted, record = compose_fault_chain(
        clean,
        shift_context(environment, clean, 0),
        (("latency_spike", LatencySpikeFault(0.8), 17), ("stale_observation", StaleObservationFault(0.8), 19)),
        schedule_id="latency-staleness",
        scheduled_severity=0.8,
    )

    assert record.contract == FAULT_COMPOSITION_CONTRACT
    assert shifted.latency_ms > clean.latency_ms
    assert shifted.observation.timestamp < clean.observation.timestamp
    assert record.component_history[0].input_response_hash == record.initial_response_hash
    assert record.component_history[0].output_response_hash == record.component_history[1].input_response_hash
    assert record.component_history[-1].output_response_hash == record.final_response_hash
    assert all(component.effect_hash.startswith("effect_") for component in record.component_history)


def test_component_application_is_independently_reproducible() -> None:
    def execute():
        environment = FileOpsEnvironment(seed=107)
        response = environment.tool_response()
        return compose_fault_chain(
            response,
            shift_context(environment, response, 0),
            (
                ("stale_observation", StaleObservationFault(0.9), 23),
                ("latency_spike", LatencySpikeFault(0.9), 29),
            ),
            schedule_id="repeatable",
            scheduled_severity=0.9,
        )

    first_response, first_record = execute()
    second_response, second_record = execute()

    assert canonical_dumps(first_response) == canonical_dumps(second_response)
    assert first_record == second_record


def test_matched_singles_and_compound_share_component_seeds_and_realizations() -> None:
    config = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["stale_observation", "latency_spike"],
        "shift_chains": [
            ["stale_observation"],
            ["latency_spike"],
            ["stale_observation", "latency_spike"],
        ],
        "fault_severities": [0.8],
        "episodes_per_combo": 1,
        "episode_steps": 2,
        "monitor_policy": "record",
    }
    episodes = RunCoordinator(ExperimentSpec.from_config(config, seed=109)).run()
    by_fault = {episode.fault.name: episode for episode in episodes}
    stale = _first_composition(by_fault["stale_observation"])
    latency = _first_composition(by_fault["latency_spike"])
    compound = _first_composition(by_fault["stale_observation+latency_spike"])

    assert stale["initial_response_hash"] == compound["initial_response_hash"]
    assert stale["component_history"][0]["rng_seed"] == compound["component_history"][0]["rng_seed"]
    assert stale["final_response_hash"] == compound["component_history"][0]["output_response_hash"]
    assert latency["component_history"][0]["rng_seed"] == compound["component_history"][1]["rng_seed"]
    assert all(
        attempt["response_provenance"]["fault_compositions"]
        for step in by_fault["stale_observation+latency_spike"].metadata["evaluator_trace"]
        for attempt in step["tool_attempts"]
    )
    assert FAULT_COMPOSITION_CONTRACT not in canonical_dumps(
        by_fault["stale_observation+latency_spike"].metadata["step_trace"]
    )


def test_legacy_compound_is_an_explicitly_deprecated_alias() -> None:
    assert CompoundShiftFault.deprecated is True
    assert CompoundShiftFault.replacement == (
        "stale_observation",
        "missing_field",
        "conflicting_tool_output",
        "latency_spike",
    )
