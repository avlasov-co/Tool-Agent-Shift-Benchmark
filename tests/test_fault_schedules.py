from __future__ import annotations

import pytest

from tool_agent_shift_benchmark.core.config_schema import ConfigValidationError, parse_config_data
from tool_agent_shift_benchmark.core.fault_schedule import FAULT_SCHEDULE_CONTRACT, FaultSchedule
from tool_agent_shift_benchmark.core.identity import IDENTITY_SCHEMA_VERSION
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator


def schedule_config(*schedules: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["stale_observation"],
        "shift_chains": [["stale_observation"]],
        "fault_severities": [0.7],
        "fault_schedules": list(schedules),
        "episodes_per_combo": 1,
        "episode_steps": 6,
        "monitor_policy": "record",
    }


def schedule(
    *,
    onset: int = 0,
    duration: int | None = None,
    persistence: str = "persistent",
    recurrence: int | None = None,
    profile: list[float] | None = None,
) -> dict[str, object]:
    return {
        "shift_chain": ["stale_observation"],
        "configured_severity": 0.7,
        "onset_step": onset,
        "duration": duration,
        "persistence": persistence,
        "recurrence": recurrence,
        "per_step_severity": profile or [0.7],
    }


def shifted_episode(config: dict[str, object]):
    episodes = RunCoordinator(ExperimentSpec.from_config(config)).run()
    return next(episode for episode in episodes if episode.fault.name == "stale_observation")


def test_schedule_activation_supports_persistent_transient_and_intermittent_windows() -> None:
    persistent = FaultSchedule(("schema_drift",), 0.8, 2, None, "persistent", None, (0.4, 0.8))
    transient = FaultSchedule(("missing_field",), 0.5, 1, 2, "transient", None, (0.2, 0.5))
    intermittent = FaultSchedule(("stale_observation",), 1.0, 1, 2, "transient", 4, (0.3, 0.9))

    assert [persistent.severity_at(step) for step in range(5)] == [None, None, 0.4, 0.8, 0.8]
    assert [transient.severity_at(step) for step in range(5)] == [None, 0.2, 0.5, None, None]
    assert [intermittent.severity_at(step) for step in range(8)] == [
        None,
        0.3,
        0.9,
        None,
        None,
        0.3,
        0.9,
        None,
    ]
    assert intermittent.provenance(2)["contract"] == FAULT_SCHEDULE_CONTRACT
    assert intermittent.provenance(3)["active"] is False


def test_current_schedule_config_validates_timing_profiles_and_matrix_coverage() -> None:
    parsed = parse_config_data(
        schedule_config(schedule(onset=1, duration=2, persistence="transient", recurrence=4, profile=[0.2, 0.7]))
    )
    configured = parsed.fault_schedules[0]
    assert configured.onset_step == 1
    assert configured.duration == 2
    assert configured.recurrence == 4
    assert configured.per_step_severity == (0.2, 0.7)

    with pytest.raises(ConfigValidationError, match="must be greater than duration"):
        parse_config_data(schedule_config(schedule(onset=1, duration=2, persistence="transient", recurrence=2)))
    with pytest.raises(ConfigValidationError, match="cover exactly"):
        parse_config_data(
            {
                **schedule_config(schedule()),
                "fault_schedules": [
                    {
                        **schedule(),
                        "configured_severity": 0.5,
                    }
                ],
            }
        )


def test_runtime_records_late_onset_and_recovery_without_leaking_schedule_labels() -> None:
    episode = shifted_episode(schedule_config(schedule(onset=1, duration=1, persistence="transient")))
    trace = episode.metadata["evaluator_trace"]

    assert len(trace) >= 3
    assert [entry["fault_schedule_provenance"][0]["active"] for entry in trace[:3]] == [False, True, False]
    assert trace[0]["shift_provenance"] == []
    assert trace[1]["shift_provenance"]
    assert trace[2]["shift_provenance"] == []
    assert all(
        "fault_schedule_provenance" not in entry["tool_response"]["observation"]["metadata"]
        for entry in episode.metadata["step_trace"]
    )


def test_persistent_and_overlapping_schedules_are_evaluated_on_every_step() -> None:
    persistent = shifted_episode(schedule_config(schedule()))
    persistent_trace = persistent.metadata["evaluator_trace"]
    assert len(persistent_trace) > 1
    assert all(entry["fault_schedule_provenance"][0]["active"] for entry in persistent_trace)
    assert all(entry["shift_provenance"] for entry in persistent_trace)

    overlapping = shifted_episode(
        schedule_config(
            schedule(onset=0, duration=3, persistence="transient", profile=[0.2, 0.4, 0.7]),
            schedule(onset=1, duration=2, persistence="transient", profile=[0.3, 0.6]),
        )
    )
    overlap_trace = overlapping.metadata["evaluator_trace"]
    assert [item["active"] for item in overlap_trace[0]["fault_schedule_provenance"]] == [True, False]
    assert [item["active"] for item in overlap_trace[1]["fault_schedule_provenance"]] == [True, True]
    assert len(overlap_trace[1]["shift_provenance"]) == 2


def test_fault_schedule_is_part_of_semantic_and_episode_identity() -> None:
    first_spec = ExperimentSpec.from_config(schedule_config(schedule(onset=0, duration=2, persistence="transient")))
    second_spec = ExperimentSpec.from_config(schedule_config(schedule(onset=1, duration=2, persistence="transient")))
    first_planner = ExperimentPlanner(first_spec)
    second_planner = ExperimentPlanner(second_spec)
    first_item = next(item for item in first_planner.plan() if item.shift == "stale_observation")
    second_item = next(item for item in second_planner.plan() if item.shift == "stale_observation")

    assert IDENTITY_SCHEMA_VERSION == "4"
    assert first_planner.run_id != second_planner.run_id
    assert first_item.episode_id != second_item.episode_id
    assert first_item.identity.fault_schedule_ids == tuple(
        schedule_item.schedule_id for schedule_item in first_item.fault_schedules
    )
    semantic_schedule = next(
        item for item in first_planner.identity.semantic.fault_schedules if item.components[0].name != "normal"
    )
    assert semantic_schedule.onset_step == 0
    assert semantic_schedule.duration == 2
    assert semantic_schedule.schedule_id == first_item.fault_schedules[0].schedule_id
