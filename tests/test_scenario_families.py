from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from tool_agent_shift_benchmark.agents import AGENTS
from tool_agent_shift_benchmark.core.artifacts import ArtifactStore
from tool_agent_shift_benchmark.core.config_schema import ConfigValidationError, parse_config_data
from tool_agent_shift_benchmark.core.context import (
    POLICY_VISIBLE_SCENARIO_ID,
    ObservationContext,
    redact_response_for_policy,
)
from tool_agent_shift_benchmark.core.orchestration import ExperimentPlanner, ExperimentSpec, RunCoordinator
from tool_agent_shift_benchmark.core.scenarios import (
    SCENARIO_COVERAGE_CONTRACT,
    SCENARIO_FAMILY_CONTRACT,
    SCENARIO_MANIFEST_CONTRACT,
    SCENARIO_SPLIT_CONTRACT,
    SPLIT_NAMESPACE_SIZE,
    STANDARD_SPLIT_OFFSETS,
    scenario_coverage_summary,
)
from tool_agent_shift_benchmark.core.serialization import canonical_dumps, read_csv, read_json
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.run_eval import run_eval


def config(*, split: str = "development", count: int = 4) -> dict[str, object]:
    return {
        "schema_version": 2,
        "environments": ["file_ops", "calendar_ops", "risk_ops"],
        "agents": ["naive"],
        "faults": ["normal"],
        "fault_severities": [1.0],
        "episodes_per_combo": count,
        "episode_steps": 6,
        "scenario_split": split,
        "oversight_modes": ["record_only"],
    }


def test_standard_splits_are_deterministic_reserved_and_non_overlapping() -> None:
    plans = {
        split: ExperimentPlanner(ExperimentSpec.from_config(config(split=split), seed=211)).canonical_plan()
        for split in ("development", "validation", "challenge")
    }
    repeated = ExperimentPlanner(ExperimentSpec.from_config(config(split="challenge"), seed=211)).canonical_plan()

    index_sets = {split: {item.scenario_index for item in plan} for split, plan in plans.items()}
    assert index_sets["development"] == set(range(0, 4))
    assert index_sets["validation"] == set(range(SPLIT_NAMESPACE_SIZE, SPLIT_NAMESPACE_SIZE + 4))
    assert index_sets["challenge"] == set(range(2 * SPLIT_NAMESPACE_SIZE, 2 * SPLIT_NAMESPACE_SIZE + 4))
    assert index_sets["development"].isdisjoint(index_sets["validation"])
    assert index_sets["development"].isdisjoint(index_sets["challenge"])
    assert index_sets["validation"].isdisjoint(index_sets["challenge"])
    assert {item.scenario_spec.content_hash for item in plans["challenge"]} == {
        item.scenario_spec.content_hash for item in repeated
    }
    assert all(item.scenario_spec.split == split for split, plan in plans.items() for item in plan)
    assert len({item.scenario_spec.content_hash for plan in plans.values() for item in plan}) == 36


def test_overlapping_custom_splits_are_rejected() -> None:
    value = config(count=2)
    value["scenario_split"] = "first"
    value["scenario_splits"] = [
        {"name": "first", "indices": [10, 11]},
        {"name": "second", "indices": [11, 12]},
    ]

    with pytest.raises(ConfigValidationError, match="overlaps splits") as raised:
        parse_config_data(value)

    assert raised.value.path == "$.scenario_splits"


def test_parameterized_families_cover_declared_distribution_dimensions() -> None:
    specs = []
    for split in ("development", "validation", "challenge"):
        planner = ExperimentPlanner(ExperimentSpec.from_config(config(split=split, count=12), seed=223))
        planner.canonical_plan()
        specs.extend(planner.scenario_specs())

    summary = scenario_coverage_summary(specs)
    repeated = scenario_coverage_summary(reversed(specs))

    assert summary == repeated
    assert summary["contract"] == SCENARIO_COVERAGE_CONTRACT
    assert summary["scenario_count"] == 108
    assert set(summary["dimensions"]["split"]) == {"development", "validation", "challenge"}
    assert set(summary["dimensions"]["family"]) == {
        "file_ops_parameterized_resource_lifecycle",
        "calendar_ops_parameterized_coordination",
        "risk_ops_parameterized_market_lifecycle",
    }
    assert len(summary["dimensions"]["task_type"]) >= 9
    assert {"active_lock", "late_conflict", "volatility_jump"} & set(summary["dimensions"]["hazard"])
    assert "private_meeting_note" in summary["dimensions"]["protected_object_type"]
    assert "operation_deadline" in summary["dimensions"]["temporal_behavior"]
    assert "schema_drift" in summary["dimensions"]["applicable_fault"]
    for spec in specs:
        assert spec.contract == SCENARIO_MANIFEST_CONTRACT
        assert spec.family.contract == SCENARIO_FAMILY_CONTRACT
        assert spec.family.parameters
        assert spec.family.constraint_dimensions
        assert spec.family.temporal_behavior
        assert spec.family.applicable_faults


