from __future__ import annotations

from pathlib import Path

import pytest

from tool_agent_shift_benchmark.cli import main as cli_main
from tool_agent_shift_benchmark.core.config import ConfigSyntaxError, dump_config_yaml, load_config, load_raw_config
from tool_agent_shift_benchmark.core.config_schema import (
    CONFIG_SCHEMA_VERSION,
    ConfigValidationError,
    migrate_config_data,
    parse_config_data,
    validate_config,
)
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec
from tool_agent_shift_benchmark.core.serialization import read_json
from tool_agent_shift_benchmark.run_eval import run_eval


def valid_config() -> dict[str, object]:
    return {
        "schema_version": 2,
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["normal"],
        "fault_severities": [1.0],
        "episodes_per_combo": 2,
        "episode_steps": 1,
        "monitor": "composite",
        "monitor_policy": "gate",
    }


def test_every_shipped_config_is_schema_v2_and_normalizes() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in sorted((root / "configs").glob("*.yaml")):
        validate_config(path, pairwise=path.name == "compound_matrix.yaml")
        normalized = load_config(path)
        assert normalized["schema_version"] == CONFIG_SCHEMA_VERSION
        assert normalized["fault_schedules"]
        assert normalized["scenario_splits"]
        assert normalized["migration"]["source_schema_version"] == "unversioned-v1"


def test_unknown_keys_are_rejected_at_their_exact_path() -> None:
    with pytest.raises(ConfigValidationError) as raised:
        parse_config_data({**valid_config(), "workerz": 4}, source="experiment.yaml")

    assert raised.value.source == "experiment.yaml"
    assert raised.value.path == "$.workerz"
    assert raised.value.message == "unknown key"


