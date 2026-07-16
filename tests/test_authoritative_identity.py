from __future__ import annotations

import json
from pathlib import Path

import pytest

from tool_agent_shift_benchmark.analysis.run_pairwise_compounds import _plan_fault_combo, _run_fault_combo
from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.contracts import IdentityMismatchError, PluginDescriptor
from tool_agent_shift_benchmark.core.episode import Episode
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment


def base_config(agent: str = "naive", environment: str = "file_ops") -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": [environment],
        "agents": [agent],
        "faults": ["normal"],
        "fault_severities": [1.0],
        "episodes_per_combo": 3,
        "episode_steps": 1,
        "monitor": "composite",
        "monitor_policy": "gate",
    }
    references = []
    if agent not in {"naive", "retry", "validate_then_act", "conservative", "offline_llm_fixture"}:
        references.append(
            {
                "kind": "agent",
                "name": agent,
                "version": "test",
                "contract_version": "1",
                "entry_point": f"tests:{agent}",
            }
        )
    if environment not in {"file_ops", "calendar_ops", "risk_ops"}:
        references.append(
            {
                "kind": "environment",
                "name": environment,
                "version": "test",
                "contract_version": "1",
                "entry_point": f"tests:{environment}",
            }
        )
    if references:
        config["plugin_references"] = references
    return config


def test_planner_identity_is_preserved_in_completed_runtime_records() -> None:
    catalog = PluginCatalog(include_external=False)
    spec = ExperimentSpec.from_config(base_config(), seed=19)
    planner = ExperimentPlanner(spec, catalog)

    episodes = RunCoordinator(spec, catalog).run()

    assert [episode.episode_id for episode in episodes] == sorted(item.episode_id for item in planner.plan())
    by_id = {item.episode_id: item for item in planner.plan()}
    for episode in episodes:
        planned = by_id[episode.episode_id].identity
        assert episode.run_id == planned.run_id
        assert episode.scenario_id == planned.scenario_id
        assert episode.seed == planned.scenario_seed
        assert episode.scenario_pair_id == planned.scenario_pair_id
        assert episode.planned_identity == planned.to_dict()


def test_faulty_environment_descriptor_becomes_structured_identity_error(tmp_path: Path) -> None:
    class FaultyDescriptorEnvironment(FileOpsEnvironment):
        name = "faulty_environment"

        def reset(self, seed: int, scenario_index: int = 0) -> None:
            super().reset(seed, scenario_index)
            self.scenario_id = f"faulty_environment_scenario_{scenario_index}"

        def runtime_descriptor(self) -> PluginDescriptor:
            return PluginDescriptor("environment", self.name, version="wrong-version")

    catalog = PluginCatalog(include_external=False)
    catalog.register(
        PluginDescriptor("environment", "faulty_environment", version="planned-version"),
        FaultyDescriptorEnvironment,
    )
    spec = ExperimentSpec.from_config(
        {**base_config(environment="faulty_environment"), "episodes_per_combo": 1},
        seed=5,
    )
    planned = ExperimentPlanner(spec, catalog).plan()[0]
    checkpoint = tmp_path / "checkpoint.json"
    coordinator = RunCoordinator(spec, catalog)

    assert coordinator.run(checkpoint_path=checkpoint) == []
    error = coordinator.errors[0]
    saved = json.loads(checkpoint.read_text(encoding="utf-8"))["errors"][0]

    assert error.episode_id == planned.episode_id
    assert error.phase == "environment_descriptor"
    assert error.field == "plugin_descriptor"
    assert error.expected["version"] == "planned-version"
    assert error.actual["version"] == "wrong-version"
    assert error.plugin_descriptor["name"] == "faulty_environment"
    assert saved["episode_id"] == planned.episode_id
    assert saved["expected"] == error.expected
    assert saved["actual"] == error.actual


def test_faulty_plugin_return_identity_is_rejected() -> None:
    class FaultyAgent:
        name = "faulty_agent"

        def decide(self, context, response):
            return AgentDecision("different_agent", AgentAction("abstain", abstain=True), 1.0)

    catalog = PluginCatalog(include_external=False)
    catalog.register(PluginDescriptor("agent", "faulty_agent", version="test"), FaultyAgent)
    spec = ExperimentSpec.from_config(
        {**base_config(agent="faulty_agent"), "episodes_per_combo": 1},
        seed=6,
    )
    planned = ExperimentPlanner(spec, catalog).plan()[0]
    coordinator = RunCoordinator(spec, catalog)

    assert coordinator.run() == []
    error = coordinator.errors[0]
    assert error.episode_id == planned.episode_id
    assert error.phase == "agent_decision"
    assert error.field == "decision.agent_name"
    assert error.expected == "faulty_agent"
    assert error.actual == "different_agent"


