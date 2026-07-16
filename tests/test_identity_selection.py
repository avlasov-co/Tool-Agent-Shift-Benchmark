from __future__ import annotations

import json
from pathlib import Path

import pytest

from tool_agent_shift_benchmark.cli import _plan_command as plan_command
from tool_agent_shift_benchmark.cli import build_parser
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.orchestration import (
    ExperimentPlanner,
    ExperimentSpec,
    RunCoordinator,
    UnknownEpisodeSelectionError,
)


def base_config(episodes: int = 5) -> dict[str, object]:
    return {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["normal"],
        "episodes_per_combo": episodes,
    }


def planner(config: dict[str, object], **overrides: object) -> ExperimentPlanner:
    catalog = PluginCatalog(include_external=False)
    return ExperimentPlanner(ExperimentSpec.from_config(config, seed=11, **overrides), catalog)


def test_copied_episode_id_filters_the_canonical_complete_plan() -> None:
    complete = planner(base_config(3))
    complete_plan = complete.plan()
    target = complete_plan[1].episode_id

    filtered = planner(base_config(3), episode_ids=[target])

    # Identity v2 intentionally changes scientific IDs, while retaining the
    # legacy complete-plan run ID as explicit compatibility provenance.
    assert complete.legacy_run_id == "run_dfb379c348b1cb76"
    assert filtered.run_id == complete.run_id
    assert [item.episode_id for item in filtered.plan()] == [target]


def test_multiple_ids_and_selector_order_keep_canonical_order() -> None:
    complete = planner(base_config()).plan()
    requested = [complete[3].episode_id, complete[1].episode_id]

    first = planner(base_config(), episode_ids=requested).plan()
    second = planner(base_config(), episode_ids=list(reversed(requested))).plan()

    expected = [complete[1].episode_id, complete[3].episode_id]
    assert [item.episode_id for item in first] == expected
    assert [item.episode_id for item in second] == expected


def test_scenario_and_combined_filters_do_not_change_identity() -> None:
    complete = planner(base_config())
    target = complete.plan()[2]
    indexed = planner(base_config(), scenario_indices=[2])
    combined = planner(base_config(), scenario_indices=[2], episode_ids=[target.episode_id])

    assert indexed.run_id == combined.run_id == complete.run_id
    assert [item.episode_id for item in indexed.plan()] == [target.episode_id]
    assert [item.episode_id for item in combined.plan()] == [target.episode_id]


def test_unknown_id_is_distinct_from_an_empty_selection() -> None:
    with pytest.raises(UnknownEpisodeSelectionError, match="ep_unknown"):
        planner(base_config(), episode_ids=["ep_unknown"]).plan()

    complete = planner(base_config())
    target = complete.plan()[1].episode_id
    assert planner(base_config(), scenario_indices=[4], episode_ids=[target]).plan() == []
    assert planner(base_config(), selection_limit=0).plan() == []


