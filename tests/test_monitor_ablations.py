from __future__ import annotations

import pytest

from tool_agent_shift_benchmark.core.config_schema import ConfigValidationError, parse_config_data
from tool_agent_shift_benchmark.core.monitoring import MONITOR_MODE_ORDER, monitor_composition
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.metrics.aggregation import aggregate
from tool_agent_shift_benchmark.monitors.composite import CompositeMonitor


def ablation_config(modes: list[str] | None = None) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["stale_observation"],
        "fault_severities": [1.0],
        "episodes_per_combo": 1,
        "episode_steps": 2,
        "monitor_policy": "gate",
    }
    if modes is not None:
        config["monitor_modes"] = modes
    return config


def test_monitor_modes_expand_every_treatment_in_deterministic_order() -> None:
    planner = ExperimentPlanner(ExperimentSpec.from_config(ablation_config(list(reversed(MONITOR_MODE_ORDER)))))
    plan = planner.plan()

    assert len(plan) == 10
    assert [item.identity.monitor_mode for item in plan] == [mode for mode in MONITOR_MODE_ORDER for _ in range(2)]
    assert len({item.episode_id for item in plan}) == len(plan)
    assert len({item.scenario_pair_id for item in plan}) == 1
    assert len({item.seed_streams.agent_behavior for item in plan}) == 1
    assert planner.identity.semantic.monitor_modes == MONITOR_MODE_ORDER


def test_monitor_mode_request_order_does_not_change_identity_or_plan_order() -> None:
    forward = ExperimentPlanner(ExperimentSpec.from_config(ablation_config(["no_monitor", "full_composite_monitor"])))
    reverse = ExperimentPlanner(ExperimentSpec.from_config(ablation_config(["full_composite_monitor", "no_monitor"])))

    assert forward.run_id == reverse.run_id
    assert [item.episode_id for item in forward.plan()] == [item.episode_id for item in reverse.plan()]


@pytest.mark.parametrize(
    ("mode", "components"),
    [
        ("no_monitor", ()),
        ("schema_only", ("schema_monitor",)),
        ("schema_plus_freshness", ("schema_monitor", "freshness_monitor")),
        (
            "schema_plus_freshness_plus_consistency",
            ("schema_monitor", "freshness_monitor", "consistency_monitor"),
        ),
        (
            "full_composite_monitor",
            (
                "schema_monitor",
                "freshness_monitor",
                "consistency_monitor",
                "constraint_monitor",
                "risk_monitor",
            ),
        ),
    ],
)
def test_named_monitor_compositions_are_exact_and_ordered(mode: str, components: tuple[str, ...]) -> None:
    descriptor = monitor_composition(mode)
    runtime = CompositeMonitor(mode=mode)

    assert descriptor.components == components
    assert tuple(monitor.name for monitor in runtime.monitors) == components


def test_no_monitor_is_a_real_allowing_treatment_with_no_child_checks() -> None:
    episodes = RunCoordinator(ExperimentSpec.from_config(ablation_config(["no_monitor"]), seed=127)).run()
    shifted = next(episode for episode in episodes if episode.fault.name == "stale_observation")

    assert shifted.metadata["monitor_mode"] == "no_monitor"
    assert shifted.metadata["oversight_mode"] == "gate"
    assert shifted.monitor_decisions
    assert all(decision.monitor_name == "no_monitor" for decision in shifted.monitor_decisions)
    assert all(decision.allow_action for decision in shifted.monitor_decisions)
    assert all(decision.metadata["children"] == [] for decision in shifted.monitor_decisions)


def test_unknown_and_duplicate_monitor_modes_are_rejected_at_exact_paths() -> None:
    with pytest.raises(ConfigValidationError) as unknown:
        parse_config_data(ablation_config(["unknown"]))
    with pytest.raises(ConfigValidationError) as duplicate:
        parse_config_data(ablation_config(["schema_only", "schema_only"]))

    assert unknown.value.path == "$.monitor_modes[0]"
    assert duplicate.value.path == "$.monitor_modes[1]"


def test_analysis_groups_monitor_treatments_independently() -> None:
    episodes = RunCoordinator(
        ExperimentSpec.from_config(
            ablation_config(["no_monitor", "schema_plus_freshness", "full_composite_monitor"]),
            seed=131,
        )
    ).run()
    rows = aggregate(episodes)

    assert len(rows) == 6
    assert {str(row["monitor_mode"]) for row in rows} == {
        "no_monitor",
        "schema_plus_freshness",
        "full_composite_monitor",
    }
    assert {str(row["oversight_mode"]) for row in rows} == {"gate"}
    assert all(float(row["episodes"]) == 1.0 for row in rows)