def test_completed_skipped_resumed_replayed_failed_and_serialized_ids_are_stable(tmp_path: Path) -> None:
    catalog = PluginCatalog(include_external=False)
    spec = ExperimentSpec.from_config(base_config(), seed=23)
    plan = ExperimentPlanner(spec, catalog).plan()
    completed = RunCoordinator(spec, catalog).run()
    checkpoint = tmp_path / "checkpoint.json"
    manifest_dir = tmp_path / "scenarios"
    RunCoordinator(spec, catalog).run(scenario_manifest_dir=manifest_dir)

    skipped = RunCoordinator(spec, catalog).run({plan[0].episode_id}, checkpoint_path=checkpoint)
    resumed = RunCoordinator(spec, catalog).run(checkpoint_path=checkpoint)
    replayed = RunCoordinator(
        ExperimentSpec.from_config(
            {**base_config(), "scenario_manifest_path": str(manifest_dir)},
            seed=23,
            replay_episode_ids=[plan[1].episode_id],
        ),
        catalog,
    ).run()
    restored = Episode.from_dict(json.loads(json.dumps(replayed[0].to_dict())))
    checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))

    assert {episode.episode_id for episode in completed} == {item.episode_id for item in plan}
    assert {episode.episode_id for episode in skipped} == {plan[1].episode_id, plan[2].episode_id}
    assert resumed == []
    assert checkpoint_payload["run_id"] == plan[0].run_id
    assert set(checkpoint_payload["completed_episode_ids"]) == {item.episode_id for item in plan}
    assert replayed[0].episode_id == plan[1].episode_id
    assert restored.episode_id == plan[1].episode_id
    assert restored.planned_identity["episode_id"] == plan[1].episode_id


def test_checkpoint_from_another_run_fails_before_rewrite(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    original = {"run_id": "run_wrong", "completed_episode_ids": [], "errors": []}
    checkpoint.write_text(json.dumps(original), encoding="utf-8")
    coordinator = RunCoordinator(ExperimentSpec.from_config(base_config(), seed=29))

    with pytest.raises(IdentityMismatchError) as raised:
        coordinator.run(checkpoint_path=checkpoint)

    assert raised.value.phase == "checkpoint_identity"
    assert raised.value.expected.startswith("run_")
    assert raised.value.actual == "run_wrong"
    assert json.loads(checkpoint.read_text(encoding="utf-8")) == original


def test_pairwise_planner_owns_pair_seed_and_episode_ids() -> None:
    common = {
        "env_name": "file_ops",
        "agent_name": "naive",
        "severity": 1.0,
        "episodes_per_combo": 2,
        "seed": 31,
    }
    clean_plan = _plan_fault_combo(fault_names=(), **common)
    pair_plan = _plan_fault_combo(fault_names=("missing_field", "schema_drift"), **common)
    pair_episodes = _run_fault_combo(fault_names=("missing_field", "schema_drift"), **common)

    assert [item.scenario_pair_id for item in clean_plan] == [item.scenario_pair_id for item in pair_plan]
    assert [item.scenario_seed for item in clean_plan] == [item.scenario_seed for item in pair_plan]
    assert [episode.episode_id for episode in pair_episodes] == [item.episode_id for item in pair_plan]
    assert [episode.scenario_pair_id for episode in pair_episodes] == [item.scenario_pair_id for item in pair_plan]
    assert [episode.seed for episode in pair_episodes] == [item.scenario_seed for item in pair_plan]


def test_serialized_planned_identity_disagreement_is_not_silently_recomputed() -> None:
    episode = RunCoordinator(ExperimentSpec.from_config({**base_config(), "episodes_per_combo": 1})).run()[0]
    payload = episode.to_dict()
    payload["episode_id"] = "ep_tampered"

    with pytest.raises(ValueError, match="serialized planned identity mismatch"):
        Episode.from_dict(payload)