def test_pagination_and_worker_partitions_are_post_identity_selectors() -> None:
    complete_planner = planner(base_config())
    complete = complete_planner.plan()
    page = planner(base_config(), selection_offset=1, selection_limit=2)
    partition_zero = planner(base_config(), partition_index=0, partition_count=2)
    partition_one = planner(base_config(), partition_index=1, partition_count=2)

    assert page.run_id == partition_zero.run_id == partition_one.run_id == complete_planner.run_id
    assert page.plan() == complete[1:3]
    assert partition_zero.plan() == complete[::2]
    assert partition_one.plan() == complete[1::2]
    assert set(partition_zero.plan()).isdisjoint(partition_one.plan())
    assert sorted(partition_zero.plan() + partition_one.plan(), key=complete.index) == complete


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"selection_offset": -1}, "selection_offset"),
        ({"selection_limit": -1}, "selection_limit"),
        ({"workers": 0}, "workers"),
        ({"scenario_indices": [-1]}, "scenario_indices"),
        ({"partition_index": 0}, "provided together"),
        ({"partition_index": 2, "partition_count": 2}, "partition_index"),
        ({"episode_ids": ["ep_a"], "replay_episode_ids": ["ep_a"]}, "cannot be combined"),
    ],
)
def test_invalid_selectors_fail_before_planning(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        planner(base_config(), **overrides)


def test_resume_and_replay_retain_canonical_episode_ids() -> None:
    config = base_config(3)
    catalog = PluginCatalog(include_external=False)
    complete_planner = planner(config)
    plan = complete_planner.plan()

    resumed = RunCoordinator(ExperimentSpec.from_config(config, seed=11), catalog).run(
        {plan[0].episode_id, plan[2].episode_id}
    )
    replayed = RunCoordinator(
        ExperimentSpec.from_config(config, seed=11, replay_episode_ids=[plan[1].episode_id]),
        catalog,
    ).run()
    serialized = Episode.from_dict(json.loads(json.dumps(replayed[0].to_dict())))

    assert [episode.episode_id for episode in resumed] == [plan[1].episode_id]
    assert [episode.episode_id for episode in replayed] == [plan[1].episode_id]
    assert serialized.episode_id == plan[1].episode_id
    with pytest.raises(UnknownEpisodeSelectionError, match="unknown resume"):
        RunCoordinator(ExperimentSpec.from_config(config, seed=11), catalog).run({"ep_unknown"})


def test_selectors_embedded_in_config_are_operational() -> None:
    complete = planner(base_config(3))
    target = complete.plan()[1].episode_id
    selected_config = {
        **base_config(3),
        "scenario_indices": [1],
        "episode_ids": [target],
        "selection_offset": 0,
        "selection_limit": 1,
    }
    selected = planner(selected_config)
    explicitly_cleared = planner(selected_config, scenario_indices=[], episode_ids=[], selection_limit=None)

    assert selected.run_id == complete.run_id
    assert [item.episode_id for item in selected.plan()] == [target]
    assert explicitly_cleared.run_id == complete.run_id
    assert explicitly_cleared.plan() == complete.plan()[0:1]


def test_cli_omitted_selectors_defer_to_normalized_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = {**base_config(), "seed": 11, "selection_offset": 1, "selection_limit": 2}
    config_path = tmp_path / "configured-selection.yaml"
    config_path.write_text(
        """\
schema_version: 2
environments: [file_ops]
agents: [naive]
faults: [normal]
episodes_per_combo: 5
seed: 11
selection_offset: 1
selection_limit: 2
""",
        encoding="utf-8",
    )
    args = build_parser().parse_args(["plan", "--config", str(config_path)])

    plan_command(args)
    payload = json.loads(capsys.readouterr().out)
    expected = planner(config).plan()

    assert payload["identity"]["operational"]["selection_offset"] == 1
    assert [item["episode_id"] for item in payload["matrix"]] == [item.episode_id for item in expected]


def test_cli_and_python_planning_apply_identical_selectors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "selection.yaml"
    config_path.write_text(
        "\n".join(
            [
                "environments: [file_ops]",
                "schema_version: 2",
                "agents: [naive]",
                "faults: [normal]",
                "episodes_per_combo: 5",
            ]
        ),
        encoding="utf-8",
    )
    complete = planner(base_config()).plan()
    target = complete[3].episode_id
    args = build_parser().parse_args(
        [
            "plan",
            "--config",
            str(config_path),
            "--seed",
            "11",
            "--scenario-index",
            "3",
            "--episode-id",
            target,
            "--offset",
            "0",
            "--limit",
            "1",
        ]
    )

    plan_command(args)
    payload = json.loads(capsys.readouterr().out)
    api = planner(base_config(), scenario_indices=[3], episode_ids=[target], selection_limit=1)

    assert payload["run_id"] == api.run_id
    assert [item["episode_id"] for item in payload["matrix"]] == [item.episode_id for item in api.plan()]
