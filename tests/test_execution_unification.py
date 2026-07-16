from __future__ import annotations

import json

from tool_agent_shift_benchmark.analysis.run_pairwise_compounds import _plan_fault_combo
from tool_agent_shift_benchmark.cli import _plan_command, build_parser
from tool_agent_shift_benchmark.core.execution import ExecutionRequest, normalize_execution_request
from tool_agent_shift_benchmark.core.orchestration import RunCoordinator
from tool_agent_shift_benchmark.core.serialization import canonicalize


def _config(path) -> None:
    path.write_text(
        """\
schema_version: 2
environments: [file_ops]
agents: [naive]
faults: [normal, stale_observation]
fault_severities: [1.0]
episodes_per_combo: 2
""",
        encoding="utf-8",
    )


def test_cli_and_api_use_the_same_normalized_execution_plan(tmp_path, capsys) -> None:
    config = tmp_path / "small.yaml"
    _config(config)
    request = ExecutionRequest(config_path=str(config), seed=17, workers=2)
    api_plan = normalize_execution_request(request)

    _plan_command(build_parser().parse_args(["plan", "--config", str(config), "--seed", "17"]))
    cli_plan = json.loads(capsys.readouterr().out)

    assert cli_plan["execution"]["schema_version"] == "execution-plan-v1"
    assert cli_plan["run_id"] == api_plan.planner.run_id
    assert cli_plan["matrix"] == canonicalize([item.to_dict() for item in api_plan.episodes])


def test_worker_count_changes_only_execution_not_the_normalized_plan_ids(tmp_path) -> None:
    config = tmp_path / "workers.yaml"
    _config(config)
    one = normalize_execution_request(ExecutionRequest(config_path=str(config), seed=23, workers=1))
    many = normalize_execution_request(ExecutionRequest(config_path=str(config), seed=23, workers=3))

    assert one.planner.run_id == many.planner.run_id
    assert [item.episode_id for item in one.episodes] == [item.episode_id for item in many.episodes]
    assert [episode.episode_id for episode in RunCoordinator(one.spec).run()] == [
        episode.episode_id for episode in RunCoordinator(many.spec).run()
    ]


def test_pairwise_compatibility_plan_is_a_projection_of_the_common_planner() -> None:
    plans = _plan_fault_combo(
        env_name="file_ops",
        agent_name="naive",
        fault_names=("schema_drift", "missing_field"),
        severity=1.0,
        episodes_per_combo=2,
        seed=29,
    )

    assert plans
    assert all(item.episode.identity.identity_schema_version == "20" for item in plans)
    assert all(item.episode.shift == "schema_drift+missing_field" for item in plans)
