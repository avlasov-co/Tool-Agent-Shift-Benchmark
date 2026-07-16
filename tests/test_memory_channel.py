from __future__ import annotations

from random import Random

import pytest

from tool_agent_shift_benchmark.core.memory import (
    MEMORY_CORRUPTION_TYPES,
    POLICY_MEMORY_CONTRACT,
    MemoryWrite,
    PolicyMemoryChannel,
    corrupt_memory_view,
)
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_dumps


def memory_config(*, agent: str, schedule: dict[str, object] | None = None) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": [agent],
        "faults": ["corrupted_memory"],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "monitor_policy": "record",
        "requery_attempts": 1,
    }
    if schedule is not None:
        config["fault_schedules"] = [schedule]
    return config


def shifted_episode(config: dict[str, object]):
    episodes = RunCoordinator(ExperimentSpec.from_config(config, seed=811)).run()
    return next(episode for episode in episodes if episode.fault.name == "corrupted_memory")


def test_policy_memory_persists_clean_writes_and_keeps_immutable_snapshots() -> None:
    channel = PolicyMemoryChannel()
    empty = channel.read(step=0, stateful_agent=True)
    receipt = channel.write(
        [MemoryWrite("last_observation", {"visible_response_hash": "visible_a"}, "file_listing", 1000, 0.9)],
        step=0,
    )[0]
    persisted = channel.read(step=1, stateful_agent=True)

    assert empty.policy_view is not None and empty.policy_view.entries == ()
    assert persisted.policy_view is not None
    assert persisted.policy_view.get("last_observation") == receipt
    assert persisted.policy_view.revision == 1
    assert empty.policy_view.entries == ()
    assert persisted.pristine_reference_hash == channel.pristine_reference_hash()
    with pytest.raises(Exception):
        receipt.confidence = 0.1  # type: ignore[misc]


@pytest.mark.parametrize("corruption_type", MEMORY_CORRUPTION_TYPES)
def test_each_memory_corruption_family_changes_only_the_policy_view(corruption_type: str) -> None:
    channel = PolicyMemoryChannel()
    channel.write(
        [MemoryWrite("last_observation", {"visible_response_hash": "visible_a"}, "file_listing", 1000)],
        step=0,
    )
    pristine = channel.read(step=1, stateful_agent=True)
    assert pristine.policy_view is not None
    corrupted, records = corrupt_memory_view(
        pristine.policy_view,
        severity=1.0,
        rng=Random(7),
        current_step=1,
        corruption_types=(corruption_type,),
    )
    reread = channel.read(step=1, stateful_agent=True)

    assert [record.corruption_type for record in records] == [corruption_type]
    assert records[0].target == "last_observation"
    assert records[0].before_hash
    assert corrupted.view_hash != pristine.policy_view.view_hash
    assert reread.policy_view == pristine.policy_view


def test_severity_selects_corruption_count_and_zero_is_a_clean_read() -> None:
    channel = PolicyMemoryChannel()
    channel.write([MemoryWrite("k", {"value": 1}, "tool", 10)], step=0)
    clean = channel.read(step=1, stateful_agent=True)
    assert clean.policy_view is not None

    unchanged, no_records = corrupt_memory_view(clean.policy_view, severity=0.0, rng=Random(3), current_step=1)
    _maximum, maximum_records = corrupt_memory_view(clean.policy_view, severity=1.0, rng=Random(3), current_step=1)

    assert unchanged == clean.policy_view
    assert no_records == ()
    assert {record.corruption_type for record in maximum_records} == set(MEMORY_CORRUPTION_TYPES)


def test_stateless_agent_is_unaffected_by_scheduled_memory_corruption() -> None:
    episodes = RunCoordinator(ExperimentSpec.from_config(memory_config(agent="naive"), seed=811)).run()
    clean = next(episode for episode in episodes if episode.fault.name == "normal")
    shifted = next(episode for episode in episodes if episode.fault.name == "corrupted_memory")

    clean_steps = clean.metadata["step_trace"]
    shifted_steps = shifted.metadata["step_trace"]
    assert [step["decision"]["action"] for step in shifted_steps] == [
        step["decision"]["action"] for step in clean_steps
    ]
    assert [record.execution_result for record in shifted.action_records] == [
        record.execution_result for record in clean.action_records
    ]
    assert all(step["memory"]["view"] is None for step in shifted_steps)
    assert shifted.metadata["stateful_policy_memory"] is False


def test_stateful_agent_detects_corruption_ignores_it_and_overwrites_from_current_observation() -> None:
    episode = shifted_episode(memory_config(agent="retry"))
    steps = episode.metadata["step_trace"]
    evaluator_steps = episode.metadata["evaluator_trace"]

    assert episode.metadata["policy_memory_contract"] == POLICY_MEMORY_CONTRACT
    assert episode.metadata["stateful_policy_memory"] is True
    assert steps[0]["memory"]["view"]["revision"] == 0
    assert any(operation["operation"] == "ignore" for step in steps[1:] for operation in step["memory_operations"])
    assert any(operation["operation"] == "overwrite" for step in steps[1:] for operation in step["memory_operations"])
    assert all(step["memory_writes"] for step in steps)
    assert any(
        attempt["response_provenance"]["memory"]["corruptions"]
        for step in evaluator_steps[1:]
        for attempt in step["tool_attempts"]
    )
    policy_payload = canonical_dumps(steps)
    assert "pristine_reference_hash" not in policy_payload
    assert "corruption_type" not in policy_payload
    assert "hidden_ground_truth" not in policy_payload


def test_memory_corruption_follows_transient_schedule_boundaries() -> None:
    schedule = {
        "shift_chain": ["corrupted_memory"],
        "configured_severity": 1.0,
        "onset_step": 1,
        "duration": 1,
        "persistence": "transient",
        "recurrence": None,
        "per_step_severity": [1.0],
    }
    episode = shifted_episode(memory_config(agent="retry", schedule=schedule))
    evaluator_steps = episode.metadata["evaluator_trace"]
    corruption_counts = [
        sum(len(attempt["response_provenance"]["memory"]["corruptions"]) for attempt in step["tool_attempts"])
        for step in evaluator_steps
    ]

    assert corruption_counts[0] == 0
    assert corruption_counts[1] > 0
    assert all(count == 0 for count in corruption_counts[2:])
