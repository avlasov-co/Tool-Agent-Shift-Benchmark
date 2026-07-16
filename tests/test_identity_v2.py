from __future__ import annotations

from pathlib import Path

import pytest

from tool_agent_shift_benchmark.core.catalog import PluginCatalog
from tool_agent_shift_benchmark.core.config import load_config
from tool_agent_shift_benchmark.core.identity import IDENTITY_SCHEMA_VERSION
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec
from tool_agent_shift_benchmark.core.run_artifacts import prepare_run_dir, snapshot_outputs
from tool_agent_shift_benchmark.run_eval import run_eval


def base_config() -> dict[str, object]:
    return {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["schema_drift"],
        "fault_severities": [1.0],
        "episodes_per_combo": 2,
        "episode_steps": 2,
        "monitor": "composite",
        "monitor_policy": "gate",
    }


def planner(config: dict[str, object], *, seed: int = 42, **overrides: object) -> ExperimentPlanner:
    catalog = PluginCatalog(include_external=False)
    return ExperimentPlanner(ExperimentSpec.from_config(config, seed=seed, **overrides), catalog)


def test_equivalent_yaml_and_directories_have_the_same_identity(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_path = first_dir / "experiment.yaml"
    second_path = second_dir / "experiment.yaml"
    first_path.write_text(
        """\
schema_version: 2
environments: [file_ops]
agents: [naive]
faults: [schema_drift]
fault_severities: [1]
episodes_per_combo: 2
episode_steps: 2
monitor: composite
monitor_policy: gate
""",
        encoding="utf-8",
    )
    second_path.write_text(
        """\
schema_version: 2
monitor_policy: gate
episode_steps: 2
episodes_per_combo: 2
fault_severities:
  - 1.0
faults:
  - schema_drift
agents:
  - naive
environments:
  - file_ops
monitor: composite
""",
        encoding="utf-8",
    )
    first_config = {**load_config(first_path), "_config_path": str(first_path), "_working_directory": str(first_dir)}
    second_config = {
        **load_config(second_path),
        "_config_path": str(second_path),
        "_working_directory": str(second_dir),
    }

    first = planner(first_config)
    second = planner(second_config)

    assert first.run_id == second.run_id
    assert first.config_digest == second.config_digest
    assert first.identity.semantic == second.identity.semantic
    assert first.identity.operational != second.identity.operational


def test_operational_settings_do_not_change_scientific_identity() -> None:
    complete = planner(base_config())
    target = complete.plan()[0].episode_id
    operational = {
        **base_config(),
        "_config_path": "/other/config.yaml",
        "_working_directory": "/tmp/worker",
        "output_path": "/tmp/results",
        "logging": "verbose",
        "artifact_policy": "legacy",
        "progress_display": False,
        "retry_attempts": 4,
        "failure_policy": "fail_fast",
        "execution_batch_size": 32,
    }
    changed = planner(
        operational,
        workers=8,
        episode_ids=[target],
        selection_offset=0,
        selection_limit=1,
        partition_index=0,
        partition_count=1,
    )

    assert changed.run_id == complete.run_id
    assert changed.config_digest == complete.config_digest
    assert changed.identity.operational.workers == 8
    assert changed.identity.operational.output_path == "/tmp/results"


@pytest.mark.parametrize(
    ("change", "seed"),
    [
        ({"environments": ["calendar_ops"]}, 42),
        ({"agents": ["conservative"]}, 42),
        ({"faults": ["missing_field"]}, 42),
        ({"fault_severities": [0.5]}, 42),
        ({"episodes_per_combo": 3}, 42),
        ({"episode_steps": 3}, 42),
        ({"monitor_policy": "record"}, 42),
        ({"scenario_generator_version": "2.0.0"}, 42),
        ({"scenario_schema_version": "v2"}, 42),
        ({"scenario_split": "holdout", "scenario_splits": [{"name": "holdout", "indices": [0]}]}, 42),
        ({"evaluator_version": "2.0.0"}, 42),
        ({"monitor_modes": ["schema_only"]}, 42),
        ({"policy_resources": {"policy": "a" * 64}}, 42),
        ({}, 43),
    ],
)
def test_semantic_changes_alter_run_identity(change: dict[str, object], seed: int) -> None:
    baseline = planner(base_config())
    changed = planner({**base_config(), **change}, seed=seed)

    assert changed.run_id != baseline.run_id
    assert changed.config_digest != baseline.config_digest


def test_non_commutative_component_order_changes_identity() -> None:
    forward = planner(
        {
            **base_config(),
            "shift_chains": [["missing_field", "schema_drift"]],
        }
    )
    reverse = planner(
        {
            **base_config(),
            "shift_chains": [["schema_drift", "missing_field"]],
        }
    )

    assert forward.run_id != reverse.run_id
    forward_names = [component.name for component in forward.identity.semantic.shift_chains[0]]
    reverse_names = [component.name for component in reverse.identity.semantic.shift_chains[0]]
    assert forward_names == ["missing_field", "schema_drift"]
    assert reverse_names == ["schema_drift", "missing_field"]


def test_only_proven_order_insensitive_matrix_collections_are_normalized() -> None:
    first = planner(
        {
            **base_config(),
            "environments": ["risk_ops", "file_ops"],
            "agents": ["retry", "naive"],
            "shift_chains": [["missing_field"], ["schema_drift"]],
            "fault_severities": [1.0, 0.5],
        }
    )
    reordered = planner(
        {
            **base_config(),
            "environments": ["file_ops", "risk_ops"],
            "agents": ["naive", "retry"],
            "shift_chains": [["schema_drift"], ["missing_field"]],
            "fault_severities": [0.5, 1],
        }
    )

    assert first.run_id == reordered.run_id
    assert first.identity.semantic == reordered.identity.semantic


def test_identity_document_contains_required_typed_fields() -> None:
    identity = planner(base_config()).identity
    semantic = identity.semantic

    assert identity.schema_version == IDENTITY_SCHEMA_VERSION
    assert semantic.identity_schema_version == IDENTITY_SCHEMA_VERSION
    assert semantic.scenario_generator.name == "synthetic_indexed"
    assert semantic.scenario_schema_version == "v1"
    assert semantic.environments[0].version == "1.0.0"
    assert semantic.agents[0].version == "1.0.0"
    assert semantic.fault_schedules[0].cadence == "each_step"
    assert semantic.oversight_treatment == "gate"
    assert semantic.step_semantics.maximum_steps == 2
    assert semantic.scenario_seed_streams.root_seed == 42
    assert semantic.evaluator.name == "hidden_state_evaluator"


def test_normalized_identity_is_saved_in_run_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """\
environments: [file_ops]
schema_version: 2
agents: [naive]
faults: [normal]
fault_severities: [1.0]
episodes_per_combo: 1
episode_steps: 1
monitor: composite
monitor_policy: record
""",
        encoding="utf-8",
    )

    episodes = run_eval(str(config_path), 7)
    run_dir = prepare_run_dir("identity", overwrite=True)
    manifest = snapshot_outputs(run_dir, command=["tasb", "run"])

    assert manifest["run_id"] == episodes[0].run_id
    assert manifest["identity_schema_version"] == IDENTITY_SCHEMA_VERSION
    assert manifest["normalized_semantic_identity"]["identity_schema_version"] == IDENTITY_SCHEMA_VERSION
    assert manifest["normalized_semantic_identity"]["scenario_seed_streams"]["root_seed"] == 7
    assert manifest["operational_settings"]["config_path"] == str(config_path)
    assert manifest["config_digest"].startswith("cfg_")