def test_split_and_scenario_identity_are_absent_from_policy_inputs() -> None:
    coordinator = RunCoordinator(ExperimentSpec.from_config(config(split="challenge", count=1), seed=227))
    episodes = coordinator.run()

    assert episodes
    assert all(episode.metadata["scenario_manifest"]["split"] == "challenge" for episode in episodes)
    for episode in episodes:
        policy_payload = canonical_dumps(episode.metadata["step_trace"])
        assert "challenge" not in policy_payload
        assert episode.scenario_id not in policy_payload
        assert all(
            step["tool_response"]["observation"]["scenario_id"] == POLICY_VISIBLE_SCENARIO_ID
            for step in episode.metadata["step_trace"]
        )


def test_first_party_agents_are_invariant_to_scenario_and_split_labels() -> None:
    environment = FileOpsEnvironment(seed=229, scenario_index=0)
    clean = environment.tool_response()
    alternate = replace(
        clean,
        observation=replace(
            clean.observation,
            scenario_id="challenge_memorization_probe_999999",
            metadata={**clean.observation.metadata, "scenario_split": "challenge"},
        ),
    )
    first = redact_response_for_policy(clean)
    second = redact_response_for_policy(alternate)
    first_context = ObservationContext.from_environment(environment, first.observation)
    second_context = ObservationContext.from_environment(environment, second.observation)

    assert not hasattr(first_context, "scenario_id")
    assert first.to_dict() == second.to_dict()
    for agent_type in AGENTS.values():
        first_decision = agent_type().decide(first_context, first)
        second_decision = agent_type().decide(second_context, second)
        assert first_decision.to_dict() == second_decision.to_dict()
        source = inspect.getsource(agent_type)
        assert "scenario_id" not in source
        assert "scenario_split" not in source
        assert "challenge" not in source
        assert "behavior_seed" not in source


def test_coverage_artifacts_and_contracts_are_manifested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "challenge.yaml"
    config_path.write_text(
        """\
schema_version: 2
environments: [file_ops, calendar_ops, risk_ops]
agents: [naive]
faults: [normal]
episodes_per_combo: 2
episode_steps: 6
scenario_split: challenge
oversight_modes: [record_only]
""",
        encoding="utf-8",
    )

    store = ArtifactStore(tmp_path / "run")
    episodes = run_eval(str(config_path), 233, artifact_store=store)
    coverage = read_json(store.run_dir / "results" / "scenario_coverage.json")
    rows = read_csv(store.run_dir / "results" / "scenario_coverage.csv")
    manifest = store.finalize(command=["tasb", "run"])

    assert len(episodes) == 6
    assert coverage["scenario_count"] == 6
    assert coverage["dimensions"]["split"] == {"challenge": 6}
    assert {row["dimension"] for row in rows} >= {
        "task_type",
        "hazard",
        "protected_object_type",
        "constraint_dimension",
        "temporal_behavior",
        "applicable_fault",
    }
    assert manifest["scenario_manifest_contract"] == SCENARIO_MANIFEST_CONTRACT
    assert manifest["scenario_family_contract"] == SCENARIO_FAMILY_CONTRACT
    assert manifest["scenario_split_contract"] == SCENARIO_SPLIT_CONTRACT
    assert manifest["scenario_coverage_hash"] == coverage["coverage_hash"]
    assert STANDARD_SPLIT_OFFSETS["challenge"] == 2 * SPLIT_NAMESPACE_SIZE
