from __future__ import annotations

from pathlib import Path

from tool_agent_shift_benchmark.agents import AGENT_ROLES, DIAGNOSTIC_AGENTS, REFERENCE_AGENTS
from tool_agent_shift_benchmark.core.competence import (
    COMPETENCE_REQUIREMENTS,
    evaluate_clean_competence,
    run_clean_competence_preflight,
)
from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.orchestration import ExperimentSpec
from tool_agent_shift_benchmark.core.serialization import read_json
from tool_agent_shift_benchmark.environments.file_ops import FileOpsEnvironment
from tool_agent_shift_benchmark.run_eval import run_eval


def _config(**changes: object) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 2,
        "environments": ["file_ops", "calendar_ops", "risk_ops"],
        "agents": ["naive"],
        "faults": ["missing_field"],
        "fault_severities": [1.0],
        "episodes_per_combo": 4,
        "episode_steps": 1,
        "monitor_policy": "record",
    }
    config.update(changes)
    return config


def test_diagnostic_and_reference_agent_roles_are_explicit_and_disjoint() -> None:
    assert set(DIAGNOSTIC_AGENTS).isdisjoint(REFERENCE_AGENTS)
    assert all(AGENT_ROLES[name] == "diagnostic" for name in DIAGNOSTIC_AGENTS)
    assert all(AGENT_ROLES[name] == "reference" for name in REFERENCE_AGENTS)


def test_file_clean_recommendation_uses_declared_safe_target() -> None:
    for seed in range(12):
        environment = FileOpsEnvironment(seed=seed, scenario_index=0)
        initial = environment.tool_response()
        environment.execute(
            ObservationContext.from_environment(environment, initial.observation).recommended_action(
                initial.observation.data
            )
        )
        response = environment.tool_response()
        context = ObservationContext.from_environment(environment, response.observation)
        action = context.recommended_action(response.observation.data)
        target = next(item for item in environment.files if item["path"] == action.target)

        assert action.target == environment.task_target
        assert target["hidden_protected"] is False


def test_reference_agents_pass_environment_specific_clean_golden_gates() -> None:
    report = run_clean_competence_preflight(ExperimentSpec.from_config(_config(), seed=67))

    assert report["passed"] is True
    assert report["failed_gates"] == []
    assert len(report["rows"]) == len(COMPETENCE_REQUIREMENTS) * len(REFERENCE_AGENTS)
    assert all(row["passed"] for row in report["rows"])
    assert all(row["safety"] == 1.0 for row in report["rows"])


def test_failed_or_incomplete_gate_remains_visible() -> None:
    report = evaluate_clean_competence(
        [],
        expected={("file_ops", REFERENCE_AGENTS[0]): 2},
        orchestration_errors=[{"episode_id": "ep_failed", "error_type": "RuntimeError"}],
    )

    assert report["passed"] is False
    assert report["failed_gates"] == [f"file_ops:{REFERENCE_AGENTS[0]}"]
    assert report["rows"][0]["completed_episodes"] == 0
    assert report["orchestration_errors"]


def test_run_and_analysis_metadata_include_competence_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "clean-gate.yaml"
    config_path.write_text(
        """\
schema_version: 2
environments: [file_ops]
agents: [naive]
faults: [normal]
fault_severities: [1.0]
episodes_per_combo: 1
episode_steps: 1
monitor_policy: record
""",
        encoding="utf-8",
    )

    run_eval(str(config_path), seed=71)
    config = read_json(tmp_path / "results" / "config.json")
    report = read_json(tmp_path / "results" / "competence_report.json")

    assert report["passed"] is True
    assert config["competence_gate"]["passed"] is True
    assert config["competence_gate"]["failed_gates"] == []
