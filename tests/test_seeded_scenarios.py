from __future__ import annotations

from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonical_bytes
from tool_agent_shift_benchmark.environments.calendar_ops import CalendarOpsEnvironment
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.environments.risk_ops import RiskOpsEnvironment


def _config(**changes: object) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops", "calendar_ops", "risk_ops"],
        "agents": ["naive"],
        "faults": ["normal", "missing_field"],
        "fault_severities": [1.0],
        "episodes_per_combo": 2,
        "episode_steps": 1,
        "monitor": "composite",
        "monitor_policy": "record",
    }
    config.update(changes)
    return config


def _scenario_bytes(environment: type, seed: int, index: int = 0) -> bytes:
    return canonical_bytes(environment(seed=seed, scenario_index=index).hidden_ground_truth())


def test_identical_inputs_produce_byte_identical_scenarios() -> None:
    for environment in (FileOpsEnvironment, CalendarOpsEnvironment, RiskOpsEnvironment):
        assert _scenario_bytes(environment, 9281) == _scenario_bytes(environment, 9281)


def test_different_seeds_change_meaningful_environment_properties() -> None:
    for environment in (FileOpsEnvironment, CalendarOpsEnvironment, RiskOpsEnvironment):
        variants = {_scenario_bytes(environment, seed) for seed in range(5)}
        assert len(variants) >= 4


def test_agent_and_shift_selection_do_not_change_base_scenario_stream() -> None:
    baseline = ExperimentPlanner(ExperimentSpec.from_config(_config(), seed=17)).canonical_plan()
    changed = ExperimentPlanner(
        ExperimentSpec.from_config(
            _config(agents=["conservative"], faults=["schema_drift"], fault_severities=[0.5]),
            seed=17,
        )
    ).canonical_plan()

    baseline_seeds = {(item.environment, item.scenario_index): item.seed for item in baseline}
    changed_seeds = {(item.environment, item.scenario_index): item.seed for item in changed}
    assert changed_seeds == baseline_seeds


def test_worker_count_does_not_change_scenarios_or_stream_records() -> None:
    serial_spec = ExperimentSpec.from_config(_config(faults=["normal"]), seed=31, workers=1)
    parallel_spec = ExperimentSpec.from_config(_config(faults=["normal"]), seed=31, workers=4)
    serial_plan = ExperimentPlanner(serial_spec).canonical_plan()
    parallel_plan = ExperimentPlanner(parallel_spec).canonical_plan()

    assert [item.seed_streams for item in serial_plan] == [item.seed_streams for item in parallel_plan]
    serial = RunCoordinator(serial_spec).run()
    parallel = RunCoordinator(parallel_spec).run()
    assert [episode.metadata["seed_streams"] for episode in serial] == [
        episode.metadata["seed_streams"] for episode in parallel
    ]
    assert all(episode.metadata["scenario_generator"]["version"] == "2.0.0" for episode in serial)
