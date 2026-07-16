from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.scenarios import (
    SCENARIO_MANIFEST_SCHEMA_VERSION,
    ScenarioManifestError,
    ScenarioSpec,
    read_scenario_manifest,
)
from tool_agent_shift_benchmark.core.serialization import canonical_bytes, canonical_dumps, read_json, write_json
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment


def _config(**changes: object) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["normal", "missing_field"],
        "fault_severities": [1.0],
        "episodes_per_combo": 2,
        "episode_steps": 1,
        "monitor_policy": "record",
    }
    config.update(changes)
    return config


def test_scenario_spec_is_structurally_separated_hashed_and_deeply_immutable() -> None:
    spec = FileOpsEnvironment(seed=91, scenario_index=2).scenario_spec

    assert spec.schema_version == SCENARIO_MANIFEST_SCHEMA_VERSION
    assert spec.public_task_description
    assert spec.policy_visible_state
    assert spec.hidden_evaluator_state
    assert spec.constraints
    assert spec.transition_parameters
    assert len(spec.content_hash) == 64
    with pytest.raises(TypeError):
        spec.constraints["allowed_root"] = "/tampered"  # type: ignore[index]


def test_run_writes_one_manifest_per_scenario_and_plan_hides_evaluator_state(tmp_path: Path) -> None:
    spec = ExperimentSpec.from_config(_config(), seed=17)
    planner = ExperimentPlanner(spec)
    plan = planner.canonical_plan()
    manifest_dir = tmp_path / "scenarios"

    RunCoordinator(spec).run(scenario_manifest_dir=manifest_dir)

    assert len(list(manifest_dir.glob("*.json"))) == 2
    assert len({item.scenario_spec.content_hash for item in plan}) == 2
    assert all(
        item.scenario_spec.content_hash == read_scenario_manifest(manifest_dir, item.scenario_id).content_hash
        for item in plan
    )
    public_plan = canonical_dumps([item.to_dict() for item in plan])
    assert "hidden_evaluator_state" not in public_plan
    assert "latent_hazards" not in public_plan


def test_tamper_detection_rejects_modified_manifest(tmp_path: Path) -> None:
    spec = ExperimentSpec.from_config(_config(faults=["normal"], episodes_per_combo=1), seed=19)
    manifest_dir = tmp_path / "scenarios"
    RunCoordinator(spec).run(scenario_manifest_dir=manifest_dir)
    path = next(manifest_dir.glob("*.json"))
    payload = read_json(path)
    payload["constraints"]["allowed_root"] = "/tampered"
    write_json(path, payload)

    with pytest.raises(ScenarioManifestError, match="hash mismatch"):
        read_scenario_manifest(manifest_dir, "file_ops_scenario_0")


def test_replay_loads_manifest_without_invoking_current_generator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(faults=["normal"], episodes_per_combo=1)
    original = ExperimentSpec.from_config(config, seed=23)
    manifest_dir = tmp_path / "scenarios"
    episodes = RunCoordinator(original).run(scenario_manifest_dir=manifest_dir)

    def forbidden_reset(self: FileOpsEnvironment, seed: int, scenario_index: int = 0) -> None:
        raise AssertionError("current generator was invoked during replay")

    monkeypatch.setattr(FileOpsEnvironment, "reset", forbidden_reset)
    replay = ExperimentSpec.from_config(
        {**config, "scenario_manifest_path": str(manifest_dir)},
        seed=23,
        replay_episode_ids=[episodes[0].episode_id],
    )
    replayed = RunCoordinator(replay).run()

    assert replayed[0].episode_id == episodes[0].episode_id
    assert (
        replayed[0].metadata["scenario_manifest"]["content_hash"]
        == episodes[0].metadata["scenario_manifest"]["content_hash"]
    )


def test_explicit_v1_manifest_migrates_and_incomplete_legacy_data_fails() -> None:
    legacy = {
        "schema_version": 1,
        "generator": {"name": "legacy", "version": "1.0.0"},
        "environment": "file_ops",
        "scenario_id": "file_ops_scenario_0",
        "scenario_index": 0,
        "scenario_seed": 7,
        "task": {"task": "clean_temp", "target": "/workspace/tmp/a.tmp"},
        "visible_state": {"data": {"files": []}, "timestamp": 1000},
        "hidden_state": {"files": []},
        "constraints": {"allowed_root": "/workspace"},
        "transition_parameters": {"initial_time": 1000},
    }

    migrated = ScenarioSpec.from_dict(legacy)

    assert migrated.schema_version == 3
    assert migrated.family.name == "file_ops_legacy_template"
    assert migrated.seed_stream_algorithm == "legacy-explicit-seed-v1"
    with pytest.raises(ScenarioManifestError, match="not reconstructible"):
        ScenarioSpec.from_dict({"schema_version": 1, "scenario_id": "incomplete"})


def test_hashed_v2_manifest_is_validated_and_migrated() -> None:
    current = FileOpsEnvironment(seed=97, scenario_index=3).scenario_spec
    payload = {
        "schema_version": 2,
        "contract": "scenario-manifest-v2",
        "generator_name": "deterministic_synthetic_scenarios",
        "generator_version": "2.1.0",
        "environment": current.environment,
        "scenario_id": current.scenario_id,
        "scenario_index": current.scenario_index,
        "scenario_seed": current.scenario_seed,
        "seed_stream_algorithm": current.seed_stream_algorithm,
        "public_task_description": dict(current.public_task_description),
        "policy_visible_state": dict(current.policy_visible_state),
        "hidden_evaluator_state": dict(current.hidden_evaluator_state),
        "constraints": dict(current.constraints),
        "transition_parameters": dict(current.transition_parameters),
    }
    payload["content_hash"] = hashlib.sha256(canonical_bytes(payload)).hexdigest()

    migrated = ScenarioSpec.from_dict(payload)

    assert migrated.schema_version == 3
    assert migrated.contract == "scenario-manifest-v3"
    assert migrated.split == "legacy"
    tampered = {**payload, "scenario_seed": 98}
    with pytest.raises(ScenarioManifestError, match="hash mismatch"):
        ScenarioSpec.from_dict(tampered)