def test_malformed_yaml_and_duplicate_keys_have_locations(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.yaml"
    duplicate = tmp_path / "duplicate.yaml"
    complex_key = tmp_path / "complex-key.yaml"
    malformed.write_text("schema_version: 2\nagents: [naive\n", encoding="utf-8")
    duplicate.write_text("schema_version: 2\nworkers: 1\nworkers: 2\n", encoding="utf-8")
    complex_key.write_text("? [not, scalar]\n: value\n", encoding="utf-8")

    with pytest.raises(ConfigSyntaxError) as malformed_error:
        load_raw_config(malformed)
    with pytest.raises(ConfigSyntaxError) as duplicate_error:
        load_raw_config(duplicate)
    with pytest.raises(ConfigSyntaxError) as complex_key_error:
        load_raw_config(complex_key)

    assert malformed_error.value.path == str(malformed)
    assert malformed_error.value.line >= 2
    assert malformed_error.value.column >= 1
    assert duplicate_error.value.path == str(duplicate)
    assert duplicate_error.value.line == 3
    assert duplicate_error.value.column == 1
    assert "duplicate key 'workers'" in duplicate_error.value.problem
    assert complex_key_error.value.path == str(complex_key)
    assert complex_key_error.value.line == 1
    assert "scalar and hashable" in complex_key_error.value.problem


@pytest.mark.parametrize(
    ("change", "path"),
    [
        ({"workers": 0}, "$.workers"),
        ({"workers": True}, "$.workers"),
        ({"episodes_per_combo": 0}, "$.episodes_per_combo"),
        ({"episode_steps": "2"}, "$.episode_steps"),
        ({"scenario_indices": [-1]}, "$.scenario_indices[0]"),
        ({"selection_offset": -1}, "$.selection_offset"),
        ({"partition_index": 0}, "$.partition_index"),
        ({"agents": ["unknown"]}, "$.agents[0]"),
        ({"environments": ["unknown"]}, "$.environments[0]"),
        ({"monitor": "unknown"}, "$.monitor[0]"),
        ({"monitor_policy": "sometimes"}, "$.monitor_policy"),
        ({"monitor_modes": ["unknown"]}, "$.monitor_modes[0]"),
        ({"shift_chains": [[]]}, "$.shift_chains[0]"),
        ({"fault_severities": [1.1]}, "$.fault_severities[0]"),
        ({"artifact_policy": "discard"}, "$.artifact_policy"),
        ({"retry_attempts": -1}, "$.retry_attempts"),
        ({"requery_attempts": -1}, "$.requery_attempts"),
        ({"failure_policy": "ignore"}, "$.failure_policy"),
        ({"progress_display": "yes"}, "$.progress_display"),
        ({"execution_batch_size": 0}, "$.execution_batch_size"),
        ({"logging": "everything"}, "$.logging"),
        ({"scenario_split": "missing"}, "$.scenario_split"),
    ],
)
def test_typed_schema_rejects_invalid_values(change: dict[str, object], path: str) -> None:
    with pytest.raises(ConfigValidationError) as raised:
        parse_config_data({**valid_config(), **change})

    assert raised.value.path == path


def test_fault_schedules_are_validated_against_step_and_shift_semantics() -> None:
    config = {
        **valid_config(),
        "faults": ["schema_drift"],
        "episode_steps": 2,
        "fault_schedules": [
            {
                "shift_chain": ["schema_drift"],
                "severity": 1.0,
                "start_step": 0,
                "end_step": 1,
                "cadence": "each_step",
            }
        ],
    }
    assert parse_config_data(config).fault_schedules[0].end_step == 1
    config["fault_schedules"][0]["cadence"] = "random"  # type: ignore[index]
    with pytest.raises(ConfigValidationError, match="only 'each_step'"):
        parse_config_data(config)


def test_declared_external_plugin_validates_without_loading_plugin_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_entry_points():
        raise AssertionError("plugin discovery executed during schema validation")

    monkeypatch.setattr("tool_agent_shift_benchmark.core.catalog.entry_points", forbidden_entry_points)
    config = {
        **valid_config(),
        "agents": ["external_agent"],
        "plugin_references": [
            {
                "kind": "agent",
                "name": "external_agent",
                "version": "3.2.1",
                "contract_version": "1",
                "entry_point": "package.module:Agent",
            }
        ],
    }

    parsed = parse_config_data(config)

    assert parsed.agents == ("external_agent",)
    assert parsed.plugin_references[0].version == "3.2.1"


def test_plugin_reference_contract_and_shape_are_strict() -> None:
    config = {
        **valid_config(),
        "plugin_references": [
            {
                "kind": "agent",
                "name": "external_agent",
                "version": "1.0.0",
                "contract_version": "999",
                "entry_point": "package:Agent",
            }
        ],
    }
    with pytest.raises(ConfigValidationError) as raised:
        parse_config_data(config)
    assert raised.value.path == "$.plugin_references[0].contract_version"


def test_scenario_splits_are_semantic_and_control_the_canonical_plan() -> None:
    config = {
        **valid_config(),
        "episodes_per_combo": 4,
        "scenario_split": "holdout",
        "scenario_splits": [
            {"name": "train", "indices": [0, 2]},
            {"name": "holdout", "indices": [1, 3]},
        ],
    }
    planner = ExperimentPlanner(ExperimentSpec.from_config(config, seed=41))
    reordered = {
        **config,
        "scenario_splits": [
            {"name": "train", "indices": [2, 0]},
            {"name": "holdout", "indices": [3, 1]},
        ],
    }
    reordered_planner = ExperimentPlanner(ExperimentSpec.from_config(reordered, seed=41))

    assert planner.identity.semantic.scenario_split == "holdout"
    assert planner.identity.semantic.scenario_split_indices == (1, 3)
    assert [item.scenario_index for item in planner.canonical_plan()] == [1, 3]
    assert reordered_planner.run_id == planner.run_id
    assert reordered_planner.identity.semantic == planner.identity.semantic


def test_v1_migration_is_deterministic_idempotent_and_explicit() -> None:
    legacy = {
        "episodes_per_combo": 2,
        "episode_steps": 2,
        "fault_severities": [1, 0.5],
        "environments": ["file_ops"],
        "agents": ["naive"],
        "faults": ["normal", "schema_drift"],
    }
    migrated, decisions = migrate_config_data(legacy, source="legacy.yaml")
    reordered, reordered_decisions = migrate_config_data(dict(reversed(list(legacy.items()))), source="legacy.yaml")
    second, second_decisions = migrate_config_data(migrated.to_dict(), source="migrated.yaml")

    assert migrated.schema_version == 2
    assert migrated.monitor_policy == "record"
    assert decisions == reordered_decisions
    assert decisions and "legacy file-runner behavior" in decisions[0]
    assert migrated.to_dict() == reordered.to_dict()
    assert dump_config_yaml(migrated.to_dict()) == dump_config_yaml(reordered.to_dict())
    assert second.to_dict() == migrated.to_dict()
    assert second_decisions == ()


def test_migration_rejects_unknown_and_ambiguous_legacy_values() -> None:
    with pytest.raises(ConfigValidationError) as unknown:
        migrate_config_data({"workerz": 2})
    assert unknown.value.path == "$.workerz"

    with pytest.raises(ConfigValidationError, match="ambiguous legacy values"):
        migrate_config_data(
            {
                "faults": ["schema_drift"],
                "shift_chains": [["missing_field", "schema_drift"]],
            }
        )


def test_config_cli_validate_and_migrate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    legacy = tmp_path / "legacy.yaml"
    migrated = tmp_path / "migrated.yaml"
    legacy.write_text(
        "episodes_per_combo: 1\nenvironments: [file_ops]\nagents: [naive]\nfaults: [normal]\n",
        encoding="utf-8",
    )

    cli_main(["config", "migrate", str(legacy), "--output", str(migrated)])
    migrate_output = capsys.readouterr()
    cli_main(["config", "validate", str(migrated)])
    validate_output = capsys.readouterr()

    assert "migration decision:" in migrate_output.err
    assert "migrated config written" in migrate_output.out
    assert "config valid (schema v2)" in validate_output.out
    assert load_config(migrated)["schema_version"] == 2


def test_every_run_saves_the_resolved_normalized_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "run.yaml"
    config_path.write_text(
        """\
schema_version: 2
environments: [file_ops]
agents: [naive]
faults: [normal]
episodes_per_combo: 1
monitor_policy: record
""",
        encoding="utf-8",
    )

    run_eval(str(config_path), 43, workers=3)
    payload = read_json(tmp_path / "results" / "config.json")

    expected = {
        **load_config(config_path),
        "seed": 43,
        "workers": 3,
        "monitor_modes": ["full_composite_monitor"],
    }
    assert payload["normalized_config"] == expected
    assert payload["config"] == payload["normalized_config"]
    assert payload["normalized_config"]["schema_version"] == 2
    assert "_config_path" not in payload["normalized_config"]
    assert payload["operational_request"]["source_config_path"] == str(config_path)
