from __future__ import annotations

from pathlib import Path

from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.serialization import read_csv, read_json
from tool_agent_shift_benchmark.metrics.aggregation import aggregate, within_scenario_deltas
from tool_agent_shift_benchmark.run_eval import run_eval


def _config(**changes: object) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops", "calendar_ops", "risk_ops"],
        "agents": ["validate_then_act"],
        "faults": ["missing_field", "schema_drift"],
        "fault_severities": [0.5, 1.0],
        "episodes_per_combo": 2,
        "episode_steps": 1,
        "monitor_policy": "record",
    }
    config.update(changes)
    return config


def test_scenario_units_expand_to_clean_and_shifted_matched_treatments() -> None:
    plan = ExperimentPlanner(ExperimentSpec.from_config(_config(), seed=41)).canonical_plan()
    pairs: dict[str, list] = {}
    for item in plan:
        pairs.setdefault(item.scenario_pair_id or "", []).append(item)

    assert len(pairs) == 6
    assert all(pair_id.startswith("pair_") for pair_id in pairs)
    for members in pairs.values():
        assert len(members) == 5
        assert sum(member.shift == "normal" for member in members) == 1
        assert len({member.scenario_spec.content_hash for member in members}) == 1
        assert len({member.seed_streams.scenario_generation for member in members}) == 1
        assert len({member.seed_streams.agent_behavior for member in members}) == 1
        assert len({member.seed_streams.execution for member in members}) == 1
        assert len({member.identity.scenario_manifest_hash for member in members}) == 1


def test_pair_identity_is_stable_across_treatment_selection_and_workers() -> None:
    clean = ExperimentPlanner(
        ExperimentSpec.from_config(_config(faults=["normal"], fault_severities=[1.0]), seed=43, workers=1)
    ).canonical_plan()
    shifted = ExperimentPlanner(
        ExperimentSpec.from_config(_config(faults=["missing_field"], fault_severities=[1.0]), seed=43, workers=4)
    ).canonical_plan()

    clean_pairs = {(item.environment, item.scenario_index, item.agent): item.scenario_pair_id for item in clean}
    shifted_pairs = {(item.environment, item.scenario_index, item.agent): item.scenario_pair_id for item in shifted}
    assert shifted_pairs == clean_pairs


def test_worker_partitions_keep_all_treatments_for_a_pair_together() -> None:
    config = _config(environments=["file_ops"], episodes_per_combo=4)
    complete = ExperimentPlanner(ExperimentSpec.from_config(config, seed=47)).plan()
    zero = ExperimentPlanner(ExperimentSpec.from_config(config, seed=47, partition_index=0, partition_count=2)).plan()
    one = ExperimentPlanner(ExperimentSpec.from_config(config, seed=47, partition_index=1, partition_count=2)).plan()

    zero_pairs = {item.scenario_pair_id for item in zero}
    one_pairs = {item.scenario_pair_id for item in one}
    assert zero_pairs.isdisjoint(one_pairs)
    assert zero_pairs | one_pairs == {item.scenario_pair_id for item in complete}
    assert all(
        {item.scenario_pair_id for item in partition}.isdisjoint({item.scenario_pair_id for item in other})
        for partition, other in ((zero, one), (one, zero))
    )


def test_pair_references_survive_checkpoint_resume_and_replay(tmp_path: Path) -> None:
    config = _config(environments=["file_ops"], faults=["missing_field"], fault_severities=[1.0])
    spec = ExperimentSpec.from_config(config, seed=53)
    plan = ExperimentPlanner(spec).plan()
    checkpoint = tmp_path / "checkpoint.json"
    manifests = tmp_path / "scenarios"
    completed = RunCoordinator(spec).run(checkpoint_path=checkpoint, scenario_manifest_dir=manifests)
    checkpoint_data = read_json(checkpoint)
    target = plan[1]
    replay_spec = ExperimentSpec.from_config(
        {**config, "scenario_manifest_path": str(manifests)},
        seed=53,
        replay_episode_ids=[target.episode_id],
    )
    replayed = RunCoordinator(replay_spec).run()
    resumed = RunCoordinator(spec).run(checkpoint_path=checkpoint)

    assert resumed == []
    assert replayed[0].scenario_pair_id == target.scenario_pair_id
    assert replayed[0].metadata["scenario_manifest"]["content_hash"] == target.scenario_spec.content_hash
    assert set(checkpoint_data["completed_scenario_pair_ids"]) == {episode.scenario_pair_id for episode in completed}


def test_within_scenario_deltas_and_unique_counts_are_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "matched.yaml"
    config_path.write_text(
        """\
schema_version: 2
environments: [file_ops]
agents: [validate_then_act]
faults: [missing_field]
fault_severities: [1.0]
episodes_per_combo: 2
episode_steps: 1
monitor_policy: record
""",
        encoding="utf-8",
    )

    store = ArtifactStore(tmp_path / "run")
    episodes = run_eval(str(config_path), seed=59, artifact_store=store)
    deltas = within_scenario_deltas(episodes)
    summary = aggregate(episodes)
    metadata = read_json(store.run_dir / "results" / "config.json")
    written = read_csv(store.run_dir / "results" / "within_scenario_deltas.csv")

    assert len(episodes) == 4
    assert len(deltas) == len(written) == 2
    assert all(row["scenario_pair_id"] for row in deltas)
    assert metadata["episodes"] == 4
    assert metadata["unique_scenarios"] == 2
    assert metadata["unique_scenario_pairs"] == 2
    assert {row["unique_scenarios"] for row in summary} == {2.0}
